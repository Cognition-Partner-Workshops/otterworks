import json
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal

import duckdb
import pytest

from parity.__main__ import run
from parity.adapters import identifier
from parity.core import canonical, compare


@pytest.fixture
def databases(tmp_path):
    paths = [tmp_path / "left.db", tmp_path / "right.db"]
    for path in paths:
        conn = duckdb.connect(str(path))
        conn.execute("CREATE TABLE ledger(id INTEGER, amount DECIMAL(18,4), agent VARCHAR, posted TIMESTAMP)")
        conn.execute("INSERT INTO ledger VALUES (1, 10.1234, NULL, '2025-06-15 14:30:00')")
        conn.execute("INSERT INTO ledger VALUES (2, 20.5678, '', '2025-06-16 09:00:00')")
        conn.close()
    return paths


def reconcile(paths, tmp_path, **extra):
    spec = {"left_table": "ledger", "right_table": "ledger", "keys": ["id"],
            "compare": ["amount", "agent", "posted"], "sample_size": 2, **extra}
    code = run({"connections": {"left": {"path": str(paths[0])}, "right": {"path": str(paths[1])}},
                "objects": [spec]}, "duckdb", "duckdb", tmp_path / "report")
    report = json.loads((tmp_path / "report/parity.json").read_text())
    return code, report["objects"][0]


@pytest.mark.parametrize(("sql", "failed"), [
    ("UPDATE ledger SET amount=ROUND(amount,2)", "profiles"),
    ("UPDATE ledger SET agent='' WHERE agent IS NULL", "profiles"),
    ("UPDATE ledger SET posted=DATE_TRUNC('day',posted)", "keyed_row_hash"),
    ("INSERT INTO ledger SELECT * FROM ledger WHERE id=1", "row_count"),
])
def test_differences(databases, tmp_path, sql, failed):
    with duckdb.connect(str(databases[1])) as conn:
        conn.execute(sql)
    code, obj = reconcile(databases, tmp_path)
    assert code == 1
    assert obj["status"] == "red"
    assert not obj["checks"][failed]
    assert not obj["checks"]["samples"]


def test_per_row_and_total_rounding_with_equal_totals(databases, tmp_path):
    for index, path in enumerate(databases):
        with duckdb.connect(str(path)) as conn:
            conn.execute("DELETE FROM ledger")
            conn.execute("""
                INSERT INTO ledger(id, amount) VALUES
                (1, ROUND(10.01 * 0.5, 2)), (2, ROUND(10.01 * 0.5, 2)),
                (3, ROUND(10.00 * 0.3333, 2)), (4, ROUND(10.00 * 0.3333, 2)),
                (5, ROUND(10.00 * 0.3334, 2))
            """)
            if index == 1:
                conn.execute("UPDATE ledger SET amount=ROUND(10.01,2)-ROUND(10.01*0.5,2) WHERE id=2")
                conn.execute("UPDATE ledger SET amount=ROUND(10.00,2)-2*ROUND(10.00*0.3333,2) WHERE id=5")
    code, obj = reconcile(databases, tmp_path)
    assert code == 1 and obj["status"] == "red"
    assert not obj["checks"]["keyed_row_hash"] and not obj["checks"]["samples"]
    assert obj["left"]["profiles"]["amount"]["sum"] == obj["right"]["profiles"]["amount"]["sum"]


def test_equal_and_deterministic(databases, tmp_path):
    code, obj = reconcile(databases, tmp_path)
    assert code == 0 and obj["status"] == "green"
    assert obj["left"]["profiles"]["amount"]["max_numeric_scale"] == 4
    assert obj["left"]["profiles"]["agent"]["null"] == 1
    assert obj["left"]["profiles"]["agent"]["empty_string"] == 1
    assert (tmp_path / "report/parity.md").exists()
    with duckdb.connect(str(databases[1])) as conn:
        conn.execute("CREATE TABLE reordered AS SELECT * FROM ledger ORDER BY id DESC")
        conn.execute("DROP TABLE ledger")
        conn.execute("ALTER TABLE reordered RENAME TO ledger")
    assert reconcile(databases, tmp_path)[1]["right"] == obj["right"]


def test_amber_needs_question_and_owner(databases, tmp_path):
    with duckdb.connect(str(databases[1])) as conn:
        conn.execute("DELETE FROM ledger")
    assert reconcile(databases, tmp_path, open_question="Confirm allocation", owner="Finance")[0] == 0
    assert reconcile(databases, tmp_path, open_question="Confirm allocation")[0] == 1


def test_empty_and_invalid_objects(databases, tmp_path):
    for path in databases:
        with duckdb.connect(str(path)) as conn:
            conn.execute("DELETE FROM ledger")
    assert reconcile(databases, tmp_path)[1]["status"] == "green"
    assert reconcile(databases, tmp_path, right_table="absent", open_question="Review", owner="Data")[0] == 1


def test_canonical_values():
    assert canonical(None) != canonical("")
    assert canonical(Decimal("12345678901234567890.12345678"))[1] == "12345678901234567890.12345678"
    assert canonical(datetime(2025, 6, 15, 14, 30))[1] == "2025-06-15T14:30:00"
    assert canonical(Decimal("1.00")) == canonical(1)
    with pytest.raises(ValueError):
        compare({"left_table": "x", "keys": [], "compare": [], "sample_size": -1}, [], [])


def test_identifier_validation():
    assert identifier("PUBLIC.LEDGER") == '"PUBLIC"."LEDGER"'
    for value in ('ledger;DROP TABLE x', 'ledger" --', '', 'a..b', 'a b', 'a\n--'):
        with pytest.raises(ValueError, match="identifier"):
            identifier(value)


@pytest.mark.parametrize("side", ["left", "right"])
@pytest.mark.parametrize("error", [ConnectionError, ImportError])
def test_connection_failures_write_reports(tmp_path, monkeypatch, side, error):
    @contextmanager
    def connect(kind, settings):
        if settings.get("fail"):
            raise error("Unavailable adapter")
        yield object()

    monkeypatch.setattr("parity.__main__.connection", connect)
    config = {"connections": {"left": {}, "right": {}}, "objects": [
        {"name": "First", "left_table": "one"}, {"name": "Second", "left_table": "two"}]}
    config["connections"][side]["fail"] = True
    out = tmp_path / "report"
    assert run(config, "duckdb", "duckdb", out) == 1
    report = json.loads((out / "parity.json").read_text())
    assert report["summary"] == {"green": 0, "amber": 0, "red": 2}
    assert [obj["name"] for obj in report["objects"]] == ["First", "Second"]
    assert all(obj["error"] == error.__name__ for obj in report["objects"])
    assert error.__name__ in (out / "parity.md").read_text()
    config["objects"] = []
    assert run(config, "duckdb", "duckdb", out) == 1
    assert json.loads((out / "parity.json").read_text())["objects"] == []


def test_failed_object_uses_configured_name(databases, tmp_path):
    code, obj = reconcile(databases, tmp_path, name="Named ledger", right_table="absent")
    assert code == 1 and obj["name"] == "Named ledger" and obj["status"] == "red"
    assert obj["error"] == "CatalogException"
    assert "Named ledger" in (tmp_path / "report/parity.md").read_text()


@pytest.mark.parametrize(("values", "minimum", "maximum", "total"), [
    (["NaN", "1"], "1", "NaN", "NaN"),
    (["Infinity", "1"], "1", "Infinity", "Infinity"),
    (["-Infinity", "1"], "-Infinity", "1", "-Infinity"),
    (["Infinity", "-Infinity", "1"], "-Infinity", "Infinity", "NaN"),
    (["NaN", "Infinity", "-Infinity", "1"], "-Infinity", "NaN", "NaN"),
    (["NaN", "NaN"], "NaN", "NaN", "NaN"),
])
def test_nonfinite_numeric_profiles(databases, tmp_path, values, minimum, maximum, total):
    for path in databases:
        with duckdb.connect(str(path)) as conn:
            conn.execute("ALTER TABLE ledger ALTER COLUMN amount TYPE DOUBLE")
            conn.execute("DELETE FROM ledger")
            conn.executemany("INSERT INTO ledger(id,amount) VALUES (?,?)", list(enumerate(map(float, values))))
    code, obj = reconcile(databases, tmp_path)
    assert code == 0 and obj["status"] == "green"
    profile = obj["left"]["profiles"]["amount"]
    assert profile["min"] == ["number", minimum]
    assert profile["max"] == ["number", maximum]
    assert profile["sum"] == ["number", total]
