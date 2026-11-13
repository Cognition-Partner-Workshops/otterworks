import json
from datetime import datetime
from decimal import Decimal

import duckdb
import pytest

from parity.__main__ import run
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
    ("UPDATE ledger SET amount=amount + CASE WHEN id=1 THEN 0.01 ELSE -0.01 END", "keyed_row_hash"),
])
def test_differences(databases, tmp_path, sql, failed):
    with duckdb.connect(str(databases[1])) as conn:
        conn.execute(sql)
    code, obj = reconcile(databases, tmp_path)
    assert code == 1
    assert obj["status"] == "red"
    assert not obj["checks"][failed]
    assert not obj["checks"]["samples"]
    if "CASE" in sql:
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
