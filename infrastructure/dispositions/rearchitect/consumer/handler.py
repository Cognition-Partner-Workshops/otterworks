import json
import os

import boto3

TABLE = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])


def handler(event, _context):
    detail = event.get("detail") or {}
    item = {
        "eventId": event["id"],
        "source": event.get("source"),
        "detailType": event.get("detail-type"),
        "eventTime": event.get("time"),
        "detail": json.dumps(detail, separators=(",", ":")),
    }
    TABLE.put_item(Item={key: value for key, value in item.items() if value is not None})
    print(json.dumps({"stored": item["eventId"]}))
    return {"stored": item["eventId"]}
