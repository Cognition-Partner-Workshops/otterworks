from decimal import Decimal
import json

import pytest

from finance_nb.queries import extract_queries as queries
from contract.warehouse import (ROOT, DatabricksWarehouse, SnowflakeWarehouse, canonical_rows,
                                load_baseline, target)

QUERIES = queries()


@pytest.fixture
def warehouse():
    client = target(QUERIES)
    if isinstance(client, SnowflakeWarehouse) and not all(client.credentials.values()):
        pytest.skip("Snowflake environment not configured")
    if isinstance(client, DatabricksWarehouse) and not client.configured:
        pytest.skip("Databricks environment not configured (DATABRICKS_HOST/TOKEN/WAREHOUSE_ID)")
    return client


def sums(rows, columns):
    return {column: str(sum((Decimal(str(row[column])) for row in rows), Decimal("0")))
            for column in columns}


@pytest.mark.parametrize("name", sorted(QUERIES))
def test_query_matches_recorded_contract(name, warehouse):
    rows = warehouse.query(QUERIES[name])
    expected = json.loads((ROOT / "expected" / f"{name}.json").read_text())
    assert len(rows) == expected["row_count"]
    assert len(rows) > 0
    assert [str(row[expected["key_column"]]).strip() for row in rows] == expected["keys"]
    if isinstance(warehouse, DatabricksWarehouse):
        # Live data is the dbx_d1111_before baseline, not the 800-row fixture behind the
        # expected sums: values must equal the old read path on the same data instead.
        old = load_baseline(name)
        assert sums(rows, expected["sums"]) == sums(old, expected["sums"])
        assert canonical_rows(rows) == canonical_rows(old)
        return
    for column, amount in expected["sums"].items():
        assert sum((Decimal(str(row[column])) for row in rows), Decimal("0")) == Decimal(amount)
