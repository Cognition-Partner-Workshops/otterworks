"""SQS event consumer for automatic search indexing."""

from __future__ import annotations

import hashlib
import json
import random
import threading
import time
from typing import TYPE_CHECKING, Any

import structlog
from prometheus_client import Counter

if TYPE_CHECKING:
    from app.services.indexer import Indexer

logger = structlog.get_logger()

SQS_MESSAGES = Counter(
    "search_service_sqs_messages_total",
    "SQS messages handled by the search indexing consumer, by outcome",
    ["outcome"],
)

BACKOFF_BASE_SECONDS = 1.0
BACKOFF_CAP_SECONDS = 30.0


class PoisonMessageError(ValueError):
    """The message can never be processed successfully (bad JSON or schema)."""


class SQSConsumer:
    """Background thread SQS consumer for search-indexing queue events."""

    def __init__(
        self,
        indexer: Indexer,
        queue_url: str,
        region: str = "us-east-1",
        endpoint_url: str = "",
        max_messages: int = 10,
        wait_time_seconds: int = 20,
        visibility_timeout: int = 60,
    ) -> None:
        self.indexer = indexer
        self.queue_url = queue_url
        self.region = region
        self.endpoint_url = endpoint_url
        self.max_messages = max_messages
        self.wait_time_seconds = wait_time_seconds
        self.visibility_timeout = visibility_timeout
        self._running = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._has_dlq: bool | None = None

    def start(self) -> None:
        """Start the SQS consumer in a background daemon thread."""
        if not self.queue_url:
            logger.warning("sqs_consumer_skipped", reason="No SQS_QUEUE_URL configured")
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="sqs-consumer"
        )
        self._thread.start()
        logger.info("sqs_consumer_started", queue_url=self.queue_url)

    def stop(self) -> None:
        """Stop the SQS consumer, allowing an in-flight long poll to return."""
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self.wait_time_seconds + 5)
        logger.info("sqs_consumer_stopped")

    def _create_sqs_client(self) -> Any:
        """Create the boto3 SQS client with explicit timeouts and bounded retries."""
        import boto3
        from botocore.config import Config

        kwargs: dict[str, Any] = {
            "region_name": self.region,
            "config": Config(
                connect_timeout=5,
                read_timeout=self.wait_time_seconds + 10,
                retries={"mode": "standard", "max_attempts": 3},
            ),
        }
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url
        return boto3.client("sqs", **kwargs)

    def _queue_has_dlq(self, sqs: Any) -> bool:
        """Return True when the queue has a redrive policy (cached after first check)."""
        if self._has_dlq is None:
            try:
                attrs = sqs.get_queue_attributes(
                    QueueUrl=self.queue_url, AttributeNames=["RedrivePolicy"]
                ).get("Attributes", {})
                self._has_dlq = bool(attrs.get("RedrivePolicy"))
            except Exception:
                logger.warning("sqs_redrive_policy_unknown", queue_url=self.queue_url)
                return False
            logger.info("sqs_redrive_policy_detected", has_dlq=self._has_dlq)
        return self._has_dlq

    @staticmethod
    def _backoff_delay(attempt: int) -> float:
        """Full-jitter exponential backoff delay for consecutive poll failures."""
        ceiling = min(BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * (2 ** attempt))
        return random.uniform(0, ceiling)

    def _poll_loop(self) -> None:
        """Main polling loop for SQS messages."""
        sqs = self._create_sqs_client()
        failures = 0

        while self._running:
            try:
                response = sqs.receive_message(
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=self.max_messages,
                    WaitTimeSeconds=self.wait_time_seconds,
                    VisibilityTimeout=self.visibility_timeout,
                    AttributeNames=["ApproximateReceiveCount"],
                )
                failures = 0
                self._process_batch(sqs, response.get("Messages", []), time.monotonic())
            except Exception:
                delay = self._backoff_delay(failures)
                failures += 1
                logger.exception(
                    "sqs_consumer_error", consecutive_failures=failures, retry_in=round(delay, 2)
                )
                self._stop_event.wait(delay)

    def _process_batch(
        self, sqs: Any, messages: list[dict[str, Any]], received_at: float
    ) -> None:
        """Process a received batch, leaving unstarted messages once the lease is half spent.

        Messages that are not started stay invisible until the visibility
        timeout expires and are then redelivered, instead of being processed
        after their lease has lapsed and duplicated by another consumer.
        """
        budget = self.visibility_timeout / 2
        for index, message in enumerate(messages):
            if not self._running or time.monotonic() - received_at >= budget:
                skipped = len(messages) - index
                SQS_MESSAGES.labels(outcome="deferred").inc(skipped)
                logger.warning(
                    "sqs_batch_deferred",
                    deferred=skipped,
                    elapsed=round(time.monotonic() - received_at, 2),
                    visibility_timeout=self.visibility_timeout,
                )
                return
            self._process_message(sqs, message)

    @staticmethod
    def _normalize_event(body: dict[str, Any]) -> dict[str, Any]:
        """Normalize event payloads from different services into the indexer format.

        Handles:
        - snake_case events with nested payload (document-service format)
        - camelCase flat events from file-service (eventType, fileId, etc.)
        """
        # Format 1: snake_case with nested payload (document-service)
        if "event_type" in body and "payload" in body:
            action_map = {
                "document_created": "index_document",
                "document_updated": "index_document",
                "document_deleted": "delete",
                "file_created": "index_file",
                "file_uploaded": "index_file",
                "file_updated": "index_file",
                "file_deleted": "delete",
                "file_trashed": "delete",
                "file_restored": "index_file",
            }
            return {
                "action": action_map.get(body["event_type"], body["event_type"]),
                "data": body["payload"],
            }

        # Format 2: camelCase flat event from file-service
        if "eventType" in body:
            event_type = body["eventType"]
            action_map = {
                "file_uploaded": "index_file",
                "file_created": "index_file",
                "file_updated": "index_file",
                "file_deleted": "delete",
                "file_trashed": "delete",
                "file_restored": "index_file",
            }
            # file_shared and file_moved events don't carry file metadata
            # (name, mimeType, sizeBytes) so they can't be indexed — skip them
            action = action_map.get(event_type)
            if not action:
                return body

            if action == "delete":
                return {
                    "action": "delete",
                    "data": {
                        "type": "file",
                        "id": body.get("fileId", ""),
                    },
                }

            # Map camelCase fields to snake_case for the indexer
            return {
                "action": action,
                "data": {
                    "id": body.get("fileId", ""),
                    "name": body.get("name", ""),
                    "mime_type": body.get("mimeType", ""),
                    "owner_id": body.get("ownerId", ""),
                    "folder_id": body.get("folderId", ""),
                    "size": body.get("sizeBytes", 0),
                    "tags": body.get("tags", []),
                    "created_at": body.get("timestamp"),
                    "updated_at": body.get("timestamp"),
                },
            }

        # Format 3: already in indexer format (action + data)
        return body

    @staticmethod
    def _parse_message(message: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        """Decode the SQS body (optionally SNS-wrapped) into an indexer event."""
        try:
            body = json.loads(message.get("Body", "{}"))
            sns_message_id = None
            if isinstance(body, dict) and "Message" in body and "TopicArn" in body:
                sns_message_id = body.get("MessageId")
                body = json.loads(body["Message"])
        except (json.JSONDecodeError, TypeError) as exc:
            raise PoisonMessageError("Message body is not valid JSON") from exc
        if not isinstance(body, dict):
            raise PoisonMessageError("Message body must be a JSON object")
        return body, sns_message_id

    def _ack(self, sqs: Any, message: dict[str, Any], log_ctx: dict[str, Any]) -> None:
        try:
            sqs.delete_message(
                QueueUrl=self.queue_url, ReceiptHandle=message.get("ReceiptHandle", "")
            )
        except Exception:
            SQS_MESSAGES.labels(outcome="ack_failed").inc()
            logger.exception("sqs_message_ack_failed", **log_ctx)

    def _process_message(self, sqs: Any, message: dict[str, Any]) -> None:
        """Process a single SQS message.

        Success and ignored events are deleted.  Poison messages are left on
        the queue for redrive when a DLQ is configured, otherwise deleted with
        full identifiers logged.  Transient failures are left for redelivery.
        """
        log_ctx: dict[str, Any] = {
            "message_id": message.get("MessageId"),
            "receive_count": message.get("Attributes", {}).get("ApproximateReceiveCount"),
        }
        try:
            body, sns_message_id = self._parse_message(message)
            log_ctx["sns_message_id"] = sns_message_id
            log_ctx["event_type"] = body.get("event_type") or body.get("eventType")
            event = self._normalize_event(body)
            if not isinstance(event.get("data", {}), dict):
                raise PoisonMessageError("Event 'data' must be a JSON object")
            result = self.indexer.process_event(event)
        except ValueError as exc:
            if self._queue_has_dlq(sqs):
                SQS_MESSAGES.labels(outcome="poison_retained").inc()
                logger.error("sqs_message_poison_retained_for_dlq", reason=str(exc), **log_ctx)
                return
            SQS_MESSAGES.labels(outcome="poison_discarded").inc()
            logger.error(
                "sqs_message_poison_discarded",
                reason=str(exc),
                body_sha256=hashlib.sha256(message.get("Body", "").encode()).hexdigest(),
                body_bytes=len(message.get("Body", "")),
                **log_ctx,
            )
            self._ack(sqs, message, log_ctx)
            return
        except Exception:
            SQS_MESSAGES.labels(outcome="failed").inc()
            logger.exception("sqs_message_processing_failed", **log_ctx)
            return

        outcome = "processed" if result is not None else "ignored"
        SQS_MESSAGES.labels(outcome=outcome).inc()
        logger.info("sqs_message_processed", outcome=outcome, result=result, **log_ctx)
        self._ack(sqs, message, log_ctx)
