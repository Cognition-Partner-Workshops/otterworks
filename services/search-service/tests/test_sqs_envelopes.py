"""SQS delivery envelopes: SNS (legacy) and EventBridge bodies normalize the same way.

Bodies are copied from tests/eventbus/evidence (captured from LocalStack).
"""

from __future__ import annotations

import json

import pytest

from app.services.sqs_consumer import SQSConsumer

DOC_EVENT = {
    "event_type": "document_created",
    "timestamp": "2026-11-11T18:00:00+00:00",
    "payload": {"id": "6f1c9d2e-0000-4000-8000-000000000001", "title": "Q3 plan"},
}
FILE_EVENT = {
    "eventType": "file_uploaded",
    "fileId": "6f1c9d2e-0000-4000-8000-000000000002",
    "ownerId": "6f1c9d2e-0000-4000-8000-0000000000aa",
    "folderId": None,
    "name": "a.pdf",
    "mimeType": "application/pdf",
    "sizeBytes": 42,
    "timestamp": "2026-11-11T18:00:00+00:00",
}


def _sns(event: dict) -> dict:
    return {
        "Type": "Notification",
        "MessageId": "m-1",
        "TopicArn": "arn:aws:sns:us-east-1:000000000000:otterworks-events",
        "Message": json.dumps(event),
        "Timestamp": "2026-11-11T18:44:12.000Z",
    }


def _eventbridge(source: str, event: dict) -> dict:
    return {
        "version": "0",
        "id": "b38867ad-144c-4de4-9ef6-2b42175e8eb8",
        "detail-type": event.get("event_type") or event["eventType"],
        "source": f"otterworks.{source}",
        "account": "000000000000",
        "time": "2026-11-11T18:44:12Z",
        "region": "us-east-1",
        "resources": [],
        "detail": event,
    }


@pytest.mark.parametrize(
    ("source", "event"),
    [("document-service", DOC_EVENT), ("file-service", FILE_EVENT)],
)
def test_eventbridge_and_sns_normalize_identically(source: str, event: dict) -> None:
    via_sns = SQSConsumer._normalize_event(SQSConsumer._unwrap_envelope(_sns(event)))
    via_eventbridge = SQSConsumer._normalize_event(SQSConsumer._unwrap_envelope(_eventbridge(source, event)))
    direct = SQSConsumer._normalize_event(event)
    assert via_eventbridge == via_sns == direct


def test_unwrapped_body_passes_through() -> None:
    assert SQSConsumer._unwrap_envelope(FILE_EVENT) is FILE_EVENT


def test_detail_must_be_an_object() -> None:
    body = {"detail-type": "x", "detail": "not-an-object"}
    assert SQSConsumer._unwrap_envelope(body) is body
