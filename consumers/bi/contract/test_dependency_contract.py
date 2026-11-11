"""Keep unmapped successful DBQL reads visible in the live contract."""
import pytest

from contract.dependencies import RED_REASON, inspect_users
from contract.warehouse import DatabricksWarehouse, target_name


def test_successful_dbql_users_dependencies_exist():
    if target_name() != "databricks":
        pytest.skip("users dependency check requires the live databricks target")
    warehouse = DatabricksWarehouse()
    if not warehouse.configured():
        pytest.skip("Databricks target selected but DATABRICKS_HOST/TOKEN/WAREHOUSE_ID not set")
    evidence = inspect_users(warehouse.transport)
    print(f"users dependency evidence: {evidence}")
    assert not evidence["missing"], f"{RED_REASON} Evidence: {evidence}"
