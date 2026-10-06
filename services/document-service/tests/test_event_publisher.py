"""SNS publishing must match the shared subscription filter contract."""

import json

import boto3
import pytest
from moto import mock_aws

from app.config import settings
from app.services.event_publisher import EventPublisher

SEARCH_FILTER = {
    "eventType": [
        "document_created",
        "document_updated",
        "document_deleted",
        "file_uploaded",
        "file_deleted",
    ]
}


@pytest.fixture
def aws(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setattr(settings, "aws_endpoint_url", "")
    monkeypatch.setattr(settings, "aws_region", "us-east-1")
    with mock_aws():
        yield


def _search_queue(topic_arn: str) -> str:
    sns = boto3.client("sns", region_name="us-east-1")
    sqs = boto3.client("sqs", region_name="us-east-1")
    queue_url = sqs.create_queue(QueueName="search-indexing")["QueueUrl"]
    queue_arn = sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])[
        "Attributes"
    ]["QueueArn"]
    sns.subscribe(
        TopicArn=topic_arn,
        Protocol="sqs",
        Endpoint=queue_arn,
        Attributes={"FilterPolicy": json.dumps(SEARCH_FILTER)},
    )
    return queue_url


async def test_document_event_reaches_filtered_search_subscription(
    aws, monkeypatch: pytest.MonkeyPatch
) -> None:
    topic_arn = boto3.client("sns", region_name="us-east-1").create_topic(Name="events")["TopicArn"]
    queue_url = _search_queue(topic_arn)
    monkeypatch.setattr(settings, "sns_enabled", True)
    monkeypatch.setattr(settings, "sns_topic_arn", topic_arn)

    await EventPublisher().publish("document_created", {"id": "doc-1"})

    messages = (
        boto3.client("sqs", region_name="us-east-1")
        .receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10)
        .get("Messages", [])
    )
    assert len(messages) == 1
    envelope = json.loads(messages[0]["Body"])
    assert envelope["MessageAttributes"]["eventType"]["Value"] == "document_created"
    body = json.loads(envelope["Message"])
    assert body["event_type"] == "document_created"
    assert body["payload"] == {"id": "doc-1"}


def test_client_bounds_timeouts_and_retries(aws) -> None:
    config = EventPublisher()._get_client().meta.config
    assert config.connect_timeout == settings.sns_connect_timeout_seconds
    assert config.read_timeout == settings.sns_read_timeout_seconds
    assert config.retries["mode"] == "standard"
    assert config.retries["total_max_attempts"] == settings.sns_max_retries + 1
