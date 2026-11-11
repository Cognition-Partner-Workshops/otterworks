"""Transport selection for document-service domain events."""

import json
from typing import Any

import pytest

from app.config import settings
from app.services.event_publisher import EVENT_SOURCE, EventPublisher


class _FakeClient:
    def __init__(self, failed: int = 0) -> None:
        self.calls: list[dict[str, Any]] = []
        self.failed = failed

    def publish(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"MessageId": "m-1"}

    def put_events(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self.failed:
            entry = {"ErrorCode": "Throttled", "ErrorMessage": "slow down"}
        else:
            entry = {"EventId": "e-1"}
        return {"FailedEntryCount": self.failed, "Entries": [entry]}


TOPIC_ARN = "arn:aws:sns:us-east-1:000000000000:otterworks-events"


@pytest.fixture
def publisher(monkeypatch: pytest.MonkeyPatch) -> tuple[EventPublisher, _FakeClient, _FakeClient]:
    monkeypatch.setattr(settings, "sns_enabled", True)
    monkeypatch.setattr(settings, "sns_topic_arn", TOPIC_ARN)
    monkeypatch.setattr(settings, "event_bus_name", "otterworks-events")
    pub = EventPublisher()
    sns, events = _FakeClient(), _FakeClient()
    pub._clients = {"sns": sns, "events": events}
    return pub, sns, events


async def test_default_transport_is_sns_only(publisher, monkeypatch):
    pub, sns, events = publisher
    monkeypatch.setattr(settings, "event_transport", "sns")
    await pub.publish("document_created", {"id": "d-1"})
    assert len(sns.calls) == 1 and events.calls == []
    call = sns.calls[0]
    attribute = {"DataType": "String", "StringValue": "document_created"}
    assert call["MessageAttributes"] == {"event_type": attribute}
    assert json.loads(call["Message"])["payload"] == {"id": "d-1"}


async def test_eventbridge_detail_is_the_sns_message(publisher, monkeypatch):
    pub, sns, events = publisher
    monkeypatch.setattr(settings, "event_transport", "dual")
    await pub.publish("comment_added", {"comment_id": "c-1"})
    entry = events.calls[0]["Entries"][0]
    assert entry["Source"] == EVENT_SOURCE
    assert entry["DetailType"] == "comment_added"
    assert entry["EventBusName"] == "otterworks-events"
    assert entry["Detail"] == sns.calls[0]["Message"]


async def test_eventbridge_only_skips_sns(publisher, monkeypatch):
    pub, sns, events = publisher
    monkeypatch.setattr(settings, "event_transport", "eventbridge")
    await pub.publish("document_deleted", {"id": "d-1", "type": "document"})
    assert sns.calls == [] and len(events.calls) == 1


async def test_unknown_transport_falls_back_to_sns(publisher, monkeypatch):
    pub, sns, events = publisher
    monkeypatch.setattr(settings, "event_transport", "kafka")
    await pub.publish("document_updated", {"id": "d-1"})
    assert len(sns.calls) == 1 and events.calls == []


async def test_rejected_entry_does_not_raise(publisher, monkeypatch):
    pub, _, _ = publisher
    pub._clients["events"] = _FakeClient(failed=1)
    monkeypatch.setattr(settings, "event_transport", "eventbridge")
    await pub.publish("document_created", {"id": "d-1"})


async def test_disabled_publishes_nothing(publisher, monkeypatch):
    pub, sns, events = publisher
    monkeypatch.setattr(settings, "sns_enabled", False)
    monkeypatch.setattr(settings, "event_transport", "dual")
    await pub.publish("document_created", {"id": "d-1"})
    assert sns.calls == [] and events.calls == []
