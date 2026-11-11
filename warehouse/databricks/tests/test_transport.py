from unittest.mock import patch

import pytest

from warehouse.databricks.baseline import delta_type, literal
from warehouse.databricks.sql import Warehouse, identifier


def client():
    return Warehouse(host="https://test.cloud.databricks.com", token="test", warehouse_id="test",
                     act="prove", run="dbx-d1111")


def test_tagged_live_transport_collects_all_chunks():
    warehouse = client()
    responses = [{"statement_id": "s1", "status": {"state": "SUCCEEDED"},
                  "manifest": {"schema": {"columns": [{"name": "id"}]}},
                  "result": {"data_array": [["1"]],
                             "next_chunk_internal_link": "/api/2.0/sql/statements/s1/result/chunks/1"}},
                 {"data_array": [["2"]]}]
    with patch.object(warehouse, "_request", side_effect=responses) as request:
        result = warehouse.execute("SELECT id FROM x", step="count")
    assert result["rows"] == [["1"], ["2"]]
    statement = request.call_args_list[0].args[1]["statement"]
    assert statement.startswith("/* run=dbx-d1111 act=prove step=count consumer=platform */")


def test_truncation_cannot_be_reported_as_parity():
    with patch.object(Warehouse, "_request", return_value={"statement_id": "s1",
                      "status": {"state": "SUCCEEDED"}, "manifest": {"truncated": True}}):
        with pytest.raises(RuntimeError, match="truncated"):
            client().execute("SELECT * FROM x", step="hash")


def test_type_and_literal_preserve_decimal_null_and_padding():
    assert delta_type("numeric(14,2)") == "DECIMAL(14,2)"
    assert delta_type("character(12)") == "STRING"
    assert literal("USD   ") == "'USD   '"
    assert literal(None) == "NULL"
    with pytest.raises(ValueError):
        delta_type("jsonb")
    with pytest.raises(ValueError):
        identifier("table; DROP TABLE x")


def test_credential_transport_rejects_redirects_and_foreign_origins():
    from warehouse.databricks.sql import NoRedirect

    with pytest.raises(RuntimeError, match="redirects"):
        NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://example.invalid")
    with pytest.raises(ValueError, match="workspace origin"):
        Warehouse(host="https://example.invalid", token="test", warehouse_id="test", act="prove")
