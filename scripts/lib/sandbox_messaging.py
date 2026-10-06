#!/usr/bin/env python3
"""Failure/recovery driver for the messaging reliability sandbox.

Reads `terraform output -json` of infrastructure/terraform/reliability-sandbox
(or its before/ twin) and drives the analytics path end to end:
SNS topic -> analytics_events queue -> consumer -> DynamoDB ledger, with the
module's redrive policy, dead-letter queue and alarms in between.

The consumer follows the analytics contract: it deletes a message only after
its durable write, and the write is a conditional transaction keyed by the
producer's eventId, so redelivery and redrive can never apply an event twice.

Every call is refused unless the resource name starts with the run token.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from typing import Any

import boto3
from botocore.exceptions import ClientError

ROLLUP_PK = "ROLLUP#analytics"


class SandboxError(RuntimeError):
    pass


def load_outputs(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    out = {k: (v["value"] if isinstance(v, dict) and "value" in v else v) for k, v in raw.items()}
    if "run_token" not in out:
        raise SandboxError(f"{path} has no run_token output; is it the sandbox root?")
    return out


def name_of(url_or_arn: str) -> str:
    return url_or_arn.rstrip("/").split("/")[-1].split(":")[-1]


class Sandbox:
    def __init__(self, outputs: dict[str, Any], session: boto3.session.Session | None = None):
        self.o = outputs
        self.token = outputs["run_token"]
        session = session or boto3.session.Session(region_name=outputs.get("region", "us-east-1"))
        self.sqs = session.client("sqs")
        self.sns = session.client("sns")
        self.ddb = session.client("dynamodb")
        self.cw = session.client("cloudwatch")
        for key in ("events_topic_arn", "analytics_queue_url", "analytics_dlq_url", "ledger_table_name",
                    "search_indexing_queue_url", "search_indexing_dlq_url", "notification_queue_url"):
            if key in outputs:
                self.guard(outputs[key])

    def guard(self, resource: str) -> str:
        if not name_of(resource).startswith(self.token):
            raise SandboxError(f"refusing to touch {resource}: not owned by run token {self.token}")
        return resource

    # --- producer -----------------------------------------------------------

    def publish(self, count: int, batch: str | None = None) -> list[str]:
        batch = batch or uuid.uuid4().hex[:8]
        ids = []
        for i in range(count):
            event_id = f"{batch}-{i:04d}"
            body = {"eventId": event_id, "eventType": "file_uploaded", "fileId": f"sbx-{event_id}",
                    "occurredAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            self.sns.publish(
                TopicArn=self.guard(self.o["events_topic_arn"]),
                Message=json.dumps(body),
                MessageAttributes={"eventType": {"DataType": "String", "StringValue": "file_uploaded"}},
            )
            ids.append(event_id)
        return ids

    # --- consumer -----------------------------------------------------------

    @staticmethod
    def parse(message: dict[str, Any]) -> dict[str, Any]:
        envelope = json.loads(message["Body"])
        inner = envelope.get("Message", envelope) if isinstance(envelope, dict) else envelope
        event = json.loads(inner) if isinstance(inner, str) else inner
        if not isinstance(event, dict) or not event.get("eventId"):
            raise ValueError("event has no eventId")
        return event

    def apply(self, event: dict[str, Any]) -> bool:
        """Durable, idempotent write. True if applied now, False if already applied."""
        table = self.guard(self.o["ledger_table_name"])
        try:
            self.ddb.transact_write_items(TransactItems=[
                {"Put": {"TableName": table,
                         "Item": {"pk": {"S": f"EVENT#{event['eventId']}"},
                                  "eventType": {"S": str(event.get("eventType", ""))},
                                  "appliedAt": {"N": str(int(time.time()))}},
                         "ConditionExpression": "attribute_not_exists(pk)"}},
                {"Update": {"TableName": table, "Key": {"pk": {"S": ROLLUP_PK}},
                            "UpdateExpression": "ADD events :one",
                            "ExpressionAttributeValues": {":one": {"N": "1"}}}},
            ])
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "TransactionCanceledException":
                raise
            reasons = exc.response.get("CancellationReasons") or []
            if reasons and reasons[0].get("Code") == "ConditionalCheckFailed":
                return False
            raise

    def consume(self, fault: str = "none", crash_after_write: bool = False, idle_seconds: int = 30,
                wait_seconds: int = 5, max_seconds: int = 900, queue_key: str = "analytics_queue_url") -> dict[str, int]:
        url = self.guard(self.o[queue_key])
        stats = {"received": 0, "applied": 0, "duplicates": 0, "failed": 0, "deleted": 0, "crashed": 0,
                 "max_receive_count_seen": 0}
        crashed: set[str] = set()
        idle_since = time.monotonic()
        started = time.monotonic()
        while time.monotonic() - idle_since < idle_seconds and time.monotonic() - started < max_seconds:
            resp = self.sqs.receive_message(QueueUrl=url, MaxNumberOfMessages=10, WaitTimeSeconds=wait_seconds,
                                            AttributeNames=["ApproximateReceiveCount"])
            messages = resp.get("Messages", [])
            if not messages:
                continue
            idle_since = time.monotonic()
            for m in messages:
                stats["received"] += 1
                stats["max_receive_count_seen"] = max(stats["max_receive_count_seen"],
                                                      int(m.get("Attributes", {}).get("ApproximateReceiveCount", "1")))
                try:
                    if fault == "ledger":
                        raise SandboxError("injected ledger outage")
                    if fault == "parse":
                        raise ValueError("injected parse failure")
                    applied = self.apply(self.parse(m))
                except (SandboxError, ValueError, ClientError):
                    # Leave it on the queue and make it visible again at once;
                    # the redrive policy decides when it has failed for good.
                    stats["failed"] += 1
                    self.sqs.change_message_visibility(QueueUrl=url, ReceiptHandle=m["ReceiptHandle"], VisibilityTimeout=0)
                    continue
                stats["applied" if applied else "duplicates"] += 1
                if crash_after_write and m["MessageId"] not in crashed:
                    # Crash once per message between the durable write and the ack.
                    crashed.add(m["MessageId"])
                    stats["crashed"] += 1
                    self.sqs.change_message_visibility(QueueUrl=url, ReceiptHandle=m["ReceiptHandle"], VisibilityTimeout=0)
                    continue
                self.sqs.delete_message(QueueUrl=url, ReceiptHandle=m["ReceiptHandle"])
                stats["deleted"] += 1
        return stats

    # --- recovery -----------------------------------------------------------

    def depth(self, url: str) -> int:
        attrs = self.sqs.get_queue_attributes(QueueUrl=self.guard(url), AttributeNames=[
            "ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible"])["Attributes"]
        return int(attrs["ApproximateNumberOfMessages"]) + int(attrs["ApproximateNumberOfMessagesNotVisible"])

    def wait_depth(self, key: str, expect: int, timeout: int = 300, poll: float = 5) -> int:
        deadline = time.monotonic() + timeout
        while True:
            n = self.depth(self.o[key])
            if n >= expect or time.monotonic() >= deadline:
                return n
            time.sleep(poll)

    def redrive(self, timeout: int = 600, poll: float = 5) -> dict[str, Any]:
        dlq_arn = self.guard(self.o["analytics_dlq_arn"])
        handle = self.sqs.start_message_move_task(SourceArn=dlq_arn)["TaskHandle"]
        deadline = time.monotonic() + timeout
        while True:
            tasks = self.sqs.list_message_move_tasks(SourceArn=dlq_arn, MaxResults=1).get("Results", [])
            task = tasks[0] if tasks else {}
            if task.get("Status") in ("COMPLETED", "FAILED", "CANCELLED") or time.monotonic() >= deadline:
                task["TaskHandle"] = handle
                return task
            time.sleep(poll)

    def ledger(self) -> tuple[set[str], int]:
        table = self.guard(self.o["ledger_table_name"])
        events, rollup = set(), 0
        for page in self.ddb.get_paginator("scan").paginate(TableName=table, ConsistentRead=True):
            for item in page["Items"]:
                pk = item["pk"]["S"]
                if pk == ROLLUP_PK:
                    rollup = int(item.get("events", {}).get("N", "0"))
                elif pk.startswith("EVENT#"):
                    events.add(pk[len("EVENT#"):])
        return events, rollup

    def verify(self, expected_ids: list[str]) -> dict[str, Any]:
        events, rollup = self.ledger()
        expected = set(expected_ids)
        result = {
            "expected": len(expected),
            "ledger_events": len(events),
            "rollup_events": rollup,
            "missing": sorted(expected - events),
            "unexpected": sorted(events - expected),
            "analytics_queue_depth": self.depth(self.o["analytics_queue_url"]),
            "analytics_dlq_depth": self.depth(self.o["analytics_dlq_url"]),
        }
        result["exactly_once"] = (not result["missing"] and not result["unexpected"] and rollup == len(expected)
                                  and result["analytics_queue_depth"] == 0 and result["analytics_dlq_depth"] == 0)
        return result

    def reset(self) -> dict[str, Any]:
        purged = []
        for key in ("analytics_queue_url", "analytics_dlq_url", "search_indexing_queue_url", "search_indexing_dlq_url",
                    "notification_queue_url"):
            if key in self.o:
                try:
                    self.sqs.purge_queue(QueueUrl=self.guard(self.o[key]))
                    purged.append(name_of(self.o[key]))
                except ClientError as exc:
                    if exc.response["Error"]["Code"] not in ("AWS.SimpleQueueService.PurgeQueueInProgress",
                                                             "PurgeQueueInProgress"):
                        raise
                    purged.append(name_of(self.o[key]) + " (purge already in progress)")
        deleted = 0
        if "ledger_table_name" in self.o:
            table = self.guard(self.o["ledger_table_name"])
            for page in self.ddb.get_paginator("scan").paginate(TableName=table, ProjectionExpression="pk"):
                for item in page["Items"]:
                    self.ddb.delete_item(TableName=table, Key={"pk": item["pk"]})
                    deleted += 1
        return {"purged": purged, "ledger_items_deleted": deleted}

    def status(self) -> dict[str, Any]:
        out: dict[str, Any] = {"run_token": self.token, "queues": {}}
        for key in ("analytics_queue_url", "analytics_dlq_url", "search_indexing_queue_url", "search_indexing_dlq_url"):
            if key in self.o:
                attrs = self.sqs.get_queue_attributes(QueueUrl=self.guard(self.o[key]), AttributeNames=["All"])["Attributes"]
                out["queues"][name_of(self.o[key])] = {
                    "visible": int(attrs.get("ApproximateNumberOfMessages", 0)),
                    "in_flight": int(attrs.get("ApproximateNumberOfMessagesNotVisible", 0)),
                    "redrive_policy": json.loads(attrs["RedrivePolicy"]) if "RedrivePolicy" in attrs else None,
                }
        names = list((self.o.get("dlq_alarm_names") or {}).values()) + list((self.o.get("backlog_alarm_names") or {}).values())
        if names:
            alarms = self.cw.describe_alarms(AlarmNames=[self.guard(n) for n in names])["MetricAlarms"]
            out["alarms"] = {a["AlarmName"]: {"state": a["StateValue"], "actions": a.get("AlarmActions", [])} for a in alarms}
        return out


NAME_KEYS = ("name", "alarm_name", "function_name", "bucket", "role_name")
SAFE_ACTIONS = {"create", "no-op", "read", "update"}


def plan_guard(plan: dict[str, Any], token: str, allow_delete: bool = False) -> list[str]:
    """Problems with a `terraform show -json` plan; empty means it only touches this token's resources."""
    problems = []
    if plan.get("resource_drift"):
        problems.append("plan reports drift on existing resources")
    for rc in plan.get("resource_changes", []):
        actions = set(rc.get("change", {}).get("actions", []))
        if rc.get("change", {}).get("importing"):
            problems.append(f"{rc['address']}: imports are not allowed in the sandbox")
        if not allow_delete and not actions <= SAFE_ACTIONS:
            problems.append(f"{rc['address']}: {sorted(actions)} is not create/update")
        if rc.get("mode") == "data":
            continue
        values = rc.get("change", {}).get("after") or rc.get("change", {}).get("before") or {}
        for key in NAME_KEYS:
            name = values.get(key)
            if isinstance(name, str) and not name.startswith(token):
                problems.append(f"{rc['address']}: {key}={name} does not start with {token}")
        tags = values.get("tags_all") or {}
        if "tags_all" in values and tags is not None and tags.get("run_token") not in (None, token):
            problems.append(f"{rc['address']}: run_token tag {tags.get('run_token')} != {token}")
    return problems


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--outputs", help="terraform output -json of the sandbox root")
    sub = p.add_subparsers(dest="cmd", required=True)
    pg = sub.add_parser("plan-guard", help="refuse a plan that is not confined to this run token")
    pg.add_argument("--plan-json", required=True)
    pg.add_argument("--run-token", required=True)
    pg.add_argument("--allow-delete", action="store_true")
    pub = sub.add_parser("publish")
    pub.add_argument("--count", type=int, default=5)
    pub.add_argument("--batch")
    pub.add_argument("--ids-file", required=True)
    con = sub.add_parser("consume")
    con.add_argument("--fault", choices=["none", "ledger", "parse"], default="none")
    con.add_argument("--crash-after-write", action="store_true")
    con.add_argument("--idle-seconds", type=int, default=30)
    con.add_argument("--max-seconds", type=int, default=900)
    wt = sub.add_parser("wait-depth")
    wt.add_argument("--queue", choices=["analytics_queue_url", "analytics_dlq_url"], required=True)
    wt.add_argument("--expect", type=int, required=True)
    wt.add_argument("--timeout", type=int, default=300)
    rd = sub.add_parser("redrive")
    rd.add_argument("--timeout", type=int, default=600)
    vf = sub.add_parser("verify")
    vf.add_argument("--ids-file", required=True)
    sub.add_parser("reset")
    sub.add_parser("status")
    args = p.parse_args(argv)

    if args.cmd == "plan-guard":
        with open(args.plan_json, encoding="utf-8") as fh:
            problems = plan_guard(json.load(fh), args.run_token, args.allow_delete)
        print(json.dumps({"run_token": args.run_token, "problems": problems}, indent=2))
        return 1 if problems else 0
    if not args.outputs:
        p.error("--outputs is required")
    sb = Sandbox(load_outputs(args.outputs))
    rc = 0
    if args.cmd == "publish":
        ids = sb.publish(args.count, args.batch)
        try:
            with open(args.ids_file, encoding="utf-8") as fh:
                prior = json.load(fh)
        except FileNotFoundError:
            prior = []
        with open(args.ids_file, "w", encoding="utf-8") as fh:
            json.dump(prior + ids, fh)
        result: Any = {"published": ids}
    elif args.cmd == "consume":
        result = sb.consume(args.fault, args.crash_after_write, args.idle_seconds, max_seconds=args.max_seconds)
    elif args.cmd == "wait-depth":
        n = sb.wait_depth(args.queue, args.expect, args.timeout)
        result = {"queue": args.queue, "depth": n, "expected_at_least": args.expect}
        rc = 0 if n >= args.expect else 1
    elif args.cmd == "redrive":
        result = sb.redrive(args.timeout)
        rc = 0 if result.get("Status") == "COMPLETED" else 1
    elif args.cmd == "verify":
        with open(args.ids_file, encoding="utf-8") as fh:
            result = sb.verify(json.load(fh))
        rc = 0 if result["exactly_once"] else 1
    elif args.cmd == "reset":
        result = sb.reset()
    else:
        result = sb.status()
    print(json.dumps(result, indent=2, sort_keys=True))
    return rc


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SandboxError as exc:
        print(f"sandbox: {exc}", file=sys.stderr)
        sys.exit(2)
