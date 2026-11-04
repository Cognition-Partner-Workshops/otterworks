"""Tests for search event emission to the Analytics Service."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import requests

from app.config import AnalyticsConfig, AppConfig
from app.main import create_app
from app.models.search_result import SearchResponse
from app.services.analytics_events import (
    ANALYTICS_EVENTS_DROPPED,
    AnalyticsEmitter,
    build_search_performed_event,
)


class _InlineExecutor:
    def submit(self, fn, *args, **kwargs):
        fn(*args, **kwargs)


class _HoldingExecutor:
    def __init__(self):
        self.submitted = []

    def submit(self, fn, *args, **kwargs):
        self.submitted.append((fn, args, kwargs))

    def run_all(self):
        submitted, self.submitted = self.submitted, []
        for fn, args, kwargs in submitted:
            fn(*args, **kwargs)


class _FailingExecutor:
    def submit(self, fn, *args, **kwargs):
        raise RuntimeError("executor is shut down")


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
    searched_at = datetime(2026, 10, 28, 11, 0, tzinfo=timezone.utc)

    event = build_search_performed_event("u-1", response, searched_at)

    assert event["metadata"]["document_hit_ids"] == ""
    assert event["metadata"]["searched_at"] == "2026-10-28T11:00:00.000Z"


def test_emitter_drops_when_backlog_is_full_and_recovers():
    executor = _HoldingExecutor()
    emitter = AnalyticsEmitter(
        AnalyticsConfig(service_url="http://analytics.test", max_pending=2),
        executor=executor,
    )
    response = SearchResponse(results=[], total=0, page=1, page_size=20, query="query")
    dropped_before = ANALYTICS_EVENTS_DROPPED._value.get()

    with patch("app.services.analytics_events.requests.post"):
        emitter.emit_search_performed("u-1", response)
        emitter.emit_search_performed("u-1", response)
        emitter.emit_search_performed("u-1", response)

        assert len(executor.submitted) == 2
        assert ANALYTICS_EVENTS_DROPPED._value.get() == dropped_before + 1

        executor.run_all()
        emitter.emit_search_performed("u-1", response)

    assert len(executor.submitted) == 1
    executor.run_all()


def test_timeouts_release_slots_for_each_event():
    emitter = AnalyticsEmitter(
        AnalyticsConfig(service_url="http://analytics.test", max_pending=2),
        executor=_InlineExecutor(),
    )
    response = SearchResponse(results=[], total=0, page=1, page_size=20, query="query")
    dropped_before = ANALYTICS_EVENTS_DROPPED._value.get()

    with patch(
        "app.services.analytics_events.requests.post",
        side_effect=requests.Timeout("analytics timed out"),
    ) as post:
        for _ in range(10):
            emitter.emit_search_performed("u-1", response)

    assert post.call_count == 10
    assert ANALYTICS_EVENTS_DROPPED._value.get() == dropped_before
    assert emitter._slots.acquire(blocking=False)
    assert emitter._slots.acquire(blocking=False)
    assert not emitter._slots.acquire(blocking=False)
    emitter._slots.release()
    emitter._slots.release()


def test_submit_error_releases_slot_without_raising():
    emitter = AnalyticsEmitter(
        AnalyticsConfig(service_url="http://analytics.test", max_pending=1),
        executor=_FailingExecutor(),
    )
    response = SearchResponse(results=[], total=0, page=1, page_size=20, query="query")

    emitter.emit_search_performed("u-1", response)
    emitter.executor = _InlineExecutor()

    with patch("app.services.analytics_events.requests.post") as post:
        emitter.emit_search_performed("u-1", response)

    post.assert_called_once()


def test_event_timestamp_is_captured_before_queued_send():
    executor = _HoldingExecutor()
    emitter = AnalyticsEmitter(
        AnalyticsConfig(service_url="http://analytics.test", max_pending=1),
        executor=executor,
    )
    response = SearchResponse(results=[], total=0, page=1, page_size=20, query="query")
    searched_at = datetime(2026, 10, 28, 11, 0, tzinfo=timezone.utc)
    send_time = datetime(2026, 10, 28, 11, 5, tzinfo=timezone.utc)

    with (
        patch("app.services.analytics_events.datetime") as clock,
        patch("app.services.analytics_events.requests.post") as post,
    ):
        clock.now.return_value = searched_at
        emitter.emit_search_performed("u-1", response)
        clock.now.return_value = send_time
        executor.run_all()

    assert post.call_args.kwargs["json"]["metadata"]["searched_at"] == (
        "2026-10-28T11:00:00.000Z"
    )


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
