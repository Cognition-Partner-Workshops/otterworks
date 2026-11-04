"""Emit search events to the Analytics Service."""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from prometheus_client import Counter
import requests
import structlog

from app.config import AnalyticsConfig
from app.models.search_result import SearchResponse

logger = structlog.get_logger()

SEARCH_PERFORMED = "search.performed"
ANALYTICS_EVENTS_DROPPED = Counter(
    "search_analytics_events_dropped_total",
    "search.performed events dropped because the send backlog was full",
)


def build_search_performed_event(
    user_id: str, response: SearchResponse, searched_at: datetime
) -> dict:
    """Build an analytics event for a completed search."""
    return {
        "eventType": SEARCH_PERFORMED,
        "userId": user_id,
        "resourceId": str(uuid.uuid4()),
        "resourceType": "search",
        "metadata": {
            "query": response.query,
            "result_count": str(response.total),
            "searched_at": (
                searched_at.astimezone(timezone.utc)
                .isoformat(timespec="milliseconds")
                .replace("+00:00", "Z")
            ),
            "document_hit_ids": ",".join(
                hit.id for hit in response.results if hit.type == "document"
            ),
        },
    }


class AnalyticsEmitter:
    """Send search events to the Analytics Service asynchronously."""

    def __init__(self, config: AnalyticsConfig, executor=None) -> None:
        self.config = config
        self.executor = (
            executor
            if executor is not None
            else ThreadPoolExecutor(max_workers=2, thread_name_prefix="analytics-emit")
        )
        self._slots = threading.BoundedSemaphore(config.max_pending)

    @property
    def enabled(self) -> bool:
        return bool(self.config.service_url)

    def emit_search_performed(self, user_id: str, response: SearchResponse) -> None:
        """Schedule an event for a successful search with an identified user."""
        if not self.enabled or not user_id:
            return

        searched_at = datetime.now(timezone.utc)
        if not self._slots.acquire(blocking=False):
            ANALYTICS_EVENTS_DROPPED.inc()
            logger.warning(
                "analytics_emit_dropped",
                event_type=SEARCH_PERFORMED,
                max_pending=self.config.max_pending,
            )
            return

        event = build_search_performed_event(user_id, response, searched_at)
        try:
            self.executor.submit(self._send, event)
        except Exception as error:
            self._slots.release()
            logger.warning(
                "analytics_emit_dropped",
                event_type=SEARCH_PERFORMED,
                max_pending=self.config.max_pending,
                error=str(error),
            )

    def _send(self, event: dict) -> None:
        try:
            self._post(event)
        finally:
            self._slots.release()

    def _post(self, event: dict) -> None:
        try:
            response = requests.post(
                f"{self.config.service_url.rstrip('/')}/api/v1/analytics/events",
                json=event,
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            logger.warning(
                "analytics_emit_failed",
                event_type=event["eventType"],
                error=str(error),
            )
