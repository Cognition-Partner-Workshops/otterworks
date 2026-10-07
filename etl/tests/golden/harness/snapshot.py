"""Captures every output surface of a run as plain, reviewable JSON.

Files (one per surface, see README.md for the exact shape):
  result.json       process exit code
  s3.json           every object in every bucket: decompressed/decoded body,
                    ContentType, ContentEncoding, StorageClass, user metadata
  dynamodb.json     every item of every table, typed AttributeValue form,
                    sorted by primary key
  sqs.json          visible / in-flight message counts per queue
  postgres.json     columns and rows of every table in the golden database,
                    ordered by primary key
  meilisearch.json  every index: primary key, settings, stats and documents

Bodies are parsed so diffs are readable: gzip is detected by magic bytes and
decompressed; JSON objects are stored parsed, JSON Lines as a list of parsed
lines (with a flag for the trailing newline), other UTF-8 as text, anything
else as base64. Archived objects (GLACIER etc.) are restored after the run so
their bodies can be read; the listed storage class is captured before that.
JSON key order is not preserved (files are written with sorted
keys); list and line order is.
"""

from __future__ import annotations

import base64
import datetime as dt
import gzip
import json
import time
from decimal import Decimal

from botocore.exceptions import ClientError
from psycopg2 import sql

from . import infra

GZIP_MAGIC = b"\x1f\x8b"


def dumps(value) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def decode_body(raw: bytes) -> dict:
    out: dict = {"gzip": raw[:2] == GZIP_MAGIC}
    if out["gzip"]:
        raw = gzip.decompress(raw)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        out.update(format="base64", body=base64.b64encode(raw).decode("ascii"))
        return out
    try:
        out.update(format="json", body=json.loads(text))
        return out
    except ValueError:
        pass
    lines = text.split("\n")
    trailing_newline = text.endswith("\n")
    if trailing_newline:
        lines = lines[:-1]
    try:
        if lines and all(line.strip() for line in lines):
            out.update(
                format="jsonl",
                body=[json.loads(line) for line in lines],
                trailing_newline=trailing_newline,
            )
            return out
    except ValueError:
        pass
    out.update(format="text", body=text)
    return out


def _read_object(client, bucket: str, key: str, timeout: float = 30.0) -> dict:
    try:
        return client.get_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "InvalidObjectState":
            raise
    client.restore_object(Bucket=bucket, Key=key, RestoreRequest={"Days": 1})
    deadline = time.monotonic() + timeout
    while 'ongoing-request="false"' not in (
        client.head_object(Bucket=bucket, Key=key).get("Restore") or ""
    ):
        if time.monotonic() > deadline:
            raise TimeoutError("restore of s3://%s/%s did not finish" % (bucket, key))
        time.sleep(0.2)
    return client.get_object(Bucket=bucket, Key=key)


def capture_s3() -> dict:
    client = infra.s3()
    result: dict = {}
    for bucket in sorted(b["Name"] for b in client.list_buckets()["Buckets"]):
        objects: dict = {}
        for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket):
            for summary in page.get("Contents", []):
                key = summary["Key"]
                obj = _read_object(client, bucket, key)
                entry = decode_body(obj["Body"].read())
                entry.update(
                    content_type=obj.get("ContentType"),
                    content_encoding=obj.get("ContentEncoding"),
                    storage_class=summary.get("StorageClass", "STANDARD"),
                    metadata=obj.get("Metadata", {}),
                )
                objects[key] = entry
        result[bucket] = objects
    return result


def capture_dynamodb() -> dict:
    client = infra.dynamodb()
    result: dict = {}
    for table in sorted(client.list_tables()["TableNames"]):
        key_names = [
            k["AttributeName"]
            for k in client.describe_table(TableName=table)["Table"]["KeySchema"]
        ]
        items = []
        for page in client.get_paginator("scan").paginate(
            TableName=table, ConsistentRead=True
        ):
            items.extend(page.get("Items", []))
        items.sort(
            key=lambda item: json.dumps(
                [item.get(k) for k in key_names], sort_keys=True
            )
        )
        result[table] = {"key_schema": key_names, "items": items}
    return result


def capture_sqs() -> dict:
    client = infra.sqs()
    result: dict = {}
    for url in client.list_queues().get("QueueUrls", []):
        attrs = client.get_queue_attributes(
            QueueUrl=url,
            AttributeNames=[
                "ApproximateNumberOfMessages",
                "ApproximateNumberOfMessagesNotVisible",
            ],
        )["Attributes"]
        result[url.rsplit("/", 1)[-1]] = {
            "visible": int(attrs["ApproximateNumberOfMessages"]),
            "in_flight": int(attrs["ApproximateNumberOfMessagesNotVisible"]),
        }
    return dict(sorted(result.items()))


def _pg_value(value):
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (bytes, memoryview)):
        return base64.b64encode(bytes(value)).decode("ascii")
    return value


def capture_postgres() -> dict:
    result: dict = {}
    conn = infra.pg_connect()
    try:
        with conn.cursor() as cur:
            for table in infra.pg_tables(conn):
                cur.execute(
                    "SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = %s ORDER BY ordinal_position",
                    (table,),
                )
                columns = cur.fetchall()
                cur.execute(
                    "SELECT a.attname FROM pg_index i JOIN pg_attribute a "
                    "ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) "
                    "WHERE i.indrelid = %s::regclass AND i.indisprimary ORDER BY a.attnum",
                    (table,),
                )
                order = [r[0] for r in cur.fetchall()] or [c[0] for c in columns]
                cur.execute(
                    sql.SQL("SELECT * FROM {} ORDER BY {}").format(
                        sql.Identifier(table),
                        sql.SQL(", ").join(map(sql.Identifier, order)),
                    )
                )
                names = [d[0] for d in cur.description]
                rows = [
                    {n: _pg_value(v) for n, v in zip(names, row)}
                    for row in cur.fetchall()
                ]
                result[table] = {
                    "columns": [{"name": n, "type": t} for n, t in columns],
                    "rows": rows,
                }
    finally:
        conn.close()
    return result


def capture_meilisearch() -> dict:
    infra.wait_meili_idle()
    result: dict = {}
    indexes = infra.meili("GET", "/indexes", params={"limit": 1000})
    indexes.raise_for_status()
    for index in sorted(indexes.json().get("results", []), key=lambda i: i["uid"]):
        uid = index["uid"]
        settings_resp = infra.meili("GET", "/indexes/%s/settings" % uid)
        stats_resp = infra.meili("GET", "/indexes/%s/stats" % uid)
        settings_resp.raise_for_status()
        stats_resp.raise_for_status()
        documents = []
        offset = 0
        while True:
            page = infra.meili(
                "GET",
                "/indexes/%s/documents" % uid,
                params={"offset": offset, "limit": 1000},
            )
            page.raise_for_status()
            batch = page.json().get("results", [])
            documents.extend(batch)
            offset += len(batch)
            if not batch or offset >= page.json().get("total", 0):
                break
        primary_key = index.get("primaryKey")
        documents.sort(
            key=lambda d: json.dumps(
                d.get(primary_key) if primary_key else d, sort_keys=True
            )
        )
        result[uid] = {
            "primary_key": primary_key,
            "settings": settings_resp.json(),
            "stats": stats_resp.json(),
            "documents": documents,
        }
    return result


def capture(exit_code: int) -> dict[str, object]:
    return {
        "result.json": {"exit_code": exit_code},
        "s3.json": capture_s3(),
        "dynamodb.json": capture_dynamodb(),
        "sqs.json": capture_sqs(),
        "postgres.json": capture_postgres(),
        "meilisearch.json": capture_meilisearch(),
    }


def render(files: dict[str, object]) -> dict[str, str]:
    return {name: dumps(value) for name, value in sorted(files.items())}
