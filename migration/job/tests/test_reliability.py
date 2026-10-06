"""Reliability regressions: bounded external calls (timeouts), jittered retry, contract batch_id,

statement-handle cleanup and the Db2 FK-violation guard mapping (CONTRACTS.md §9.4.2, §9.4.4).
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from ldm.drivers.base import KeyRange
from ldm.drivers.db2 import Db2Source
from ldm.errors import PurgeGuardError, SourceError
from ldm.runner import execute, prepare_run
from ldm.stages import extract, load, purge, validate
from ldm.stages.extract import UnloadError, _command_unload

from .conftest import Seed, make_ctx, seed_source


@pytest.fixture
def seed() -> Seed:
    return seed_source()


# --- EXTRACT: the unload subprocess is bounded -------------------------------------------------


def _unload_ctx(tmp_path: Path, manifest: Path, seed: Seed, **env: str):
    ctx = make_ctx(tmp_path, seed.source, manifest=manifest, env=env)
    ts = ctx.table("DOCARCH")
    return ctx, ts, ctx.selection_for(ts.config), KeyRange("DOCARCH", 1, "k1", "k2")


def test_command_unload_is_bounded_and_timeout_fails_the_range(
    tmp_path: Path, manifest_after: Path, seed: Seed, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, ts, sel, rng = _unload_ctx(tmp_path, manifest_after, seed, LDM_UNLOAD_TIMEOUT_S="7")
    calls: dict[str, object] = {}

    def hung(argv, **kwargs):
        calls.update(kwargs)
        raise extract.subprocess.TimeoutExpired(cmd=argv, timeout=kwargs.get("timeout"))

    monkeypatch.setattr(extract.subprocess, "run", hung)
    with pytest.raises(UnloadError, match="timed out after 7s"):
        _command_unload(ctx, ts, sel, rng, tmp_path / "out.dat")
    assert calls["timeout"] == 7


def test_command_unload_default_timeout_is_one_hour(
    tmp_path: Path, manifest_after: Path, seed: Seed, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, ts, sel, rng = _unload_ctx(tmp_path, manifest_after, seed)
    monkeypatch.delenv("LDM_UNLOAD_TIMEOUT_S", raising=False)
    seen: dict[str, object] = {}

    class _Proc:
        returncode = 1
        stdout = ""
        stderr = ""

    def fake_run(argv, **kwargs):
        seen.update(kwargs)
        return _Proc()

    monkeypatch.setattr(extract.subprocess, "run", fake_run)
    with pytest.raises(UnloadError, match="exited 1"):
        _command_unload(ctx, ts, sel, rng, tmp_path / "out.dat")
    assert seen["timeout"] == 3600


# --- PURGE: retries keep the exponential cap but sleep a jittered delay ------------------------


def test_purge_retry_sleep_is_jittered_under_the_backoff_cap(
    tmp_path: Path, manifest_after: Path, seed: Seed, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = make_ctx(tmp_path, seed.source, manifest=manifest_after)
    prepare_run(ctx)
    for stage in (extract, load, validate):
        stage.run(ctx)

    source = seed.source
    real = source.purge_batch
    remaining = {"n": 3}

    def flaky(schema, table, key_column, keys, run_id, namespace, batch_no):
        if table == "DOCARCH" and remaining["n"]:
            remaining["n"] -= 1
            raise SourceError(-911, "40001", f"{table} batch {batch_no}: deadlock")
        return real(schema, table, key_column, keys, run_id, namespace, batch_no)

    monkeypatch.setattr(source, "purge_batch", flaky)
    slept: list[float] = []
    jittered: list[tuple[float, float]] = []
    monkeypatch.setattr(purge, "_sleep", slept.append)
    monkeypatch.setattr(purge, "_jitter", lambda lo, hi: jittered.append((lo, hi)) or (lo + hi) / 2)
    code, tables = execute(ctx, "purge")
    assert code == 0, tables
    assert jittered == [(0.0, 5.0), (0.0, 10.0), (0.0, 20.0)]
    assert slept == [2.5, 5.0, 10.0]


# --- LOAD: stg rows carry the 1-based batch id of contract §9.4.2 ------------------------------


def test_staging_rows_carry_one_based_batch_no(tmp_path: Path, manifest_after: Path, seed: Seed) -> None:
    ctx = make_ctx(tmp_path, seed.source, manifest=manifest_after)
    prepare_run(ctx)
    extract.extract_table(ctx, ctx.table("DOCARCH"))
    ctx.manifest.batch.load_batch_rows = 3
    ts = ctx.table("DOCARCH")
    load.load_table(ctx, ts)
    rows = [
        r
        for r in ctx.target.staging["DOCARCH"]
        if r.stg_id in ctx.target.staging_ns and ctx.target.staging_ns[r.stg_id] == (ctx.run_id, ctx.namespace)
    ]
    assert rows, "no staged rows"
    batches = [r.batch_no for r in rows]
    assert min(batches) == 1, f"batch_id must be 1-based, got {sorted(set(batches))}"
    assert sorted(set(batches)) == list(range(1, max(batches) + 1))
    counts = Counter(batches)
    assert counts[max(batches)] <= 3
    assert all(v == 3 for k, v in counts.items() if k != max(batches))


# --- Db2 driver: statement handle cleanup and the FK-violation guard ---------------------------


class _FakeIbmDb:
    """Enough of ibm_db to drive Db2Source without the C driver."""

    SQL_ATTR_AUTOCOMMIT = 1
    SQL_AUTOCOMMIT_ON = 1
    SQL_AUTOCOMMIT_OFF = 0

    def __init__(self, *, delete_error: str = "", rows: list[tuple] | None = None):
        self.delete_error = delete_error
        self.rows = list(rows or [])
        self.freed: list[object] = []
        self.rolled_back = 0
        self.autocommit_trace: list[int] = []

    def prepare(self, conn, sql):
        return ("stmt", sql)

    def execute(self, stmt, params=None):
        sql = stmt[1]
        if sql.startswith("DELETE") and self.delete_error:
            return False
        return True

    def fetch_tuple(self, stmt):
        return self.rows.pop(0) if self.rows else False

    def free_result(self, stmt):
        self.freed.append(stmt)

    def autocommit(self, conn, value):
        self.autocommit_trace.append(value)
        return True

    def num_rows(self, stmt):
        return 0

    def rollback(self, conn):
        self.rolled_back += 1
        return True

    def commit(self, conn):
        return True

    def stmt_errormsg(self, stmt=None):
        return self.delete_error or ""

    def conn_errormsg(self):
        return ""


def _db2(fake: _FakeIbmDb) -> Db2Source:
    src = Db2Source("h", "50000", "D24A", "u", "p")
    src._ibm_db = fake
    src._conn = object()
    return src


def test_db2_fk_violation_maps_to_purge_guard_not_source_error() -> None:
    fake = _FakeIbmDb(delete_error="SQL0532N delete prevented SQLCODE=-532, SQLSTATE=23504")
    src = _db2(fake)
    with pytest.raises(PurgeGuardError, match="foreign key violation"):
        src.purge_batch("ARCHIVE", "DOCARCH", "ARCH_KEY", ["K1", "K2"], "run-1", "t01-after", 1)
    assert fake.rolled_back == 1
    assert fake.autocommit_trace == [fake.SQL_AUTOCOMMIT_OFF, fake.SQL_AUTOCOMMIT_ON]


def test_db2_rows_frees_statement_when_consumer_stops_early() -> None:
    fake = _FakeIbmDb(rows=[("a",), ("b",), ("c",)])
    src = _db2(fake)
    it = src._rows("SELECT X FROM T")
    assert next(it) == ("a",)
    it.close()
    assert len(fake.freed) == 1


def test_db2_rows_frees_statement_on_normal_exhaustion() -> None:
    fake = _FakeIbmDb(rows=[("a",)])
    src = _db2(fake)
    assert list(src._rows("SELECT X FROM T")) == [("a",)]
    assert len(fake.freed) == 1


# --- PostgreSQL driver: conninfo carries keepalives and a statement deadline -------------------


def test_postgres_conninfo_sets_keepalives_and_statement_timeout() -> None:
    pytest.importorskip("psycopg")
    from ldm.drivers.postgresql import PostgresTarget

    info = PostgresTarget("h", 5432, "db", "u", "p").conninfo()
    assert "keepalives=1" in info
    assert "keepalives_idle=60" in info
    assert "statement_timeout=600000" in info
    info_off = PostgresTarget("h", 5432, "db", "u", "p", statement_timeout_ms=0).conninfo()
    assert "statement_timeout" not in info_off
