from datetime import date, timedelta
from decimal import Decimal
import json
import os
import re

import pytest

from finance_nb.queries import extract_queries as queries
from contract.warehouse import ROOT, TERADATA_BASELINE, SnowflakeWarehouse, target

QUERIES = queries()
LIVE = os.getenv("WAREHOUSE_CONTRACT_TARGET", "teradata-emulator") == "snowflake"
MONTH_KEYED = {"revenue", "dso", "collections"}


def fixture(kind, name):
    data = json.loads((ROOT / kind / (f"teradata/{name}.json" if kind == "recorded" else f"{name}.json")).read_text())
    if kind == "recorded":
        return data["columns"], [dict(zip(data["columns"], row, strict=True)) for row in data["rows"]]
    return data


@pytest.fixture(scope="module")
def warehouse():
    client = target(QUERIES)
    if isinstance(client, SnowflakeWarehouse) and not client.configured:
        pytest.skip("Snowflake environment not configured")
    yield client
    client.close()


def test_teradata_baseline_covers_every_notebook_query():
    assert set(TERADATA_BASELINE) == set(QUERIES)


@pytest.mark.skipif(LIVE, reason="Teradata baseline targets only")
@pytest.mark.parametrize("name", sorted(QUERIES))
def test_query_matches_recorded_contract(name, warehouse):
    rows = warehouse.query(name)
    expected = fixture("expected", name)
    assert len(rows) == expected["row_count"]
    assert len(rows) > 0
    for column, amount in expected["sums"].items():
        assert sum((Decimal(str(row[column])) for row in rows), Decimal("0")) == Decimal(amount)
    assert [str(row[expected["key_column"]]).strip() for row in rows] == expected["keys"]


@pytest.mark.skipif(not LIVE, reason="WAREHOUSE_CONTRACT_TARGET is not snowflake")
def test_snowflake_session_is_tagged_on_parity_warehouse(warehouse):
    assert warehouse.session() == {
        "DATABASE_NAME": SnowflakeWarehouse.DATABASE,
        "SCHEMA_NAME": SnowflakeWarehouse.SCHEMA,
        "WAREHOUSE_NAME": "SFX_D1110_PARITY_WH",
        "QUERY_TAG": '{"run":"sfx-d1110","act":"consumers","consumer":"finance-notebook"}',
    }


@pytest.mark.skipif(not LIVE, reason="WAREHOUSE_CONTRACT_TARGET is not snowflake")
@pytest.mark.parametrize("name", sorted(QUERIES))
def test_snowflake_matches_recorded_contract(name, warehouse):
    rows = warehouse.query(name)
    print(f"snowflake query_id {name}={warehouse.query_ids[name]} rows={len(rows)}")
    columns, recorded = fixture("recorded", name)
    expected = fixture("expected", name)
    assert rows and list(rows[0]) == columns
    assert len(rows) == expected["row_count"]
    for column in expected["sums"]:
        assert all(isinstance(row[column], Decimal) for row in rows)
    if name in MONTH_KEYED:
        assert [row["MONTH_LABEL"] for row in rows] == expected["keys"]
    CHECKS[name](rows, recorded)


def check_revenue(rows, recorded):
    assert all(row["REVENUE"] > 0 for row in rows)


def check_dso(rows, recorded):
    assert all(row["DSO"] >= 0 for row in rows) == all(Decimal(r["DSO"]) >= 0 for r in recorded)


def check_collections(rows, recorded):
    for row, baseline in zip(rows, recorded, strict=True):
        for column in ("BILLED", "COLLECTED"):
            assert (row[column] == 0) == (Decimal(baseline[column]) == 0), (row, baseline)


def check_overdue(rows, recorded):
    cutoff = date.today() - timedelta(days=30)
    balances = [row["OVERDUE_BALANCE"] for row in rows]
    assert all(amount > 0 for amount in balances) and balances == sorted(balances, reverse=True)
    for row in rows:
        assert re.fullmatch(r"ACC-9\d{9}", row["ACCOUNT_NO"])
        assert isinstance(row["OLDEST_DUE_DATE"], date)
        assert date(2020, 1, 31) <= row["OLDEST_DUE_DATE"] < cutoff
    baseline = {r["ACCOUNT_NO"]: r for r in recorded}
    shared = [row for row in rows if row["ACCOUNT_NO"] in baseline]
    assert shared
    for row in shared:
        assert row["CUSTOMER_NAME"] == baseline[row["ACCOUNT_NO"]]["CUSTOMER_NAME"]
        assert row["OLDEST_DUE_DATE"].isoformat() == baseline[row["ACCOUNT_NO"]]["OLDEST_DUE_DATE"]


CHECKS = {"revenue": check_revenue, "dso": check_dso, "collections": check_collections, "overdue": check_overdue}
