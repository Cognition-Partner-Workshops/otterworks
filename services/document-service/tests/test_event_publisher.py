"""SNS event publishing."""

import json
import uuid
from datetime import UTC, datetime

import pytest

from app.config import settings
from app.services import event_publisher as event_publisher_module
from app.services.event_publisher import EventPublisher, _UUIDEncoder


class FakeSNS:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self.error = error

    def publish(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {"MessageId": "1"}


@pytest.fixture
def sns_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "sns_enabled", True)
    monkeypatch.setattr(settings, "sns_topic_arn", "arn:aws:sns:us-east-1:000000000000:docs")


def test_encoder_serialises_uuid_and_datetime() -> None:
    doc_id = uuid.uuid4()
    when = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    encoded = json.loads(json.dumps({"id": doc_id, "at": when}, cls=_UUIDEncoder))
    assert encoded == {"id": str(doc_id), "at": "2026-01-02T03:04:05+00:00"}


def test_encoder_rejects_unknown_types() -> None:
    with pytest.raises(TypeError):
        json.dumps({"value": object()}, cls=_UUIDEncoder)


@pytest.mark.asyncio
async def test_publish_is_skipped_when_sns_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "sns_enabled", False)
    publisher = EventPublisher()

    def no_client():
        raise AssertionError("SNS must not be contacted while disabled")

    monkeypatch.setattr(publisher, "_get_client", no_client)
    await publisher.publish("document_created", {"id": uuid.uuid4()})


@pytest.mark.asyncio
async def test_publish_sends_event_envelope(sns_enabled: None) -> None:
    publisher = EventPublisher()
    fake = FakeSNS()
    publisher._client = fake
    doc_id = uuid.uuid4()

    await publisher.publish("document_created", {"id": doc_id, "title": "T"})

    (call,) = fake.calls
    assert call["TopicArn"] == settings.sns_topic_arn
    assert call["MessageAttributes"] == {
        "event_type": {"DataType": "String", "StringValue": "document_created"}
    }
    message = json.loads(call["Message"])
    assert message["event_type"] == "document_created"
    assert message["payload"] == {"id": str(doc_id), "title": "T"}
    assert datetime.fromisoformat(message["timestamp"]).tzinfo is not None


@pytest.mark.asyncio
async def test_publish_failure_is_swallowed(sns_enabled: None) -> None:
    publisher = EventPublisher()
    fake = FakeSNS(error=RuntimeError("throttled"))
    publisher._client = fake

    await publisher.publish("document_deleted", {"id": uuid.uuid4()})

    assert len(fake.calls) == 1


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        ("", {"region_name": "eu-west-1"}),
        (
            "http://localstack:4566",
            {"region_name": "eu-west-1", "endpoint_url": "http://localstack:4566"},
        ),
    ],
)
def test_client_is_built_once_from_settings(
    monkeypatch: pytest.MonkeyPatch, endpoint: str, expected: dict
) -> None:
    import boto3

    built: list[tuple[str, dict]] = []

    def fake_client(service: str, **kwargs):
        built.append((service, kwargs))
        return FakeSNS()

    monkeypatch.setattr(boto3, "client", fake_client)
    monkeypatch.setattr(settings, "aws_region", "eu-west-1")
    monkeypatch.setattr(settings, "aws_endpoint_url", endpoint)
    publisher = EventPublisher()

    first = publisher._get_client()
    assert publisher._get_client() is first
    assert built == [("sns", expected)]


def test_module_exposes_a_shared_publisher() -> None:
    assert isinstance(event_publisher_module.event_publisher, EventPublisher)
