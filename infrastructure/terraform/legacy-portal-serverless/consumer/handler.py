"""Writes one DynamoDB item per announcement.published event from the run's bus."""

import json
import os

import boto3
from botocore.config import Config

# Two attempts of at most 1 s connect + 2 s read, plus one standard-mode backoff of up to 1 s,
# stay inside the function's 10 s timeout; whole-event retries belong to Lambda async invoke.
SDK_CONFIG = Config(connect_timeout=1, read_timeout=2, retries={"mode": "standard", "total_max_attempts": 2})
TABLE = boto3.resource("dynamodb", config=SDK_CONFIG).Table(os.environ["TABLE_NAME"])


def handler(event, _context):
    try:
        detail = event.get("detail") or {}
        item = {
            "eventId": event["id"],
            "announcementId": detail.get("id"),
            "title": detail.get("title"),
            "body": detail.get("body"),
            "published": bool(detail.get("published")),
            "createdAt": detail.get("createdAt"),
            "eventTime": event.get("time"),
            "source": event.get("source"),
            "detailType": event.get("detail-type"),
            "detail": json.dumps(detail, separators=(",", ":")),
        }
        TABLE.put_item(Item={k: v for k, v in item.items() if v is not None})
    except Exception as e:
        # The whole event goes to the log so it can be re-invoked once retries are exhausted.
        print(json.dumps({"failed": event.get("id"), "error": f"{type(e).__name__}: {e}", "event": event}, default=str))
        raise
    print(json.dumps({"stored": item["eventId"], "announcementId": item["announcementId"]}))
    return {"stored": item["eventId"]}
