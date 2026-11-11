from decimal import Decimal
import json

import pytest

from semantic import DATABRICKS, queries
from contract.warehouse import ROOT, DatabricksWarehouse, SnowflakeWarehouse, target, target_name

DATABRICKS_TARGET = target_name() == "databricks"
QUERIES = queries(DATABRICKS) if DATABRICKS_TARGET else queries()
# The Databricks target reads the live baseline (BUSINESS_DATE=20261109, 2000-row seed), so its
# expectations and old-path rows are the Teradata emulator's output on that same data.
EXPECTED = ROOT / "expected" / ("baseline" if DATABRICKS_TARGET else "")
OLD_PATH = ROOT / "recorded" / "teradata-baseline"


@pytest.fixture(scope="module")
def warehouse():
    _RESULTS.clear()
    client = target(QUERIES)
    if isinstance(client, SnowflakeWarehouse) and not all(client.credentials.values()):
        pytest.skip("Snowflake environment not configured")
    if isinstance(client, DatabricksWarehouse) and not client.configured():
        pytest.skip("Databricks target selected but DATABRICKS_HOST/TOKEN/WAREHOUSE_ID not set")
    return client


_RESULTS = {}


def run(warehouse, name):
    if name not in _RESULTS:
        if isinstance(warehouse, DatabricksWarehouse):
            _RESULTS[name] = warehouse.query(QUERIES[name], name)
        else:
            _RESULTS[name] = warehouse.query(QUERIES[name])
    return _RESULTS[name]


def canonical(value):
    return str(value).strip()


@pytest.mark.parametrize("name", sorted(QUERIES))
def test_query_matches_recorded_contract(name, warehouse):
    rows = run(warehouse, name)
    expected = json.loads((EXPECTED / f"{name}.json").read_text())
    assert len(rows) == expected["row_count"]
    assert len(rows) > 0
    for column, amount in expected["sums"].items():
        assert sum((Decimal(str(row[column])) for row in rows), Decimal("0")) == Decimal(amount)
    assert [str(row[expected["key_column"]]).strip() for row in rows] == expected["keys"]


@pytest.mark.parametrize("name", sorted(QUERIES))
def test_databricks_rows_equal_old_read_path(name, warehouse):
    if not isinstance(warehouse, DatabricksWarehouse):
        pytest.skip("old-path row comparison applies to the databricks target")
    old = json.loads((OLD_PATH / f"{name}.json").read_text())
    rows = run(warehouse, name)
    assert list(rows[0]) == old["columns"]
    assert [[canonical(v) for v in row.values()] for row in rows] == \
        [[canonical(v) for v in row] for row in old["rows"]]
