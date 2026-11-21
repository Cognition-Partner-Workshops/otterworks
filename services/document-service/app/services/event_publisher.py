"""Domain event publishing to SNS and/or EventBridge."""

import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog

from app.config import settings

logger = structlog.get_logger()


class _UUIDEncoder(json.JSONEncoder):
    def default(self, o: object) -> Any:
        if isinstance(o, UUID):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


EVENT_SOURCE = "otterworks.document-service"
_TRANSPORTS = {"sns", "eventbridge", "dual"}


class EventPublisher:
    """Publishes domain events to AWS SNS, EventBridge, or both (dual-run)."""

    def __init__(self) -> None:
        self._clients: dict[str, Any] = {}

    def _get_client(self, service: str = "sns"):  # noqa: ANN202
        if service not in self._clients:
            import boto3

            kwargs = {"region_name": settings.aws_region}
            if settings.aws_endpoint_url:
                kwargs["endpoint_url"] = settings.aws_endpoint_url
            self._clients[service] = boto3.client(service, **kwargs)
        return self._clients[service]

    @staticmethod
    def _transport() -> str:
        transport = settings.event_transport.lower()
        return transport if transport in _TRANSPORTS else "sns"

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        if not settings.sns_enabled:
            logger.info("sns_event_skipped", event_type=event_type)
            return

        message = {
            "event_type": event_type,
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": payload,
        }

        body = json.dumps(message, cls=_UUIDEncoder)
        transport = self._transport()
        if transport in ("sns", "dual"):
            await self._publish_sns(event_type, body)
        if transport in ("eventbridge", "dual"):
            await self._publish_eventbridge(event_type, body)

    async def _publish_sns(self, event_type: str, body: str) -> None:
        try:
            client = self._get_client("sns")
            await asyncio.to_thread(
                client.publish,
                TopicArn=settings.sns_topic_arn,
                Message=body,
                MessageAttributes={
                    "event_type": {"DataType": "String", "StringValue": event_type}
                },
            )
            logger.info("sns_event_published", event_type=event_type)
        except Exception:
            logger.exception("sns_publish_failed", event_type=event_type)

    async def _publish_eventbridge(self, event_type: str, body: str) -> None:
        try:
            client = self._get_client("events")
            response = await asyncio.to_thread(
                client.put_events,
                Entries=[
                    {
                        "EventBusName": settings.event_bus_name,
                        "Source": EVENT_SOURCE,
                        "DetailType": event_type,
                        "Detail": body,
                    }
                ],
            )
            if response.get("FailedEntryCount"):
                entry = response["Entries"][0]
                logger.error(
                    "eventbridge_publish_rejected",
                    event_type=event_type,
                    error_code=entry.get("ErrorCode"),
                    error_message=entry.get("ErrorMessage"),
                )
                return
            logger.info("eventbridge_event_published", event_type=event_type)
        except Exception:
            logger.exception("eventbridge_publish_failed", event_type=event_type)


event_publisher = EventPublisher()
