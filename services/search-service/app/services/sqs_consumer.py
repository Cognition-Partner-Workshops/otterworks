"""SQS event consumer for automatic search indexing."""

from __future__ import annotations

import asyncio
import contextlib
import json
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

import structlog

if TYPE_CHECKING:
    from app.config import SQSConfig
    from app.services.indexer import Indexer

logger = structlog.get_logger()

T = TypeVar("T")


async def _run_in_daemon_thread(func: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """Like ``asyncio.to_thread`` but on a daemon thread that is never joined.

    The default executor is joined on loop and interpreter shutdown, so a
    cancelled 20 s ``receive_message`` long poll would still hold up process
    exit. Abandoning it is safe: unreceived messages stay on the queue and
    received-but-unprocessed ones reappear after the visibility timeout.
    """
    loop = asyncio.get_running_loop()
    future: asyncio.Future[T] = loop.create_future()

    def settle(result: Any, exc: BaseException | None) -> None:
        if future.done():
            return
        if exc is not None:
            future.set_exception(exc)
        else:
            future.set_result(result)

    def run() -> None:
        try:
            result, exc = func(*args, **kwargs), None
        except BaseException as e:  # noqa: BLE001 - handed to the awaiting task
            result, exc = None, e
        with contextlib.suppress(RuntimeError):  # loop already closed
            loop.call_soon_threadsafe(settle, result, exc)

    threading.Thread(target=run, daemon=True, name="sqs-consumer-poll").start()
    return await future


class SQSConsumer:
    """asyncio task SQS consumer for search-indexing queue events."""

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
        self._task: asyncio.Task[None] | None = None

    @classmethod
    def from_config(cls, config: SQSConfig, indexer: Indexer) -> SQSConsumer:
        return cls(
            indexer=indexer,
            queue_url=config.queue_url,
            region=config.region,
            endpoint_url=config.endpoint_url,
            max_messages=config.max_messages,
            wait_time_seconds=config.wait_time_seconds,
            visibility_timeout=config.visibility_timeout,
        )

    def start(self) -> None:
        """Start the SQS consumer as a task on the running event loop."""
        if not self.queue_url:
            logger.warning("sqs_consumer_skipped", reason="No SQS_QUEUE_URL configured")
            return
        if self._task is not None and not self._task.done():
            return

        self._task = asyncio.get_running_loop().create_task(
            self._poll_loop(), name="sqs-consumer"
        )
        logger.info("sqs_consumer_started", queue_url=self.queue_url)

    async def stop(self) -> None:
        """Cancel the consumer task without waiting for an in-flight long poll."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("sqs_consumer_stopped")

    def _create_sqs_client(self) -> Any:
        """Create the boto3 SQS client lazily."""
        import boto3

        kwargs: dict[str, Any] = {"region_name": self.region}
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url
        return boto3.client("sqs", **kwargs)

    async def _poll_loop(self) -> None:
        """Main polling loop for SQS messages."""
        sqs = await asyncio.to_thread(self._create_sqs_client)

        while True:
            try:
                response = await _run_in_daemon_thread(
                    sqs.receive_message,
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=self.max_messages,
                    WaitTimeSeconds=self.wait_time_seconds,
                    VisibilityTimeout=self.visibility_timeout,
                )

                messages = response.get("Messages", [])
                for message in messages:
                    await self._process_message(sqs, message)

            except Exception:
                logger.exception("sqs_consumer_error")
                await asyncio.sleep(5)

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

    async def _process_message(self, sqs: Any, message: dict[str, Any]) -> None:
        """Process a single SQS message."""
        receipt_handle = message.get("ReceiptHandle", "")
        try:
            body = json.loads(message.get("Body", "{}"))

            # Handle SNS-wrapped messages
            if "Message" in body and "TopicArn" in body:
                body = json.loads(body["Message"])

            body = self._normalize_event(body)

            result = await asyncio.to_thread(self.indexer.process_event, body)
            logger.info("sqs_message_processed", result=result)

            # Delete the message after successful processing
            await asyncio.to_thread(
                sqs.delete_message, QueueUrl=self.queue_url, ReceiptHandle=receipt_handle
            )

        except json.JSONDecodeError:
            logger.error("sqs_message_invalid_json", message_id=message.get("MessageId"))
            await asyncio.to_thread(
                sqs.delete_message, QueueUrl=self.queue_url, ReceiptHandle=receipt_handle
            )
        except ValueError:
            logger.error(
                "sqs_message_validation_failed", message_id=message.get("MessageId")
            )
            await asyncio.to_thread(
                sqs.delete_message, QueueUrl=self.queue_url, ReceiptHandle=receipt_handle
            )
        except Exception:
            logger.exception(
                "sqs_message_processing_failed", message_id=message.get("MessageId")
            )
