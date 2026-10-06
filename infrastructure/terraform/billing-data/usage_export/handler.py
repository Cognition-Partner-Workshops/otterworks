"""Export billing usage from the run database to S3, one partition per month.

The private subnets of the shared instance have no NAT and no VPC endpoints, so
this function runs outside the VPC (decision d-export-network = relay): it reads
the run's login credential from Secrets Manager, invokes the in-VPC sql-runner
with the credential in the payload, and writes what comes back to

    s3://<bucket>/usage/period=<yyyy-mm>/part-00000.csv.gz

as headerless gzip CSV with the columns in USAGE_COLUMNS. Each run overwrites
the partitions it exports (put, then delete any other object under the prefix),
so reruns are idempotent. A period without usage still gets a partition: a
part-00000.csv.gz holding zero rows. A JSON manifest per period goes to
manifests/usage/period=<yyyy-mm>.json, outside the table location.

Event:
  {}                                  every period with usage, plus the previous
                                      calendar month (UTC) even when it is empty
  {"periods": ["2026-02", "2026-09"]} exactly these periods

The credential is never logged or returned.
"""

import csv
import datetime as dt
import gzip
import io
import json
import os
import re

import boto3

BUCKET = os.environ["USAGE_BUCKET"]
SECRET_ID = os.environ["DB_SECRET_ID"]
SQL_FUNCTION = os.environ["SQL_FUNCTION"]
DATA_PREFIX = os.environ.get("DATA_PREFIX", "usage")
MANIFEST_PREFIX = os.environ.get("MANIFEST_PREFIX", "manifests/usage")
PART = "part-00000.csv.gz"

USAGE_COLUMNS = ["event_id", "tenant_id", "kind", "units", "occurred_at", "usage_date"]
PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

# occurred_at is timestamptz; it is exported as a UTC timestamp
# (yyyy-mm-dd hh:mm:ss.ffffff) together with its UTC date, the value
# fn_usage_summary groups on under the instance's UTC session time zone.
USAGE_SQL = """
SELECT u.id::text,
       u.tenant_id::text,
       u.kind,
       u.units,
       to_char(u.occurred_at AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS.US'),
       to_char((u.occurred_at AT TIME ZONE 'UTC')::date, 'YYYY-MM-DD')
FROM billing.usage_events u
WHERE u.occurred_at >= ('{start}'::date)::timestamp AT TIME ZONE 'UTC'
  AND u.occurred_at <  ('{end}'::date)::timestamp AT TIME ZONE 'UTC'
ORDER BY u.occurred_at, u.id
"""

PERIODS_SQL = """
SELECT DISTINCT to_char(occurred_at AT TIME ZONE 'UTC', 'YYYY-MM') AS period
FROM billing.usage_events
ORDER BY 1
"""

_secrets = boto3.client("secretsmanager")
_lambda = boto3.client("lambda")
_s3 = boto3.client("s3")


def _db():
    secret = json.loads(_secrets.get_secret_value(SecretId=SECRET_ID)["SecretString"])
    return {
        "host": secret["host"], "port": secret["port"], "dbname": secret["dbname"],
        "user": secret["username"], "password": secret["password"],
    }


def _query(db, name, sql):
    response = _lambda.invoke(
        FunctionName=SQL_FUNCTION,
        Payload=json.dumps({"db": db, "op": "query", "queries": [{"name": name, "sql": sql}]}).encode(),
    )
    body = json.loads(response["Payload"].read())
    if response.get("FunctionError") or "errorMessage" in body:
        raise RuntimeError(f"{SQL_FUNCTION} failed: {body.get('errorMessage', 'unknown error')}")
    rows = body["results"][name]
    if isinstance(rows, dict):
        raise RuntimeError(f"query {name} failed: {rows.get('error')}")
    return rows


def _bounds(period):
    year, month = map(int, period.split("-"))
    start = dt.date(year, month, 1)
    end = dt.date(year + (month == 12), month % 12 + 1, 1)
    return start, end


def _previous_month(today):
    first = today.replace(day=1)
    return (first - dt.timedelta(days=1)).strftime("%Y-%m")


def _periods(event, db):
    requested = event.get("periods")
    if requested:
        bad = [p for p in requested if not isinstance(p, str) or not PERIOD_RE.match(p)]
        if bad:
            raise ValueError(f"periods must be yyyy-mm: {bad}")
        return sorted(set(requested))
    present = {row[0] for row in _query(db, "periods", PERIODS_SQL)}
    present.add(_previous_month(dt.datetime.now(dt.timezone.utc).date()))
    return sorted(present)


def _gzip_csv(rows):
    text = io.StringIO()
    writer = csv.writer(text, lineterminator="\n")
    writer.writerows(rows)
    return gzip.compress(text.getvalue().encode(), mtime=0)


def _overwrite_partition(period, body):
    prefix = f"{DATA_PREFIX}/period={period}/"
    key = prefix + PART
    _s3.put_object(Bucket=BUCKET, Key=key, Body=body, ContentType="text/csv", ContentEncoding="gzip")
    stale = []
    for page in _s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=prefix):
        stale += [{"Key": o["Key"]} for o in page.get("Contents", []) if o["Key"] != key]
    for i in range(0, len(stale), 1000):
        _s3.delete_objects(Bucket=BUCKET, Delete={"Objects": stale[i:i + 1000], "Quiet": True})
    return key, len(stale)


def handler(event, _context):
    event = event or {}
    db = _db()
    exported = []
    for period in _periods(event, db):
        start, end = _bounds(period)
        rows = _query(db, f"usage_{period}", USAGE_SQL.format(start=start, end=end))
        key, removed = _overwrite_partition(period, _gzip_csv(rows))
        manifest = {
            "period": period,
            "key": f"s3://{BUCKET}/{key}",
            "format": "csv.gz, no header",
            "columns": USAGE_COLUMNS,
            "rows": len(rows),
            "units": sum(int(r[3]) for r in rows),
            "exported_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        }
        _s3.put_object(
            Bucket=BUCKET, Key=f"{MANIFEST_PREFIX}/period={period}.json",
            Body=json.dumps(manifest, indent=2).encode(), ContentType="application/json",
        )
        exported.append({k: manifest[k] for k in ("period", "key", "rows", "units")} | {"replaced": removed})
    print(json.dumps({"bucket": BUCKET, "exported": exported}))
    return {"bucket": BUCKET, "exported": exported}
