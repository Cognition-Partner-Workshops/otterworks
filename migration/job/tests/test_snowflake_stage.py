"""Snowflake LOAD path against a fake connector: internal stage (PUT, the default) and external S3 stage
(target.archive.external_stage), both through the same COPY INTO ... FROM @STG.LDM_STAGE/<run_id>/<table>/ and the
same reject bisection."""

from __future__ import annotations

import re
import types
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from ldm.config import load_manifest
from ldm.context import build_table_specs
from ldm.convert import convert_record, encode_record
from ldm.drivers.base import StagedRow
from ldm.drivers.factory import target_spec
from ldm.drivers.snowflake import SnowflakeArchive
from ldm.errors import ConfigError

from .conftest import docarch_row, make_manifest_tree

DB = "OTTERWORKS_LDM_ZZS"
BAD_KEYS = {"K03", "K11"}


class _SfError(Exception):
    def __init__(self, msg: str):
        super().__init__(msg)
        self.sqlstate, self.errno, self.raw_msg = "22018", 100038, msg


class _Cursor:
    def __init__(self, conn: _Conn):
        self.conn, self.rowcount, self._rows = conn, 0, []

    def execute(self, sql: str, params: list[object] | None = None) -> None:
        self.conn.sql.append(sql)
        self._rows = self.conn.answer(sql)
        self.rowcount = len(self._rows)

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._rows

    def close(self) -> None:
        pass


class _Conn:
    """Records every statement; PUT and S3 uploads land in `files`, COPY INTO reads them back and fails like
    Snowflake's ABORT_STATEMENT when a batch carries one of BAD_KEYS."""

    def __init__(self, stage_url: str):
        self.sql: list[str] = []
        self.stage_url = stage_url
        self.files: dict[str, list[str]] = {}  # stage-relative path -> SOURCE_KEYs
        self.rejected = 0

    def cursor(self) -> _Cursor:
        return _Cursor(self)

    def close(self) -> None:
        pass

    def answer(self, sql: str) -> list[tuple[object, ...]]:
        if sql.startswith("DESC STAGE"):
            return [
                ("STAGE_LOCATION", "URL", "String", f'["{self.stage_url}"]' if self.stage_url else "", ""),
                ("STAGE_LOCATION", "AWS_ACCESS_POINT_ARN", "String", "", ""),
            ]
        if sql.startswith("PUT"):
            m = re.match(r"PUT 'file://(.+?)' '@[A-Z0-9_]+\.STG\.LDM_STAGE/(.+?)'", sql)
            assert m, sql
            local = Path(m.group(1))
            self.files[f"{m.group(2)}/{local.name}"] = _keys(local)
            return [(local.name, local.name, 1, 1, "NONE", "NONE", "UPLOADED", "")]
        if sql.startswith("COPY INTO"):
            m = re.search(r"FROM '@[A-Z0-9_]+\.STG\.LDM_STAGE/(.+?)/' FILES = \('(.+?)'\)", sql)
            assert m, sql
            path = f"{m.group(1)}/{m.group(2)}"
            keys = self.files[path]
            if BAD_KEYS & set(keys):
                self.rejected += 1
                raise _SfError(f"Numeric value 'x' is not recognized  File '{path}'")
            del self.files[path]  # PURGE = TRUE
            return [(path, "LOADED", len(keys), len(keys), 1, 0, None)]
        return []


class _S3:
    def __init__(self, conn: _Conn):
        self.conn, self.objects, self.deleted = conn, {}, []

    def upload_file(self, local: str, bucket: str, key: str) -> None:
        self.objects[(bucket, key)] = _keys(Path(local))
        prefix = self.conn.stage_url.removeprefix(f"s3://{bucket}/")
        assert key.startswith(prefix), key
        self.conn.files[key.removeprefix(prefix)] = self.objects[(bucket, key)]

    def delete_object(self, Bucket: str, Key: str) -> None:  # noqa: N803 - boto3's keyword names
        self.deleted.append((Bucket, Key))
        del self.conn.files[Key.removeprefix(self.conn.stage_url.removeprefix(f"s3://{Bucket}/"))]


def _keys(parquet: Path) -> list[str]:
    return [k.strip() for k in pq.read_table(parquet, columns=["SOURCE_KEY"]).column("SOURCE_KEY").to_pylist()]


def _archive(tmp_path: Path, *, external: bool, stage_url: str) -> tuple[SnowflakeArchive, _Conn, _S3]:
    base = make_manifest_tree(tmp_path, "zzs", snowflake_target=True)
    ts = build_table_specs(load_manifest(base, "zzs-after"))["DOCARCH"]
    a = SnowflakeArchive("ORG-ACCT", "svc", "tok", "LDM_JOB_ZZS", "LDM_WH", DB, external_stage=external)
    conn = _Conn(stage_url)
    s3 = _S3(conn)
    a._conn, a._s3 = conn, s3
    a._sf = types.SimpleNamespace(errors=types.SimpleNamespace(Error=_SfError))  # type: ignore[assignment]
    a.register_table("DOCARCH", ts.config.key_columns, ts.config.hash_columns, ts.columns)
    a.test_specs = ts  # type: ignore[attr-defined]
    return a, conn, s3


def _rows(a: SnowflakeArchive, n: int) -> list[StagedRow]:
    ts = a.test_specs  # type: ignore[attr-defined]
    out = []
    for i in range(n):
        raw = encode_record(docarch_row(f"K{i:02d}", "FIN7", "2016-03-01-10.15.30.123456789012"), ts.columns, 256)
        conv = convert_record(raw, ts.columns)
        assert conv.ok
        out.append(StagedRow("DOCARCH", conv.source_key, 1, raw, conv.values))
    return out


def _copies(conn: _Conn) -> list[str]:
    return [s for s in conn.sql if s.startswith("COPY INTO")]


@pytest.mark.parametrize("external", [False, True], ids=["internal-stage", "external-stage"])
def test_load_copies_from_stage_run_table_dir_and_bisects_rejects(tmp_path: Path, external: bool) -> None:
    a, conn, s3 = _archive(tmp_path, external=external, stage_url="s3://bkt/zzs-after/")
    failures = a.insert_staging("run-1", "zzs-after", "DOCARCH", _rows(a, 16))

    assert sorted(f.source_key.strip() for f in failures) == sorted(BAD_KEYS)
    assert all(f.sqlstate == "22018" for f in failures)
    copies = _copies(conn)
    assert copies and all(
        f"COPY INTO {DB}.STG.DOCARCH FROM '@{DB}.STG.LDM_STAGE/run-1/DOCARCH/' FILES = ('zzs-after-" in c
        for c in copies
    )
    assert all("PURGE = TRUE" in c and "ON_ERROR = ABORT_STATEMENT" in c for c in copies)
    # 16 rows with two bad ones split as 16 -> 8+8 -> 4+4+4+4 -> ... -> single-row failures
    assert len(copies) == 1 + 2 + 4 + 4 + 4
    puts = [s for s in conn.sql if s.startswith("PUT")]
    if external:
        assert not puts, "external stage: nothing is PUT through the Snowflake client"
        assert conn.sql[0] == f"DESC STAGE {DB}.STG.LDM_STAGE" and conn.sql.count(conn.sql[0]) == 1
        assert s3.objects and all(b == "bkt" and k.startswith("zzs-after/run-1/DOCARCH/") for b, k in s3.objects)
        # loaded batches are purged by COPY, every rejected batch is deleted again: nothing strays in the prefix
        assert len(s3.deleted) == conn.rejected > 0 and conn.files == {}
        assert {k for _, k in s3.deleted} <= {k for _, k in s3.objects}
    else:
        assert len(puts) == len(copies) and not s3.objects and not s3.deleted
        assert not any(s.startswith("DESC STAGE") for s in conn.sql)
        assert all(f"'@{DB}.STG.LDM_STAGE/run-1/DOCARCH'" in p for p in puts)
        assert len(conn.files) == conn.rejected > 0  # unchanged default: rejected batches stay on the internal stage


def test_external_stage_rejects_an_internal_stage(tmp_path: Path) -> None:
    a, _, _ = _archive(tmp_path, external=True, stage_url="")
    with pytest.raises(ConfigError, match="not an external S3 stage"):
        a.insert_staging("run-1", "zzs-after", "DOCARCH", _rows(a, 1))


def test_external_location_normalises_prefix(tmp_path: Path) -> None:
    a, _, _ = _archive(tmp_path, external=True, stage_url="s3://bkt/zzs-after")
    assert a.external_location() == ("bkt", "zzs-after/")


PG = {"PG_HOST": "h", "PG_PORT": "5432", "PG_DATABASE": "d", "PG_USER": "u", "PG_PASSWORD": "p"}
SF = {
    "SNOWFLAKE_ACCOUNT": "ORG-ACCT",
    "SNOWFLAKE_USER": "svc",
    "SNOWFLAKE_PAT": "tok",
    "SNOWFLAKE_ROLE": "LDM_JOB",
    "SNOWFLAKE_WAREHOUSE": "LDM_WH",
    "SNOWFLAKE_DATABASE": DB,
}


@pytest.mark.parametrize("external", [False, True])
def test_manifest_external_stage_flag_reaches_the_driver(tmp_path: Path, external: bool) -> None:
    base = make_manifest_tree(tmp_path, "zzf", snowflake_target=True, external_stage=external)
    loaded = load_manifest(base, "zzf-after")
    assert loaded.manifest.target.archive is not None
    assert loaded.manifest.target.archive.external_stage is external
    spec = target_spec(loaded, {**PG, **SF, "AWS_REGION": "us-east-1"})
    archive = spec.kwargs["archive"]
    assert isinstance(archive, dict) and archive["external_stage"] is external and archive["s3_region"] == "us-east-1"
    opened = spec.open().archive  # type: ignore[attr-defined]
    assert opened.external_stage is external and opened.stage == "STG.LDM_STAGE"


def test_repo_s30_after_manifest_loads_through_the_external_stage() -> None:
    from .conftest import REPO_ROOT

    loaded = load_manifest(REPO_ROOT / "migration" / "manifest.yaml", "s30-after")
    assert loaded.manifest.target.archive is not None and loaded.manifest.target.archive.external_stage is True
