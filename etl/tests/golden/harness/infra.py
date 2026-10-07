"""Local infrastructure: readiness, harness-only resources, reset and seeding.

The services come from docker-compose.infra.yml (`make infra-up`). This module
only adds what the legacy scripts need beyond scripts/localstack-init.sh and
never edits the shared init scripts. Reset wipes the *contents* of every S3
bucket, DynamoDB table, SQS queue and MeiliSearch index in the local stack and
of every table in the dedicated Postgres database, so each run starts from the
scenario seed alone.
"""

from __future__ import annotations

import gzip
import json
import time
from decimal import Decimal

import boto3
import psycopg2
import requests
from psycopg2 import sql

from . import settings


class InfraNotReady(RuntimeError):
    pass


def _aws(service: str):
    return boto3.client(
        service,
        endpoint_url=settings.LOCALSTACK_URL,
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY,
        aws_secret_access_key=settings.AWS_SECRET_KEY,
    )


def s3():
    return _aws("s3")


def dynamodb():
    return _aws("dynamodb")


def sqs():
    return _aws("sqs")


def pg_connect(dbname: str = settings.PG_DB):
    return psycopg2.connect(
        host=settings.PG_HOST,
        port=settings.PG_PORT,
        dbname=dbname,
        user=settings.PG_USER,
        password=settings.PG_PASSWORD,
        connect_timeout=5,
    )


def meili(method: str, path: str, **kwargs):
    headers = {"Authorization": "Bearer %s" % settings.MEILI_API_KEY}
    resp = requests.request(
        method, settings.MEILI_URL + path, headers=headers, timeout=30, **kwargs
    )
    return resp


# ---------------------------------------------------------------- readiness


def wait_ready(timeout: float = 120.0) -> None:
    deadline = time.monotonic() + timeout
    problems: dict[str, str] = {}
    while time.monotonic() < deadline:
        problems = {}
        try:
            init = requests.get(
                settings.LOCALSTACK_URL + "/_localstack/init/ready", timeout=5
            ).json()
            if not init.get("completed"):
                problems["localstack"] = "init scripts still running"
        except Exception as exc:  # noqa: BLE001
            problems["localstack"] = repr(exc)
        try:
            pg_connect(settings.PG_ADMIN_DB).close()
        except Exception as exc:  # noqa: BLE001
            problems["postgres"] = repr(exc)
        try:
            if meili("GET", "/health").json().get("status") != "available":
                problems["meilisearch"] = "not available"
        except Exception as exc:  # noqa: BLE001
            problems["meilisearch"] = repr(exc)
        if not problems:
            return
        time.sleep(2)
    raise InfraNotReady(
        "local infra not ready (%s); start it with `make infra-up`"
        % "; ".join("%s: %s" % kv for kv in sorted(problems.items()))
    )


# ------------------------------------------------------- harness resources


def ensure_resources() -> None:
    client = sqs()
    for queue in settings.HARNESS_QUEUES:
        client.create_queue(QueueName=queue)

    ddb = dynamodb()
    existing = set(ddb.list_tables()["TableNames"])
    for table, keys in settings.HARNESS_TABLES.items():
        if table in existing:
            continue
        ddb.create_table(
            TableName=table,
            AttributeDefinitions=[
                {"AttributeName": n, "AttributeType": t} for n, t, _ in keys
            ],
            KeySchema=[{"AttributeName": n, "KeyType": k} for n, _, k in keys],
            BillingMode="PAY_PER_REQUEST",
        )
        ddb.get_waiter("table_exists").wait(TableName=table)

    bucket_client = s3()
    buckets = {b["Name"] for b in bucket_client.list_buckets()["Buckets"]}
    for bucket in settings.HARNESS_BUCKETS:
        if bucket not in buckets:
            bucket_client.create_bucket(Bucket=bucket)

    admin = pg_connect(settings.PG_ADMIN_DB)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (settings.PG_DB,))
        if cur.fetchone() is None:
            cur.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(settings.PG_DB))
            )
    admin.close()
    with pg_connect() as conn, conn.cursor() as cur:
        for name in settings.HARNESS_PG_DDL:
            cur.execute((settings.SQL_DIR / name).read_text())
    conn.close()


# -------------------------------------------------------------------- reset


def wait_meili_idle(timeout: float = 120.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pending = meili(
            "GET", "/tasks", params={"statuses": "enqueued,processing", "limit": 1}
        )
        pending.raise_for_status()
        if pending.json().get("total", len(pending.json().get("results", []))) == 0:
            return
        time.sleep(0.2)
    raise TimeoutError("MeiliSearch still has pending tasks")


def pg_tables(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name"
        )
        return [r[0] for r in cur.fetchall()]


def reset() -> None:
    bucket_client = s3()
    for bucket in bucket_client.list_buckets()["Buckets"]:
        paginator = bucket_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket["Name"]):
            keys = [{"Key": o["Key"]} for o in page.get("Contents", [])]
            if keys:
                bucket_client.delete_objects(
                    Bucket=bucket["Name"], Delete={"Objects": keys}
                )

    ddb = dynamodb()
    for table in ddb.list_tables()["TableNames"]:
        key_names = [
            k["AttributeName"]
            for k in ddb.describe_table(TableName=table)["Table"]["KeySchema"]
        ]
        paginator = ddb.get_paginator("scan")
        for page in paginator.paginate(
            TableName=table,
            ProjectionExpression=", ".join("#k%d" % i for i in range(len(key_names))),
            ExpressionAttributeNames={"#k%d" % i: n for i, n in enumerate(key_names)},
        ):
            for item in page.get("Items", []):
                ddb.delete_item(TableName=table, Key=item)

    queue_client = sqs()
    for url in queue_client.list_queues().get("QueueUrls", []):
        queue_client.purge_queue(QueueUrl=url)

    with pg_connect() as conn, conn.cursor() as cur:
        for table in pg_tables(conn):
            cur.execute(
                sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(
                    sql.Identifier(table)
                )
            )
    conn.close()

    indexes = meili("GET", "/indexes", params={"limit": 1000})
    indexes.raise_for_status()
    for index in indexes.json().get("results", []):
        meili("DELETE", "/indexes/%s" % index["uid"]).raise_for_status()
    wait_meili_idle()


# --------------------------------------------------------------------- seed


def _encode_body(entry: dict) -> bytes:
    fmt = entry.get(
        "format", "json" if not isinstance(entry.get("body"), str) else "text"
    )
    body = entry.get("body", "")
    if fmt == "json":
        raw = json.dumps(body).encode("utf-8")
    elif fmt == "jsonl":
        raw = "".join(json.dumps(line) + "\n" for line in body).encode("utf-8")
    elif fmt == "text":
        raw = body.encode("utf-8")
    else:
        raise ValueError("unknown s3 seed format %r" % fmt)
    if entry.get("gzip"):
        raw = gzip.compress(raw, mtime=0)
    return raw


def _to_dynamo(value):
    return json.loads(json.dumps(value), parse_float=Decimal, parse_int=Decimal)


def seed(data: dict) -> None:
    queue_client = sqs()
    for queue, messages in data.get("sqs", {}).items():
        url = queue_client.get_queue_url(QueueName=queue)["QueueUrl"]
        for message in messages:
            body = message if isinstance(message, str) else json.dumps(message)
            queue_client.send_message(QueueUrl=url, MessageBody=body)

    resource = boto3.resource(
        "dynamodb",
        endpoint_url=settings.LOCALSTACK_URL,
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY,
        aws_secret_access_key=settings.AWS_SECRET_KEY,
    )
    for table, items in data.get("dynamodb", {}).items():
        handle = resource.Table(table)
        for item in items:
            handle.put_item(Item=_to_dynamo(item))

    bucket_client = s3()
    for entry in data.get("s3", []):
        kwargs = {
            "Bucket": entry["bucket"],
            "Key": entry["key"],
            "Body": _encode_body(entry),
        }
        if entry.get("content_type"):
            kwargs["ContentType"] = entry["content_type"]
        if entry.get("storage_class"):
            kwargs["StorageClass"] = entry["storage_class"]
        bucket_client.put_object(**kwargs)

    if data.get("postgres"):
        with pg_connect() as conn, conn.cursor() as cur:
            for table, rows in data["postgres"].items():
                for row in rows:
                    columns = list(row)
                    cur.execute(
                        sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                            sql.Identifier(table),
                            sql.SQL(", ").join(map(sql.Identifier, columns)),
                            sql.SQL(", ").join(sql.Placeholder() * len(columns)),
                        ),
                        [row[c] for c in columns],
                    )
        conn.close()
