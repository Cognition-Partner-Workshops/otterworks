"""Drain the analytics queue the way legacy did, staging each batch before deleting it."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from otterworks_etl.analytics.transform import is_malformed, parse_sqs_body
from otterworks_etl.common import get_logger, log_event

logger = get_logger(__name__)


@dataclass
class SqsDrainResult:
    staged_keys: list[str] = field(default_factory=list)
    messages_processed: int = 0
    events: int = 0
    malformed: int = 0
    gave_up: bool = False


def drain_queue(
    client: Any,
    queue_url: str,
    stage_batch: Callable[[int, list[Any]], str],
    *,
    max_messages: int,
    batch_size: int,
    wait_time_seconds: int,
    max_consecutive_errors: int,
    messages_processed: int = 0,
    next_batch: int = 0,
) -> SqsDrainResult:
    """Receive until the queue is empty or ``max_messages`` were seen.

    ``stage_batch(index, events)`` must durably store a batch and return its key; messages
    are deleted only after it returns, so a failed task leaves them on the queue. Bodies that
    are not JSON are never deleted (legacy: they stay in flight and return every run) but count
    toward ``messages_processed``. ``messages_processed``/``next_batch`` resume a retried task.
    """
    result = SqsDrainResult(messages_processed=messages_processed)
    batch_index = next_batch
    consecutive_errors = 0
    while result.messages_processed < max_messages:
        try:
            response = client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=batch_size,
                WaitTimeSeconds=wait_time_seconds,
                AttributeNames=["All"],
                MessageAttributeNames=["All"],
            )
            consecutive_errors = 0
        except Exception as exc:
            consecutive_errors += 1
            log_event(
                logger,
                "sqs_receive_failed",
                logging.WARNING,
                consecutive_errors=consecutive_errors,
                error=str(exc),
            )
            if consecutive_errors >= max_consecutive_errors:
                # legacy: give up and aggregate what was received so far.
                log_event(logger, "sqs_receive_gave_up", logging.ERROR, attempts=consecutive_errors)
                result.gave_up = True
                break
            continue

        messages = response.get("Messages", [])
        if not messages:
            break

        events, entries = [], []
        for msg in messages:
            parsed = parse_sqs_body(msg["Body"])
            if is_malformed(parsed):
                result.malformed += 1
                continue
            events.append(parsed)
            entries.append({"Id": msg["MessageId"], "ReceiptHandle": msg["ReceiptHandle"]})

        if events:
            result.staged_keys.append(stage_batch(batch_index, events))
            batch_index += 1
            deleted = client.delete_message_batch(QueueUrl=queue_url, Entries=entries)
            failed = deleted.get("Failed") or []
            if failed:
                raise RuntimeError(
                    "SQS delete failed for %d of %d staged messages: %s"
                    % (len(failed), len(entries), failed[:3])
                )
            result.events += len(events)

        result.messages_processed += len(messages)

    if result.malformed:
        log_event(
            logger,
            "sqs_malformed_messages_left_in_flight",
            logging.WARNING,
            count=result.malformed,
            queue_url=queue_url,
        )
    return result
