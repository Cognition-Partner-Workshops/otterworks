from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from unittest.mock import patch

import pytest

from app.config import AuthConfig, SnowflakeConfig
from app.main import create_app
from app.services.snowflake_pool import BackendUnavailable, PoolTimeout, QueryTimeout

ACCOUNT_ID = "00000000-0000-4000-8000-000000000101"
OTHER_ACCOUNT_ID = "00000000-0000-4000-8000-000000000102"
HEADERS = {"X-User-ID": ACCOUNT_ID}


def _rows():
    return [
        {
            "window_end_date": date(2026, 11, 1),
            "window_days": 28,
            "account_id": ACCOUNT_ID,
            "item_type": "term",
            "rank": 1,
            "term": "q3 budget",
            "document_id": None,
            "document_title": None,
            "search_count": 3,
            "zero_result_count": 0,
            "last_searched_at": datetime(2026, 10, 28, 11),
        },
        {
            "window_end_date": date(2026, 11, 1),
            "window_days": 28,
            "account_id": ACCOUNT_ID,
            "item_type": "term",
            "rank": 2,
            "term": "roadmap",
            "document_id": None,
            "document_title": None,
            "search_count": 2,
            "zero_result_count": 2,
            "last_searched_at": datetime(2026, 10, 30, 15, 30),
        },
        {
            "window_end_date": date(2026, 11, 1),
            "window_days": 28,
            "account_id": ACCOUNT_ID,
            "item_type": "term",
            "rank": 3,
            "term": "onboarding",
            "document_id": None,
            "document_title": None,
            "search_count": 1,
            "zero_result_count": 0,
            "last_searched_at": datetime(2026, 10, 31, 12),
        },
        {
            "window_end_date": date(2026, 11, 1),
            "window_days": 28,
            "account_id": ACCOUNT_ID,
            "item_type": "document",
            "rank": 1,
            "term": None,
            "document_id": "00000000-0000-4000-8000-000000000202",
            "document_title": "Onboarding Checklist",
            "search_count": 3,
            "zero_result_count": None,
            "last_searched_at": datetime(2026, 10, 31, 12),
        },
        {
            "window_end_date": date(2026, 11, 1),
            "window_days": 28,
            "account_id": ACCOUNT_ID,
            "item_type": "document",
            "rank": 2,
            "term": None,
            "document_id": "00000000-0000-4000-8000-000000000201",
            "document_title": "Q3 Budget Plan",
            "search_count": 3,
            "zero_result_count": None,
            "last_searched_at": datetime(2026, 10, 28, 11),
        },
    ]


class FakeInsightsRepository:
    def __init__(self):
        self.rows = _rows()
        self.error = None
        self.calls = []

    def top_items(self, account_id, window_end_date):
        self.calls.append((account_id, window_end_date))
        if self.error:
            raise self.error
        return self.rows


@pytest.fixture
def insights_app(app_config, mock_meilisearch_client):
    config = replace(
        app_config,
        auth=AuthConfig(service_token="insights-service-token", require_auth=True),
        snowflake=SnowflakeConfig(account="test-account"),
    )
    with patch("app.services.meilisearch_client.meilisearch.Client") as client_class:
        client_class.return_value = mock_meilisearch_client
        flask_app = create_app(config)
    flask_app.config["TESTING"] = True
    repository = FakeInsightsRepository()
    flask_app.config["INSIGHTS_REPOSITORY"] = repository
    flask_app.config["INSIGHTS_REPOSITORY_TEST_DOUBLE"] = repository
    return flask_app


@pytest.fixture
def insights_client(insights_app):
    return insights_app.test_client()


@pytest.fixture
def insights_repository(insights_app):
    return insights_app.config["INSIGHTS_REPOSITORY_TEST_DOUBLE"]


class TestInsightsContract:
    def test_term_response_has_exact_shape_and_latest_window_default(self, insights_client, insights_repository):
        response = insights_client.get(
            f"/api/v1/insights/search/accounts/{ACCOUNT_ID}/top?type=term",
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert response.get_json() == {
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
        assert insights_repository.calls == [(ACCOUNT_ID, None)]

    def test_document_response_has_exact_shape(self, insights_client):
        response = insights_client.get(
            f"/api/v1/insights/search/accounts/{ACCOUNT_ID}/top?type=document",
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert response.get_json() == {
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

    def test_limit_truncates_and_explicit_window_is_passed_through(
        self, insights_client, insights_repository
    ):
        response = insights_client.get(
            f"/api/v1/insights/search/accounts/{ACCOUNT_ID}/top"
            "?type=term&limit=2&window_end_date=2026-11-01",
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert [item["rank"] for item in response.get_json()["items"]] == [1, 2]
        assert insights_repository.calls == [(ACCOUNT_ID, date(2026, 11, 1))]

    @pytest.mark.parametrize(
        ("account_id", "query", "expected_error"),
        [
            (ACCOUNT_ID, "", "type must be term or document"),
            (ACCOUNT_ID, "?type=unknown", "type must be term or document"),
            (ACCOUNT_ID, "?type=term&limit=0", "limit must be an integer from 1 to 10"),
            (ACCOUNT_ID, "?type=term&limit=11", "limit must be an integer from 1 to 10"),
            (ACCOUNT_ID, "?type=term&limit=abc", "limit must be an integer from 1 to 10"),
            (ACCOUNT_ID, "?type=term&window_end_date=2026-1-01", "window_end_date must be YYYY-MM-DD"),
            ("not-a-uuid", "", "invalid account_id"),
        ],
    )
    def test_validation_errors(self, insights_client, account_id, query, expected_error):
        response = insights_client.get(
            f"/api/v1/insights/search/accounts/{account_id}/top{query}",
            headers=HEADERS,
        )
        assert response.status_code == 400
        assert response.get_json() == {"error": expected_error}

    def test_other_user_is_forbidden(self, insights_client):
        response = insights_client.get(
            f"/api/v1/insights/search/accounts/{ACCOUNT_ID}/top?type=term",
            headers={"X-User-ID": OTHER_ACCOUNT_ID},
        )
        assert response.status_code == 403
        assert response.get_json() == {"error": "forbidden"}

    def test_service_token_is_allowed(self, insights_client):
        response = insights_client.get(
            f"/api/v1/insights/search/accounts/{ACCOUNT_ID}/top?type=term",
            headers={"Authorization": "Bearer insights-service-token"},
        )
        assert response.status_code == 200

    def test_no_window_returns_404(self, insights_client, insights_repository):
        insights_repository.rows = None
        response = insights_client.get(
            f"/api/v1/insights/search/accounts/{ACCOUNT_ID}/top?type=term",
            headers=HEADERS,
        )
        assert response.status_code == 404
        assert response.get_json() == {"error": "no search window for this account"}

    def test_unconfigured_backend_returns_503(self, insights_client, insights_app):
        config = insights_app.config["APP_CONFIG"]
        insights_app.config["APP_CONFIG"] = replace(config, snowflake=SnowflakeConfig(account=""))
        response = insights_client.get(
            f"/api/v1/insights/search/accounts/{ACCOUNT_ID}/top?type=term",
            headers=HEADERS,
        )
        assert response.status_code == 503
        assert response.get_json() == {"error": "insights backend not configured"}

    @pytest.mark.parametrize("error", [PoolTimeout("busy"), BackendUnavailable("offline")])
    def test_unavailable_backend_returns_503(self, insights_client, insights_repository, error):
        insights_repository.error = error
        response = insights_client.get(
            f"/api/v1/insights/search/accounts/{ACCOUNT_ID}/top?type=term",
            headers=HEADERS,
        )
        assert response.status_code == 503
        assert response.get_json() == {"error": "insights backend unavailable"}

    def test_query_timeout_returns_504(self, insights_client, insights_repository):
        insights_repository.error = QueryTimeout("timeout")
        response = insights_client.get(
            f"/api/v1/insights/search/accounts/{ACCOUNT_ID}/top?type=term",
            headers=HEADERS,
        )
        assert response.status_code == 504
        assert response.get_json() == {"error": "insights query timed out"}

    def test_generic_error_returns_500(self, insights_client, insights_repository):
        insights_repository.error = RuntimeError("query failed")
        response = insights_client.get(
            f"/api/v1/insights/search/accounts/{ACCOUNT_ID}/top?type=term",
            headers=HEADERS,
        )
        assert response.status_code == 500
        assert response.get_json() == {"error": "insights query failed"}

    def test_existing_window_without_requested_type_returns_empty_items(
        self, insights_client, insights_repository
    ):
        insights_repository.rows = [row for row in insights_repository.rows if row["item_type"] == "document"]
        response = insights_client.get(
            f"/api/v1/insights/search/accounts/{ACCOUNT_ID}/top?type=term",
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert response.get_json()["items"] == []
