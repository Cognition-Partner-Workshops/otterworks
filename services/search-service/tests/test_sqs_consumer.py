"""Tests for the asyncio SQS consumer."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from typing import Any
from unittest.mock import MagicMock, patch

from app.services.sqs_consumer import SQSConsumer

QUEUE_URL = "http://localstack:4566/000000000000/otterworks-search-events"


def _consumer(sqs: MagicMock, indexer: MagicMock | None = None) -> SQSConsumer:
    consumer = SQSConsumer(indexer=indexer or MagicMock(), queue_url=QUEUE_URL)
    consumer._create_sqs_client = lambda: sqs  # type: ignore[method-assign]
    return consumer


def _blocking_receive(release: threading.Event, batches: list[dict[str, Any]]) -> Any:
    def receive_message(**_: Any) -> dict[str, Any]:
        if batches:
            return batches.pop(0)
        release.wait(20)
        return {}

    return receive_message


def test_stop_does_not_wait_for_long_poll() -> None:
    release = threading.Event()
    sqs = MagicMock()
    sqs.receive_message.side_effect = _blocking_receive(release, [])

    async def scenario() -> float:
        consumer = _consumer(sqs)
        consumer.start()
        await asyncio.sleep(0.2)
        assert sqs.receive_message.called
        started = time.monotonic()
        await consumer.stop()
        return time.monotonic() - started

    try:
        assert asyncio.run(scenario()) < 1
    finally:
        release.set()


def test_message_is_indexed_and_deleted() -> None:
    release = threading.Event()
    event = {"eventType": "file_uploaded", "fileId": "f-1", "name": "a.txt", "ownerId": "u-1"}
    sns_body = json.dumps({"TopicArn": "arn:aws:sns:us-east-1:000000000000:otterworks-events",
                           "Message": json.dumps(event)})
    sqs = MagicMock()
    sqs.receive_message.side_effect = _blocking_receive(
        release, [{"Messages": [{"MessageId": "m-1", "ReceiptHandle": "rh-1", "Body": sns_body}]}]
    )
    indexer = MagicMock()
    indexer.process_event.return_value = {"status": "indexed", "id": "f-1", "type": "file"}

    async def scenario() -> None:
        consumer = _consumer(sqs, indexer)
        consumer.start()
        for _ in range(50):
            if sqs.delete_message.called:
                break
            await asyncio.sleep(0.05)
        await consumer.stop()

    try:
        asyncio.run(scenario())
    finally:
        release.set()

    (normalized,), _ = indexer.process_event.call_args
    assert normalized["action"] == "index_file"
    assert normalized["data"]["id"] == "f-1"
    assert normalized["data"]["owner_id"] == "u-1"
    sqs.delete_message.assert_called_once_with(QueueUrl=QUEUE_URL, ReceiptHandle="rh-1")
    _, kwargs = sqs.receive_message.call_args
    assert kwargs == {"QueueUrl": QUEUE_URL, "MaxNumberOfMessages": 10,
                      "WaitTimeSeconds": 20, "VisibilityTimeout": 60}


def test_start_without_queue_url_is_skipped() -> None:
    async def scenario() -> None:
        consumer = SQSConsumer(indexer=MagicMock(), queue_url="")
        with patch("app.services.sqs_consumer.logger") as log:
            consumer.start()
        log.warning.assert_called_once_with(
            "sqs_consumer_skipped", reason="No SQS_QUEUE_URL configured"
        )
        assert consumer._task is None
        await consumer.stop()

    asyncio.run(scenario())


def test_start_twice_runs_one_consumer() -> None:
    release = threading.Event()
    sqs = MagicMock()
    sqs.receive_message.side_effect = _blocking_receive(release, [])

    async def scenario() -> None:
        consumer = _consumer(sqs)
        consumer.start()
        task = consumer._task
        consumer.start()
        assert consumer._task is task
        await asyncio.sleep(0.2)
        await consumer.stop()

    try:
        asyncio.run(scenario())
    finally:
        release.set()
    assert sqs.receive_message.call_count == 1
