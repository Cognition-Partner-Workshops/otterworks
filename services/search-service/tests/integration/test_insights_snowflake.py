from __future__ import annotations

import json
import os
import time

import pytest

from app.config import AppConfig, AuthConfig, SnowflakeConfig
from app.main import create_app
from app.vendor import sf_attribution as attr

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("SFNFR_ACCOUNT") or not os.getenv("DOC_SEARCH_API_PRIVATE_KEY_FILE"),
        reason="Snowflake integration credentials are not configured",
    ),
]

ACCOUNT_ID = "00000000-0000-4000-8000-000000000101"
EMPTY_ACCOUNT_ID = "00000000-0000-4000-8000-000000000999"


@pytest.fixture(scope="module")
def integration_client():
    config = AppConfig(
        auth=AuthConfig(service_token="", require_auth=True),
        snowflake=SnowflakeConfig(
            account=os.environ["SFNFR_ACCOUNT"],
            private_key_file=os.environ["DOC_SEARCH_API_PRIVATE_KEY_FILE"],
            deployed_commit=os.environ.get("DEPLOYED_COMMIT", ""),
            query_phase="runtime",
        ),
    )
    app = create_app(config)
    app.config["TESTING"] = True
    return app.test_client()


def _request_empty_account(client):
    return client.get(
        f"/api/v1/insights/search/accounts/{EMPTY_ACCOUNT_ID}/top"
        "?type=term&window_end_date=2026-11-01",
        headers={"X-User-ID": EMPTY_ACCOUNT_ID},
    )


def test_unknown_account_round_trip_returns_404(integration_client):
    response = _request_empty_account(integration_client)
    assert response.status_code == 404
    assert response.get_json() == {"error": "no search window for this account"}


def test_runtime_query_is_visible_with_attribution_tag(integration_client):
    response = _request_empty_account(integration_client)
    assert response.status_code == 404

    import snowflake.connector

    endpoint = attr.Endpoint.from_csid("cs_doc_search_api_top_items", "doc_search_api")
    os.environ.pop("SNOWFLAKE_HOST", None)
    params = attr.connection_params(
        endpoint,
        account=os.environ["SFNFR_ACCOUNT"],
        private_key_file=os.environ["SFNFR_PRIVATE_KEY_FILE"],
        phase="dev",
        commit=os.environ["DEPLOYED_COMMIT"],
        run_id=attr.make_run_id("doc_search_api", "dev"),
        session_url=os.environ["SESSION_URL"],
        role=os.environ["SFNFR_ROLE"],
    )
    params["user"] = os.environ["SFNFR_USER"]
    connection = snowflake.connector.connect(**params)
    try:
        query = f"""select query_id, user_name, start_time, query_tag, query_text
          from table({attr.database_name("doc_search_api")}.information_schema.query_history_by_user(
              user_name => '{attr.service_user(endpoint.csid)}', result_limit => 100))
         where query_text ilike '%DOC_SEARCH_API%'
         order by start_time desc"""
        deadline = time.monotonic() + 60
        found = None
        while time.monotonic() < deadline:
            cursor = connection.cursor()
            try:
                cursor.execute(query)
                for row in cursor.fetchall():
                    tag = json.loads(row[3])
                    if (
                        tag.get("csid") == "cs_doc_search_api_top_items"
                        and tag.get("phase") == "runtime"
                        and tag.get("commit") == os.environ["DEPLOYED_COMMIT"]
                        and "session_url" not in tag
                    ):
                        found = row
                        break
            finally:
                cursor.close()
            if found:
                break
            time.sleep(3)
        assert found is not None, "runtime DOC_SEARCH_API query with expected attribution tag was not found"
        print(
            {
                "query_id": found[0],
                "user_name": found[1],
                "start_time": found[2],
                "query_tag": found[3],
            }
        )
    finally:
        connection.close()


def test_spec_account_term_and_document_rows(integration_client):
    term_response = integration_client.get(
        f"/api/v1/insights/search/accounts/{ACCOUNT_ID}/top"
        "?type=term&window_end_date=2026-11-01",
        headers={"X-User-ID": ACCOUNT_ID},
    )
    assert term_response.status_code == 200
    assert term_response.get_json() == {
        "window_end_date": "2026-11-01",
        "window_days": 28,
        "account_id": ACCOUNT_ID,
        "items": [
            {
                "rank": 1,
                "term": "q3 budget",
                "search_count": 3,
                "zero_result_count": 0,
                "last_searched_at": "2026-10-28T11:00:00Z",
            },
            {
                "rank": 2,
                "term": "roadmap",
                "search_count": 2,
                "zero_result_count": 2,
                "last_searched_at": "2026-10-30T15:30:00Z",
            },
            {
                "rank": 3,
                "term": "onboarding",
                "search_count": 1,
                "zero_result_count": 0,
                "last_searched_at": "2026-10-31T12:00:00Z",
            },
        ],
    }

    document_response = integration_client.get(
        f"/api/v1/insights/search/accounts/{ACCOUNT_ID}/top"
        "?type=document&window_end_date=2026-11-01",
        headers={"X-User-ID": ACCOUNT_ID},
    )
    assert document_response.status_code == 200
    assert document_response.get_json() == {
        "window_end_date": "2026-11-01",
        "window_days": 28,
        "account_id": ACCOUNT_ID,
        "items": [
            {
                "rank": 1,
                "document_id": "00000000-0000-4000-8000-000000000202",
                "document_title": "Onboarding Checklist",
                "search_count": 3,
                "zero_result_count": None,
                "last_searched_at": "2026-10-31T12:00:00Z",
            },
            {
                "rank": 2,
                "document_id": "00000000-0000-4000-8000-000000000201",
                "document_title": "Q3 Budget Plan",
                "search_count": 3,
                "zero_result_count": None,
                "last_searched_at": "2026-10-28T11:00:00Z",
            },
        ],
    }
