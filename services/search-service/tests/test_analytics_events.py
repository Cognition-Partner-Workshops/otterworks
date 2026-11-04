"""Tests for search event emission to the Analytics Service."""

from __future__ import annotations

import uuid
from dataclasses import replace
from unittest.mock import patch

import pytest
import requests

from app.config import AnalyticsConfig, AppConfig
from app.main import create_app
from app.models.search_result import SearchResponse
from app.services.analytics_events import build_search_performed_event


class _InlineExecutor:
    def submit(self, fn, *args, **kwargs):
        fn(*args, **kwargs)


@pytest.fixture()
def analytics_app(app_config: AppConfig, mock_meilisearch_client):
    config = replace(
        app_config, analytics=AnalyticsConfig(service_url="http://analytics.test")
    )
    with patch("app.services.meilisearch_client.meilisearch.Client") as mock_cls:
        mock_cls.return_value = mock_meilisearch_client
        flask_app = create_app(config)
        flask_app.config["TESTING"] = True
        flask_app.config["ANALYTICS_EMITTER"].executor = _InlineExecutor()
        yield flask_app


@pytest.fixture()
def analytics_client(analytics_app):
    return analytics_app.test_client()


def test_build_search_performed_event_with_empty_results():
    response = SearchResponse(results=[], total=0, page=1, page_size=20, query="no hits")

    event = build_search_performed_event("u-1", response)

    assert event["metadata"]["document_hit_ids"] == ""


def test_search_emits_search_performed_event(analytics_client, mock_meilisearch_client):
    mock_meilisearch_client.index.return_value.search.return_value = {
        "estimatedTotalHits": 2,
        "hits": [
            {"id": "doc-1", "type": "document", "title": "Q3 Budget"},
            {"id": "file-1", "type": "file", "name": "Q3 Budget.xlsx"},
        ],
    }

    with patch("app.services.analytics_events.requests.post") as post:
        response = analytics_client.get(
            "/api/v1/search/?q=Q3%20Budget", headers={"X-User-ID": "u-1"}
        )

    assert response.status_code == 200
    post.assert_called_once()
    args, kwargs = post.call_args
    assert args == ("http://analytics.test/api/v1/analytics/events",)
    assert kwargs["timeout"] == 2.0
    event = kwargs["json"]
    assert event["eventType"] == "search.performed"
    assert event["userId"] == "u-1"
    assert event["resourceType"] == "search"
    uuid.UUID(event["resourceId"])
    assert event["metadata"]["query"] == "Q3 Budget"
    assert event["metadata"]["result_count"] == str(response.get_json()["total"])
    assert event["metadata"]["document_hit_ids"] == "doc-1,doc-1"


def test_advanced_search_without_query_emits_wildcard_query(analytics_client):
    with patch("app.services.analytics_events.requests.post") as post:
        response = analytics_client.post(
            "/api/v1/search/advanced", json={}, headers={"X-User-ID": "u-1"}
        )

    assert response.status_code == 200
    post.assert_called_once()
    assert post.call_args.kwargs["json"]["metadata"]["query"] == "*"


def test_search_without_user_id_does_not_emit(analytics_client):
    with patch("app.services.analytics_events.requests.post") as post:
        response = analytics_client.get("/api/v1/search/?q=Q3%20Budget")

    assert response.status_code == 200
    post.assert_not_called()


def test_failed_searches_do_not_emit(analytics_app, analytics_client):
    with patch("app.services.analytics_events.requests.post") as post:
        bad_request = analytics_client.get(
            "/api/v1/search/?q=report&page=not-a-number", headers={"X-User-ID": "u-1"}
        )
        with patch.object(
            analytics_app.config["SEARCH_SERVICE"], "search", side_effect=RuntimeError
        ):
            server_error = analytics_client.get(
                "/api/v1/search/?q=report", headers={"X-User-ID": "u-1"}
            )

    assert bad_request.status_code == 400
    assert server_error.status_code == 500
    post.assert_not_called()


def test_analytics_connection_error_does_not_fail_search(analytics_client):
    with patch(
        "app.services.analytics_events.requests.post",
        side_effect=requests.ConnectionError("analytics unavailable"),
    ):
        response = analytics_client.get(
            "/api/v1/search/?q=report", headers={"X-User-ID": "u-1"}
        )

    assert response.status_code == 200


def test_default_app_does_not_emit(client):
    with patch("app.services.analytics_events.requests.post") as post:
        response = client.get("/api/v1/search/?q=report", headers={"X-User-ID": "u-1"})

    assert response.status_code == 200
    post.assert_not_called()
