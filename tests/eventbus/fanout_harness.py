"""Domain-event fan-out harness for LocalStack.

Publishes one event of every type the publishers emit today, in the exact wire
shape each publisher uses, then drains every consumer queue and records which
queue received which event and the raw body it saw.

    python tests/eventbus/fanout_harness.py --transport sns --out /tmp/before
    python tests/eventbus/fanout_harness.py --transport eventbridge --out /tmp/after

--transport sns additionally creates throwaway "tfprobe-*" queues subscribed
with the filter policies from infrastructure/terraform/modules/messaging, so the
deployed SNS routing can be observed without AWS.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import boto3

ENDPOINT = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
REGION = os.environ.get("AWS_REGION", "us-east-1")
TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:000000000000:otterworks-events")
BUS_NAME = os.environ.get("EVENT_BUS_NAME", "otterworks-events")
QUEUES = ["otterworks-notifications", "otterworks-search-events", "otterworks-audit-events-queue", "otterworks-analytics-events"]

TS = "2026-11-11T18:00:00+00:00"
DOC_ID = "6f1c9d2e-0000-4000-8000-000000000001"
FILE_ID = "6f1c9d2e-0000-4000-8000-000000000002"
OWNER = "6f1c9d2e-0000-4000-8000-0000000000aa"
OTHER = "6f1c9d2e-0000-4000-8000-0000000000bb"


def _doc(event_type: str, payload: dict) -> dict:
    return {"event_type": event_type, "timestamp": TS, "payload": payload}


def _file(event_type: str, **extra) -> dict:
    body = {"eventType": event_type, "fileId": FILE_ID, "ownerId": OWNER, "folderId": None,
            "sharedWithUserId": None, "timestamp": TS}
    body.update(extra)
    return body


_DOC_INDEX = {"id": DOC_ID, "title": "Q3 plan", "content": "draft", "owner_id": OWNER, "tags": [],
              "created_at": TS, "updated_at": TS}

# (source service, event type, message body) -- shapes mirror
# services/document-service/app/services/event_publisher.py and services/file-service/src/events.rs
EVENTS = [
    ("document-service", "document_created", _doc("document_created", _DOC_INDEX)),
    ("document-service", "document_updated", _doc("document_updated", _DOC_INDEX)),
    ("document-service", "document_deleted", _doc("document_deleted", {"id": DOC_ID, "type": "document"})),
    ("document-service", "comment_added", _doc("comment_added", {"comment_id": "c-1", "document_id": DOC_ID, "author_id": OTHER})),
    ("file-service", "file_uploaded", _file("file_uploaded", name="a.pdf", mimeType="application/pdf", sizeBytes=42)),
    ("file-service", "file_updated", _file("file_updated", name="b.pdf")),
    ("file-service", "file_moved", _file("file_moved")),
    ("file-service", "file_shared", _file("file_shared", sharedWithUserId=OTHER)),
    ("file-service", "file_trashed", _file("file_trashed")),
    ("file-service", "file_restored", _file("file_restored")),
    ("file-service", "file_deleted", _file("file_deleted")),
]

# Copied from infrastructure/terraform/modules/messaging/main.tf on main.
TF_FILTERS = {
    "tfprobe-notifications": {"eventType": ["file_shared", "comment_added", "document_edited", "user_mentioned"]},
    "tfprobe-search": {"eventType": ["document_created", "document_updated", "document_deleted", "file_uploaded", "file_deleted"]},
    "tfprobe-analytics": None,
}


def client(name: str):
    return boto3.client(name, endpoint_url=ENDPOINT, region_name=REGION,
                        aws_access_key_id="test", aws_secret_access_key="test")


def unwrap(body: dict) -> tuple[str, dict]:
    if "Message" in body and "TopicArn" in body:
        return "sns", json.loads(body["Message"])
    if "detail-type" in body and isinstance(body.get("detail"), dict):
        return "eventbridge", body["detail"]
    return "raw", body


def event_type_of(inner: dict) -> str:
    return inner.get("event_type") or inner.get("eventType") or "?"


def queue_url(sqs, name: str) -> str | None:
    try:
        return sqs.get_queue_url(QueueName=name)["QueueUrl"]
    except sqs.exceptions.QueueDoesNotExist:
        return None


def drain(sqs, url: str) -> list[dict]:
    out, empty = [], 0
    while empty < 3:
        resp = sqs.receive_message(QueueUrl=url, MaxNumberOfMessages=10, WaitTimeSeconds=1)
        msgs = resp.get("Messages", [])
        if not msgs:
            empty += 1
            continue
        empty = 0
        for m in msgs:
            out.append(json.loads(m["Body"]))
            sqs.delete_message(QueueUrl=url, ReceiptHandle=m["ReceiptHandle"])
    return out


def setup_tf_probes(sqs, sns) -> dict[str, str]:
    urls = {}
    for name, policy in TF_FILTERS.items():
        url = sqs.create_queue(QueueName=name)["QueueUrl"]
        arn = sqs.get_queue_attributes(QueueUrl=url, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
        attrs = {"FilterPolicy": json.dumps(policy)} if policy else {}
        sns.subscribe(TopicArn=TOPIC_ARN, Protocol="sqs", Endpoint=arn, Attributes=attrs)
        urls[name] = url
    return urls


def teardown_tf_probes(sqs, sns, urls: dict[str, str]) -> None:
    for sub in sns.list_subscriptions_by_topic(TopicArn=TOPIC_ARN)["Subscriptions"]:
        if sub["Endpoint"].rsplit(":", 1)[-1].startswith("tfprobe-"):
            sns.unsubscribe(SubscriptionArn=sub["SubscriptionArn"])
    for url in urls.values():
        sqs.delete_queue(QueueUrl=url)


def publish_sns(sns) -> None:
    for source, event_type, body in EVENTS:
        kwargs = {"TopicArn": TOPIC_ARN, "Message": json.dumps(body)}
        if source == "document-service":
            kwargs["MessageAttributes"] = {"event_type": {"DataType": "String", "StringValue": event_type}}
        sns.publish(**kwargs)


def publish_eventbridge(events) -> None:
    for source, event_type, body in EVENTS:
        resp = events.put_events(Entries=[{"EventBusName": BUS_NAME, "Source": f"otterworks.{source}",
                                           "DetailType": event_type, "Detail": json.dumps(body)}])
        if resp.get("FailedEntryCount"):
            raise RuntimeError(f"put_events failed for {event_type}: {resp['Entries']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--transport", choices=["sns", "eventbridge"], required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    sqs, sns = client("sqs"), client("sns")
    targets = {q: queue_url(sqs, q) for q in QUEUES}
    targets = {q: u for q, u in targets.items() if u}
    for url in targets.values():
        drain(sqs, url)

    probes = setup_tf_probes(sqs, sns) if args.transport == "sns" else {}
    try:
        targets.update(probes)
        if args.transport == "sns":
            publish_sns(sns)
        else:
            publish_eventbridge(client("events"))
        time.sleep(2)
        received = {q: drain(sqs, u) for q, u in targets.items()}
    finally:
        if probes:
            teardown_tf_probes(sqs, sns, probes)

    args.out.mkdir(parents=True, exist_ok=True)
    fixtures = args.out / "fixtures"
    fixtures.mkdir(exist_ok=True)
    matrix: dict[str, dict[str, int]] = {e[1]: {q: 0 for q in received} for e in EVENTS}
    envelopes: dict[str, set[str]] = {q: set() for q in received}
    for q, bodies in received.items():
        for body in bodies:
            kind, inner = unwrap(body)
            et = event_type_of(inner)
            envelopes[q].add(kind)
            matrix.setdefault(et, {k: 0 for k in received})[q] += 1
            (fixtures / f"{args.transport}-{q}-{et}.json").write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")

    report = {"transport": args.transport, "queues": sorted(received),
              "envelopes": {q: sorted(v) for q, v in envelopes.items()}, "matrix": matrix}
    (args.out / "routing.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    cols = list(received)
    lines = ["| event | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    for et, row in matrix.items():
        lines.append(f"| {et} | " + " | ".join(str(row[c]) for c in cols) + " |")
    (args.out / "routing.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print("envelopes:", report["envelopes"])


if __name__ == "__main__":
    main()
