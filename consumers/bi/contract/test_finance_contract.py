from decimal import Decimal
import json

import pytest

from semantic import queries
from contract.warehouse import ROOT, SnowflakeWarehouse, target

QUERIES = queries()


@pytest.fixture
def warehouse():
    client = target(QUERIES)
    if isinstance(client, SnowflakeWarehouse) and not all(client.credentials.values()):
        pytest.skip("Snowflake environment not configured")
    return client


@pytest.mark.parametrize("name", sorted(QUERIES))
def test_query_matches_recorded_contract(name, warehouse):
    rows = warehouse.query(QUERIES[name])
    expected = json.loads((ROOT / "expected" / f"{name}.json").read_text())
    assert len(rows) == expected["row_count"]
    assert len(rows) > 0
    for column, amount in expected["sums"].items():
        assert sum((Decimal(str(row[column])) for row in rows), Decimal("0")) == Decimal(amount)
    assert [str(row[expected["key_column"]]).strip() for row in rows] == expected["keys"]
