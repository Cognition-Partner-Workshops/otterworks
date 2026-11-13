import json
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import duckdb
import oracledb
import pyarrow as pa
import pytest

from loader.common import token_name
from loader.frozen import arrow_type, extract, load_duckdb, validate
from loader.snowflake import inventory, load, sql_type, teardown


def column(name, kind, precision=0, scale=-127):
    return SimpleNamespace(name=name, type_code=kind, precision=precision, scale=scale)


@pytest.fixture
def frozen(tmp_path):
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.description = [column("ID", oracledb.DB_TYPE_NUMBER), column("AMOUNT", oracledb.DB_TYPE_NUMBER, 14, 4),
                          column("AGENT", oracledb.DB_TYPE_VARCHAR), column("POSTED", oracledb.DB_TYPE_DATE)]
    cursor.fetchall.return_value = [(Decimal(1), Decimal("1.1234"), None, datetime(2025, 6, 15, 14, 30)),
                                   (Decimal(2), Decimal("2.5678"), "", datetime(2025, 6, 16))]
    path = tmp_path / "frozen"
    extract(conn, ["LEDGER"], path, "run42")
    assert cursor.execute.call_args_list[0].args == ("SET TRANSACTION READ ONLY",)
    conn.rollback.assert_called_once()
    return path / "manifest.json"


def test_duckdb_round_trip(frozen, tmp_path):
    manifest = validate(frozen)
    path = load_duckdb(frozen, tmp_path / "loaded", "run42")
    with duckdb.connect(str(path)) as conn:
        rows = conn.execute('SELECT * FROM "LEDGER" ORDER BY "ID"').fetchall()
        assert rows[0][1] == Decimal("1.1234")
        assert rows[0][2] is None and rows[1][2] == ""
        assert rows[0][3].hour == 14
        comment = conn.execute("SELECT comment FROM duckdb_tables() WHERE table_name='LEDGER'").fetchone()[0]
        assert "run42" in comment and manifest["expires_at"] in comment
    with pytest.raises(FileExistsError):
        load_duckdb(frozen, tmp_path / "loaded", "run42")
    with pytest.raises(ValueError, match="token differs"):
        load_duckdb(frozen, tmp_path / "other", "run43")


def test_corruption_rejected(frozen):
    data = json.loads(frozen.read_text())
    (frozen.parent / data["objects"][0]["file"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        validate(frozen)


def test_manifest_path_rejected(frozen):
    data = json.loads(frozen.read_text())
    data["objects"][0]["file"] = "../outside.parquet"
    frozen.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="inside frozen"):
        validate(frozen)


def test_empty_extraction(tmp_path):
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.description = [column("ID", oracledb.DB_TYPE_NUMBER)]
    cursor.fetchall.return_value = []
    manifest = extract(conn, ["EMPTY_TABLE"], tmp_path / "empty", "run42")
    assert manifest["objects"][0]["rows"] == 0
    assert validate(tmp_path / "empty/manifest.json")["objects"][0]["rows"] == 0


def test_validation_and_types():
    for token in ("main", "x;DROP", "", "UPPER", "../run42"):
        with pytest.raises(ValueError):
            token_name(token)
    assert arrow_type(column("N", oracledb.DB_TYPE_NUMBER), [Decimal("12.1234")]) == pa.decimal128(6, 4)
    with pytest.raises(ValueError):
        arrow_type(column("N", oracledb.DB_TYPE_NUMBER), [Decimal("1e38"), Decimal("0.1")])
    with pytest.raises(ValueError):
        sql_type(pa.list_(pa.int64()))


def test_snowflake_load_sql_only(frozen, monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_RUN_PUBLIC_KEY", "YWJjZA==")
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (2,)
    assert load(conn, frozen, "run42") == "MIGRATION_RUN42_AFTER"
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert any("USE_LOGICAL_TYPE=TRUE" in s and "COPY INTO" in s for s in statements)
    assert any("PUT 'file://" in s for s in statements)
    assert any("WAREHOUSE_SIZE='XSMALL' AUTO_SUSPEND=60" in s for s in statements)
    assert any("CREDIT_QUOTA=1" in s and "_RM_E" in s for s in statements)
    assert all("COMMENT=" in s for s in statements if s.startswith(("CREATE DATABASE", "CREATE TABLE", "CREATE USER")))
    cursor.fetchone.return_value = (1,)
    with pytest.raises(ValueError, match="row count"):
        load(conn, frozen, "run42")


def test_snowflake_teardown_lists_residue():
    conn = MagicMock()
    before = [{"kind": "WAREHOUSES", "name": "MIGRATION_RUN42_AFTER_WH", "state": "STARTED"},
              {"kind": "RESOURCE MONITORS", "name": "MIGRATION_RUN42_AFTER_RM_E20260101"}]
    residue = [{"kind": "ROLES", "name": "OTHER", "comment": '{"token":"run42"}'}]
    with patch("loader.snowflake.inventory", side_effect=[before, residue]):
        report = teardown(conn, "run42")
    assert report["remaining"] == residue
    statements = [call.args[0] for call in conn.cursor.return_value.__enter__.return_value.execute.call_args_list]
    assert "SUSPEND" in statements[0]
    assert any('DROP DATABASE IF EXISTS "MIGRATION_RUN42_AFTER"' == s for s in statements)
    assert any("DROP RESOURCE MONITOR" in s for s in statements)
    with patch("loader.snowflake.inventory", side_effect=[[], []]):
        assert teardown(MagicMock(), "run42") == {"remaining": [], "errors": []}


def test_inventory_matches_comments_not_substrings():
    cursor = MagicMock()
    cursor.description = [("name",), ("comment",), ("state",)]
    cursor.fetchall.return_value = [("PREFIX_RUN42_AFTER", "", "SUSPENDED"),
                                   ("UNRELATED", '{"token":"run42"}', ""), ("PREFIX_RUN420_AFTER", "", "")]
    rows = inventory(cursor, "run42")
    assert rows and all("RUN420" not in row["name"] for row in rows)


def test_snowflake_jwt(monkeypatch):
    import sys
    from types import ModuleType

    from loader.snowflake import connect

    module = ModuleType("snowflake")
    module.connector = MagicMock()
    monkeypatch.setitem(sys.modules, "snowflake", module)
    monkeypatch.setitem(sys.modules, "snowflake.connector", module.connector)
    for key in ("ACCOUNT", "USER", "PRIVATE_KEY_PATH"):
        monkeypatch.setenv("SNOWFLAKE_" + key, "test-value")
    connect()
    kwargs = module.connector.connect.call_args.kwargs
    assert kwargs["authenticator"] == "SNOWFLAKE_JWT"
    assert "password" not in kwargs
