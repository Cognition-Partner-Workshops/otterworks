"""Offline checks of the Snowflake RETENTION_PKG port (target/snowflake/200-220); the live half is
test_retention_parity.py."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

from ldm.stages.init import ddl_files

DDL_DIR = Path(__file__).resolve().parents[2] / "target" / "snowflake"
RETENTION_FILES = ("200_retention_udfs.sql", "210_retention_views.sql", "220_purge_intent.sql", "220_purge_intent.py")
DESTRUCTIVE = re.compile(r"\b(DELETE|TRUNCATE|DROP|MERGE|UPDATE)\b", re.IGNORECASE)


def _load_handler():
    spec = importlib.util.spec_from_file_location("purge_intent_handler", DDL_DIR / "220_purge_intent.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


handler = _load_handler()


class FakeResult:
    def __init__(self, rows: list[tuple]):
        self.rows = rows

    def collect(self) -> list[tuple]:
        return self.rows


class FakeSession:
    def __init__(self, prior: tuple = (0, None, None), unresolved: list[tuple] | None = None, recorded: int = 3):
        self.prior, self.unresolved, self.recorded = prior, unresolved or [], recorded
        self.statements: list[tuple[str, list]] = []

    def sql(self, sql: str, params: list | None = None) -> FakeResult:
        self.statements.append((sql, list(params or [])))
        if sql is handler.PRIOR_SQL:
            inserted = any(s is handler.INSERT_SQL for s, _ in self.statements)
            return FakeResult([(self.recorded, "2026-01-01", "2026-01-01")] if inserted else [self.prior])
        if sql is handler.UNRESOLVED_SQL:
            return FakeResult(self.unresolved)
        if sql is handler.INSERT_SQL:
            return FakeResult([(self.recorded * 2,)])
        raise AssertionError(f"unexpected statement: {sql[:60]}")


def _code_text(text: str) -> str:
    text = re.sub(r"--[^\n]*", "", text)
    return re.sub(r'"""[\s\S]*?"""', "", text)


def test_retention_ddl_applies_after_the_existing_files() -> None:
    names = [p.name for p in ddl_files(DDL_DIR)]
    assert names[-3:] == ["200_retention_udfs.sql", "210_retention_views.sql", "220_purge_intent.sql"]
    assert "220_purge_intent.py" not in names


def test_registered_procedure_body_is_the_handler_file() -> None:
    sql = (DDL_DIR / "220_purge_intent.sql").read_text()
    body = re.search(r"\nAS \$\$\n(.*)\$\$;", sql, re.DOTALL)
    assert body, "no $$ body in 220_purge_intent.sql"
    assert body.group(1) == (DDL_DIR / "220_purge_intent.py").read_text()
    assert "HANDLER = 'purge_intent'" in sql


@pytest.mark.parametrize("name", RETENTION_FILES)
def test_retention_port_never_deletes(name: str) -> None:
    code = _code_text((DDL_DIR / name).read_text())
    assert not DESTRUCTIVE.findall(code)


def test_purge_intent_requires_a_run_id() -> None:
    for run_id in (None, "", "   "):
        with pytest.raises(handler.PurgeIntentError, match=r"^-20001: RETENTION_PKG.PURGE_INTENT: run_id missing$"):
            handler.purge_intent(FakeSession(), run_id)


def test_purge_intent_records_children_then_parents_and_returns_parents() -> None:
    session = FakeSession(recorded=3)
    assert handler.purge_intent(session, "run-1", "2026-01-01", "ns") == 3
    inserts = [p for s, p in session.statements if s is handler.INSERT_SQL]
    assert inserts == [["2026-01-01", "2026-01-01", "ns", "ns", "run-1", "CLSD7Y", "2026-01-01", "2026-01-01"]]
    sequence = "ROW_NUMBER() OVER (PARTITION BY NAMESPACE ORDER BY RPAD(ARCH_KEY, 16), PHASE, CHILD_KEY)"
    assert sequence in handler.INSERT_SQL
    assert "0 AS PHASE" in handler.INSERT_SQL and "'FILEAUD'" in handler.INSERT_SQL


def test_purge_intent_rerun_is_idempotent_and_as_of_is_pinned() -> None:
    session = FakeSession(prior=(5, "2026-01-01", "2026-01-01"))
    assert handler.purge_intent(session, "run-1", "2026-01-01") == 5
    assert not any(s is handler.INSERT_SQL for s, _ in session.statements)
    with pytest.raises(handler.PurgeIntentError, match=r"^-20001: .* run run-1 already recorded as_of=2026-01-01$"):
        handler.purge_intent(session, "run-1", "2027-01-01")


@pytest.mark.parametrize(
    ("row", "message"),
    [
        (("ns", "L001", "CYCLE", None), r'^-20003: RETENTION_PKG: successor chain from "L001" does not terminate$'),
        (("ns", "DNG1", "UNKNOWN", "ZZZZ"), r'^-20002: RETENTION_PKG: unknown policy code "ZZZZ"$'),
        (("ns", "QQ", None, None), r'^-20002: RETENTION_PKG: unknown policy code "QQ  "$'),
    ],
)
def test_purge_intent_refuses_unresolvable_classes(row: tuple, message: str) -> None:
    session = FakeSession(unresolved=[row])
    with pytest.raises(handler.PurgeIntentError, match=message):
        handler.purge_intent(session, "run-1")
    assert not any(s is handler.INSERT_SQL for s, _ in session.statements)
