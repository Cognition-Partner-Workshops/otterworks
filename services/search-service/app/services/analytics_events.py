"""Emit search events to the Analytics Service."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor

import requests
import structlog

from app.config import AnalyticsConfig
from app.models.search_result import SearchResponse

logger = structlog.get_logger()

SEARCH_PERFORMED = "search.performed"


def build_search_performed_event(user_id: str, response: SearchResponse) -> dict:
    """Build an analytics event for a completed search."""
    return {
        "eventType": SEARCH_PERFORMED,
        "userId": user_id,
        "resourceId": str(uuid.uuid4()),
        "resourceType": "search",
        "metadata": {
            "query": response.query,
            "result_count": str(response.total),
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

    @property
    def enabled(self) -> bool:
        return bool(self.config.service_url)

    def emit_search_performed(self, user_id: str, response: SearchResponse) -> None:
        """Schedule an event for a successful search with an identified user."""
        if not self.enabled or not user_id:
            return

        event = build_search_performed_event(user_id, response)
        self.executor.submit(self._post, event)

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
