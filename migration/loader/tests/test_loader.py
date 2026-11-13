import json
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import duckdb
import oracledb
import pyarrow as pa
import pytest

from loader.__main__ import main
from loader.common import identifier, literal, token_name
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


def test_sql_encoding():
    assert identifier('PUBLIC.LEDGER') == '"PUBLIC"."LEDGER"'
    for value in ('ledger;DROP TABLE x', 'ledger" --', '', 'a..b', 'a b', 'a\n--'):
        with pytest.raises(ValueError, match='identifier'):
            identifier(value)
    assert literal("a'b") == "'a''b'"
    assert literal("\\'") == "'\\\\'''"


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
    residue = [{"kind": "ROLES", "name": "OTHER", "comment": '{"token":"run42","prefix":"MIGRATION"}'}]
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


def test_teardown_isolates_prefix_and_preserves_order():
    conn = MagicMock()
    ours = [{"kind": "WAREHOUSES", "name": "ONE_RUN42_AFTER_WH", "state": "STARTED"},
            {"kind": "RESOURCE MONITORS", "name": "ONE_RUN42_AFTER_RM_E20260101"}]
    other = [{"kind": "WAREHOUSES", "name": "TWO_RUN42_AFTER_WH", "state": "STARTED"},
             {"kind": "RESOURCE MONITORS", "name": "TWO_RUN42_AFTER_RM_E20260101"},
             {"kind": "WAREHOUSES", "name": "ONE_RUN42_AFTER_EXTRA_RUN42_AFTER_WH", "state": "STARTED"},
             {"kind": "WAREHOUSES", "name": "ONE_RUN42_AFTERNO_WH", "state": "STARTED"}]
    with patch("loader.snowflake.inventory", side_effect=[ours + other, other]):
        assert teardown(conn, "run42", "ONE") == {"remaining": [], "errors": []}
    statements = [c.args[0] for c in conn.cursor.return_value.__enter__.return_value.execute.call_args_list]
    assert statements == [
        'ALTER WAREHOUSE "ONE_RUN42_AFTER_WH" SUSPEND',
        'DROP DATABASE IF EXISTS "ONE_RUN42_AFTER"',
        'DROP WAREHOUSE IF EXISTS "ONE_RUN42_AFTER_WH"',
        'DROP RESOURCE MONITOR IF EXISTS "ONE_RUN42_AFTER_RM_E20260101"',
        'DROP ROLE IF EXISTS "ONE_RUN42_AFTER_ROLE"',
        'DROP USER IF EXISTS "ONE_RUN42_AFTER_USER"',
    ]


def test_teardown_cli_reports_scoped_residue(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["loader", "teardown", "--token", "run42", "--prefix", "ONE"])
    residue = [
        {"kind": "ROLES", "name": "RENAMED", "comment": '{"token":"run42","prefix":"ONE"}'},
        {"kind": "OBJECTS IN ACCOUNT", "name": "LEDGER", "database_name": "ONE_RUN42_AFTER"},
        {"kind": "ROLES", "name": "TWO_RUN42_AFTER_ROLE"},
    ]
    with patch("loader.snowflake.connect", return_value=MagicMock()), \
            patch("loader.snowflake.inventory", side_effect=[[], residue]):
        assert main() == 1
    assert json.loads(capsys.readouterr().out)["remaining"] == residue[:2]


def test_service_user_defaults(frozen, monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_RUN_PUBLIC_KEY", "YWJjZA==")
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (2,)
    load(conn, frozen, "run42", "ONE")
    statement = next(c.args[0] for c in cursor.execute.call_args_list if c.args[0].startswith("CREATE USER"))
    assert 'DEFAULT_ROLE="ONE_RUN42_AFTER_ROLE"' in statement
    assert 'DEFAULT_WAREHOUSE="ONE_RUN42_AFTER_WH"' in statement


@pytest.mark.parametrize("failure", ["BEGIN", "COMMENT", "COMMIT"])
def test_failed_duckdb_load_can_retry(frozen, tmp_path, failure):
    real_connect = duckdb.connect

    def broken_connect(path):
        conn = real_connect(path)
        proxy = MagicMock()
        proxy.__enter__.return_value = proxy
        proxy.__exit__.side_effect = lambda *args: conn.close()

        def execute(sql, *args):
            if sql.startswith(failure):
                raise RuntimeError("Simulated load failure")
            return conn.execute(sql, *args)

        proxy.execute.side_effect = execute
        return proxy

    out = tmp_path / "loaded"
    with patch("loader.frozen.duckdb.connect", side_effect=broken_connect), \
            pytest.raises(RuntimeError, match="Simulated"):
        load_duckdb(frozen, out, "run42")
    assert list(out.iterdir()) == []
    path = load_duckdb(frozen, out, "run42")
    with real_connect(str(path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM LEDGER").fetchone()[0] == 2


@pytest.mark.parametrize("precision", [7, 8, 9])
def test_timestamp_precision_rejected(tmp_path, precision):
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.description = [column("POSTED", oracledb.DB_TYPE_TIMESTAMP, scale=precision)]
    cursor.fetchall.return_value = [(datetime(2025, 6, 15, 14, 30),)]
    out = tmp_path / "frozen"
    with pytest.raises(ValueError, match=rf"TIMESTAMP\({precision}\).*microsecond"):
        extract(conn, ["LEDGER"], out, "run42")
    assert not (out / "manifest.json").exists()
    assert arrow_type(column("POSTED", oracledb.DB_TYPE_TIMESTAMP, scale=6)) == pa.timestamp("us")
