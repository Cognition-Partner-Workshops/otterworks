from decimal import Decimal
from datetime import date
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from bridge import execute, json_value

BRIDGE = Path(__file__).resolve().parents[1] / "bridge.py"
QUERY = "SEL CUSTOMER_ID FROM SFX_BILLING.CUSTOMER_ACCOUNT WHERE STATUS_CD = 'Active' ORDER BY CUSTOMER_ID"


def test_live_and_case_sensitive_comparisons():
    live = execute(QUERY)
    assert len(live["rows"]) >= 12
    assert execute(QUERY, "snowflake-semantics")["rows"] == []
    upper = QUERY.replace("'Active'", "'ACTIVE'")
    assert execute(upper)["rows"] == live["rows"]
    assert execute(upper, "snowflake-semantics")["rows"] == live["rows"]


@pytest.mark.parametrize("from_file", [False, True])
def test_record_is_exact_live_json(tmp_path, from_file):
    record = tmp_path / "active.json"
    command = [sys.executable, str(BRIDGE), "--query", "active", "--record", str(record)]
    if from_file:
        sql_file = tmp_path / "active.sql"
        sql_file.write_text(QUERY)
        command.extend(["--sql-file", str(sql_file)])
    result = subprocess.run(
        command, input=None if from_file else QUERY, capture_output=True, text=True, check=True,
    )
    payload = json.loads(result.stdout)
    assert json.loads(record.read_text()) == payload
    assert payload == {"query": "active", **execute(QUERY)}


def test_empty_result_and_decimal_date_serialization():
    result = execute("SEL CAST(123.45 AS DECIMAL(10,2)) AS AMOUNT, DATE '2026-11-09' AS DAY")
    assert json.loads(json.dumps(result, default=json_value)) == {
        "columns": ["AMOUNT", "DAY"], "rows": [["123.45", "2026-11-09"]]
    }
    assert execute("SEL CUSTOMER_ID FROM SFX_BILLING.CUSTOMER_ACCOUNT WHERE CUSTOMER_ID = -1")["rows"] == []
    assert json_value(Decimal("0.10")) == "0.10"
    assert json_value(date(2026, 11, 9)) == "2026-11-09"


def test_query_error_and_missing_home_are_nonzero():
    result = subprocess.run([sys.executable, str(BRIDGE)], input="SEL no_such_column FROM SFX_BILLING.INVOICE_HDR",
                            capture_output=True, text=True)
    assert result.returncode != 0 and result.stdout == ""
    assert "warehouse query failed" in result.stderr
    env = dict(os.environ)
    env.pop("TD_EMULATOR_HOME", None)
    result = subprocess.run([sys.executable, str(BRIDGE)], input=QUERY, env=env,
                            capture_output=True, text=True)
    assert result.returncode != 0 and "TD_EMULATOR_HOME" in result.stderr


@pytest.mark.parametrize("sql", ["", "   "])
def test_empty_sql_is_rejected(sql):
    result = subprocess.run([sys.executable, str(BRIDGE)], input=sql, capture_output=True, text=True)
    assert result.returncode != 0 and "SQL input is empty" in result.stderr
