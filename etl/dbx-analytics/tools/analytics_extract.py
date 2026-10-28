#!/usr/bin/env python3
"""Converted analytics_daily extract (analytics_daily unit).

Port of the extract half of etl/scripts/analytics_daily.py: drains the SQS
queue `otterworks-analytics` (delete-after-read, batches of 10, same
10000-message cap) and scans the DynamoDB table `otterworks-analytics-events`
with `begins_with(event_date, :ds)`. Produces one artifact:

- `analytics_events_<ds>.jsonl` — keyed event snapshot the staging landing
  consumes: one JSON object per line, verbatim event fields plus `source`
  ("sqs" | "dynamodb") marking which leg of the legacy pull produced it, so
  the landing can keep the legacy filter asymmetry (SQS undated, DynamoDB
  date-filtered).

Runs wherever the fixture is reachable; the endpoint comes from
AWS_ENDPOINT_URL only (fixture surfaces), never real AWS credentials.
"""

import argparse
import json
import os
from decimal import Decimal

import boto3

SQS_QUEUE_URL = (
    "https://sqs.us-east-1.amazonaws.com/123456789012/otterworks-analytics"
)
DYNAMO_TABLE = "otterworks-analytics-events"
MAX_MESSAGES = 10000
BATCH_SIZE = 10


def aws(service: str, kind: str = "client"):
    endpoint = os.environ.get("AWS_ENDPOINT_URL")
    factory = getattr(boto3, kind)
    return (
        factory(service, endpoint_url=endpoint) if endpoint else factory(service)
    )


def drain_sqs() -> list[dict]:
    events = []
    processed = 0
    consecutive_errors = 0
    sqs = aws("sqs")
    while processed < MAX_MESSAGES:
        try:
            response = sqs.receive_message(
                QueueUrl=SQS_QUEUE_URL,
                MaxNumberOfMessages=BATCH_SIZE,
                WaitTimeSeconds=5,
                AttributeNames=["All"],
                MessageAttributeNames=["All"],
            )
            consecutive_errors = 0
        except Exception:
            consecutive_errors += 1
            if consecutive_errors >= 3:
                break
            continue
        messages = response.get("Messages", [])
        if not messages:
            break
        to_delete = []
        for msg in messages:
            try:
                event = json.loads(msg["Body"])
                events.append(event)
                to_delete.append(
                    {"Id": msg["MessageId"], "ReceiptHandle": msg["ReceiptHandle"]}
                )
            except Exception:
                pass
        if to_delete:
            sqs.delete_message_batch(QueueUrl=SQS_QUEUE_URL, Entries=to_delete)
        processed += len(messages)
    return events


def scan_dynamodb(ds: str) -> list[dict]:
    table = aws("dynamodb", kind="resource").Table(DYNAMO_TABLE)
    events = []
    scan_kwargs = {
        "FilterExpression": "begins_with(event_date, :ds)",
        "ExpressionAttributeValues": {":ds": ds},
    }
    while True:
        response = table.scan(**scan_kwargs)
        for item in response.get("Items", []):
            for k, v in item.items():
                if isinstance(v, Decimal):
                    item[k] = int(v) if v == int(v) else float(v)
            events.append(item)
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key
    return events


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--ds", required=True, help="run date, YYYY-MM-DD")
    p.add_argument("--out", required=True, help="output JSONL path")
    args = p.parse_args()

    sqs_events = drain_sqs()
    dynamo_events = scan_dynamodb(args.ds)

    with open(args.out, "w") as fh:
        for event in sqs_events:
            fh.write(json.dumps({"source": "sqs", **event}) + "\n")
        for event in dynamo_events:
            fh.write(json.dumps({"source": "dynamodb", **event}) + "\n")

    print(
        "analytics_extract: %d sqs + %d dynamodb events -> %s"
        % (len(sqs_events), len(dynamo_events), args.out)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
