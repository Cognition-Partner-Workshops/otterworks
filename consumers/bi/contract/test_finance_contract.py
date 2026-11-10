from decimal import Decimal
import json
import os

import pytest

from semantic import queries
from contract.warehouse import ROOT, SnowflakeWarehouse, target

QUERIES = queries()
BASELINE = {
    name: (ROOT / "queries" / "teradata" / f"{name}.sql").read_text().strip()
    for name in QUERIES
}


@pytest.fixture
def warehouse():
    client = target(BASELINE)
    if isinstance(client, SnowflakeWarehouse) and not all(client.credentials.values()):
        pytest.skip("Snowflake environment not configured")
    yield client
    if isinstance(client, SnowflakeWarehouse):
        client.close()


@pytest.mark.parametrize("name", sorted(QUERIES))
def test_query_matches_recorded_contract(name, warehouse):
    if isinstance(warehouse, SnowflakeWarehouse):
        pytest.skip("exact seed assertions apply to replay/emulator targets")
    rows = warehouse.query(BASELINE[name])
    expected = json.loads((ROOT / "expected" / f"{name}.json").read_text())
    assert len(rows) == expected["row_count"]
    assert len(rows) > 0
    for column, amount in expected["sums"].items():
        assert sum((Decimal(str(row[column])) for row in rows), Decimal("0")) == Decimal(amount)
    assert [str(row[expected["key_column"]]).strip() for row in rows] == expected["keys"]


def test_snowflake_semantic_contract(warehouse):
    if not isinstance(warehouse, SnowflakeWarehouse):
        pytest.skip("live Snowflake assertions only")
    tag = warehouse.query("SELECT CURRENT_QUERY_TAG() AS QUERY_TAG", "session_query_tag")
    assert tag == [{"QUERY_TAG": warehouse.QUERY_TAG}]
    results = {}
    for name, sql in QUERIES.items():
        rows = warehouse.query(sql, name)
        recorded = json.loads((ROOT / "recorded" / "teradata" / f"{name}.json").read_text())
        assert warehouse.columns == recorded["columns"], name
        assert rows, name
        results[name] = rows
        if name in {"invoices", "invoice_revenue", "payments"}:
            assert [str(row["LABEL"]).strip() for row in rows] == [
                str(row[0]).strip() for row in recorded["rows"]
            ], name
        elif name == "gl_journal":
            assert {str(row[0]) for row in recorded["rows"]} <= {
                str(row["LABEL"]) for row in rows
            }
            assert all(Decimal(str(row["AMOUNT"])) == Decimal("0.00") for row in rows)
        else:
            assert 1 <= len(rows) <= 100
            assert all(Decimal(str(row["OVERDUE_BALANCE"])) > 0 for row in rows)
            assert all(row["ACCOUNT_NO"].startswith("ACC-") for row in rows)
            assert rows == sorted(rows, key=lambda row: (
                -Decimal(str(row["OVERDUE_BALANCE"])), row["ACCOUNT_NO"]
            ))
    assert {row["LABEL"]: row["AMOUNT"] for row in results["invoices"]} == {
        row["LABEL"]: row["AMOUNT"] for row in results["invoice_revenue"]
    }
    duplicates = warehouse.query(
        "SELECT UPPER(ACCOUNT_NUMBER) AS ACCOUNT_KEY "
        "FROM SFX_D1110_AFTER.COMPAT.ACCOUNT "
        "GROUP BY UPPER(ACCOUNT_NUMBER) "
        "HAVING COUNT(DISTINCT ACCOUNT_NUMBER) > 1",
        "account_case_duplicates",
    )
    assert duplicates == []
