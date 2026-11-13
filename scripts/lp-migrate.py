#!/usr/bin/env python3
"""Offline legacy-portal PostgreSQL -> PostgreSQL / Aurora Data API cutover."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[1]
TABLES = {
    "announcements.announcement": ("id", "body", "created_at", "published", "title"),
    "user_preferences.user_preference": ("user_id", "email_notifications", "locale", "theme"),
    "feedback.feedback": ("id", "created_at", "message", "rating", "user_id"),
}
RESUMING = (
    "DatabaseResumingException", "is not available", "HttpEndpoint is not enabled",
    "Communications link failure", "StatementTimeoutException",
)


class MigrationError(Exception):
    pass


class Checksum:
    """SHA256(count || sum(SHA256(canonical row)) mod 2**256), independent of order."""

    def __init__(self):
        self.count = 0
        self.total = 0
        self.maximum = None

    def add(self, row):
        encoded = json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
        self.total = (self.total + int.from_bytes(hashlib.sha256(encoded).digest(), "big")) % (1 << 256)
        self.count += 1
        if isinstance(row[0], int):
            self.maximum = row[0] if self.maximum is None else max(self.maximum, row[0])

    def digest(self):
        return hashlib.sha256(str(self.count).encode() + b":" + self.total.to_bytes(32, "big")).hexdigest()

    def next_id(self):
        return 1 if self.maximum is None else self.maximum + 1


def select_sql(table, marker, limit):
    columns = TABLES[table]
    expressions = [
        "created_at::text" if c == "created_at" else c
        for c in columns
    ]
    where = "" if marker is None else f" WHERE {columns[0]} > :cursor"
    return (f"SELECT json_build_array({', '.join(expressions)})::text FROM {table}"
            f"{where} ORDER BY {columns[0]} LIMIT {limit}")


def insert_sql(table):
    columns = TABLES[table]
    values = [f"CAST(:p{i} AS timestamp without time zone)" if c == "created_at" else f":p{i}"
              for i, c in enumerate(columns)]
    return f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(values)})"


def api_parameters(parameters):
    result = []
    for name, value in parameters.items():
        if value is None:
            field = {"isNull": True}
        elif isinstance(value, bool):
            field = {"booleanValue": value}
        elif isinstance(value, int):
            field = {"longValue": value}
        else:
            field = {"stringValue": value}
        result.append({"name": name, "value": field})
    return result


class Postgres:
    page_size = 250

    def __init__(self, url, readonly=False):
        try:
            import psycopg
        except ImportError:
            raise MigrationError("Install psycopg: python3 -m pip install 'psycopg[binary]>=3.1,<4'") from None
        try:
            self.connection = psycopg.connect(url, connect_timeout=15)
            mode = "REPEATABLE READ READ ONLY" if readonly else "READ COMMITTED READ WRITE"
            self.execute(f"SET TRANSACTION ISOLATION LEVEL {mode}")
            self.execute("SET LOCAL lock_timeout = '5s'")
            self.execute("SET LOCAL statement_timeout = '120s'")
            self.execute("SET LOCAL DateStyle = 'ISO, YMD'")
        except Exception:
            if hasattr(self, "connection"):
                self.connection.close()
            raise MigrationError("PostgreSQL connection/setup failed (connection details suppressed)") from None

    def execute(self, sql, parameters=None):
        sql = re.sub(r"(?<!:):([a-z][a-z0-9]*)", r"%(\1)s", sql)
        with self.connection.cursor() as cursor:
            cursor.execute(sql, parameters or None)
            return cursor.fetchall() if cursor.description else []

    def insert(self, table, rows):
        sql = re.sub(r":(p\d+)", r"%(\1)s", insert_sql(table))
        with self.connection.cursor() as cursor:
            cursor.executemany(sql, [dict(zip((f"p{i}" for i in range(len(row))), row)) for row in rows])

    def finish(self, commit=False):
        try:
            self.connection.commit() if commit else self.connection.rollback()
        finally:
            self.connection.close()


class DataAPI:
    page_size = 25

    def __init__(self, cluster, secret, database):
        self.config = {"resourceArn": cluster, "secretArn": secret, "database": database}
        self.transaction = None
        self.transaction = self.call("begin-transaction")["transactionId"]
        try:
            self.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
            self.execute("SET LOCAL lock_timeout = '5s'")
            self.execute("SET LOCAL DateStyle = 'ISO, YMD'")
        except Exception:
            self.finish()
            raise

    def call(self, operation, **payload):
        payload = dict(self.config, **payload)
        if operation in ("commit-transaction", "rollback-transaction"):
            payload.pop("database")
        if self.transaction:
            payload["transactionId"] = self.transaction
        for attempt in range(30):
            result = subprocess.run(
                ["aws", "rds-data", operation, "--cli-input-json", "file:///dev/stdin", "--output", "json"],
                input=json.dumps(payload), text=True, capture_output=True,
                env=dict(os.environ, AWS_PAGER="", AWS_DEFAULT_REGION=os.getenv("AWS_REGION", "us-east-1")),
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
            if not any(reason in result.stderr + result.stdout for reason in RESUMING):
                code = re.search(r"An error occurred \(([A-Za-z0-9]+)\)", result.stderr)
                raise MigrationError(f"Data API {operation} failed: {code[1] if code else 'details suppressed'}")
            print(f"waiting for the cluster (attempt {attempt + 1}/30)")
            if attempt < 29:
                time.sleep(10)
        raise MigrationError("Data API cluster did not accept statements after 30 attempts")

    def execute(self, sql, parameters=None):
        result = self.call("execute-statement", sql=sql, parameters=api_parameters(parameters or {}))
        return [tuple(None if f.get("isNull") else next(iter(f.values())) for f in row)
                for row in result.get("records", [])]

    def insert(self, table, rows):
        parameters = [api_parameters({f"p{i}": value for i, value in enumerate(row)}) for row in rows]
        self.call("batch-execute-statement", sql=insert_sql(table), parameterSets=parameters)

    def finish(self, commit=False):
        if self.transaction:
            try:
                self.call("commit-transaction" if commit else "rollback-transaction")
            finally:
                self.transaction = None


def pages(database, table):
    marker = None
    while True:
        records = database.execute(select_sql(table, marker, database.page_size),
                                   {} if marker is None else {"cursor": marker})
        rows = [json.loads(record[0]) for record in records]
        if not rows:
            break
        yield rows
        marker = rows[-1][0]


def fingerprint(database, table):
    checksum = Checksum()
    for batch in pages(database, table):
        for row in batch:
            checksum.add(row)
    return checksum


def next_sequence(database, table):
    if TABLES[table][0] != "id":
        return "-"
    value, called = database.execute(f"SELECT last_value, is_called FROM {table}_id_seq")[0]
    increment = database.execute(
        "SELECT seqincrement FROM pg_sequence WHERE seqrelid = CAST(:name AS regclass)",
        {"name": table + "_id_seq"},
    )[0][0]
    return value + increment if called else value


def verify(source, target):
    print("table | source rows | target rows | source checksum | target checksum | source next | target next | expected next | result")
    success = True
    for table in TABLES:
        left, right = fingerprint(source, table), fingerprint(target, table)
        expected = left.next_id() if TABLES[table][0] == "id" else "-"
        source_next, target_next = next_sequence(source, table), next_sequence(target, table)
        matches = left.count == right.count and left.digest() == right.digest() and expected == target_next
        print(f"{table} | {left.count} | {right.count} | {left.digest()} | {right.digest()} | "
              f"{source_next} | {target_next} | {expected} | {'PASS' if matches else 'FAIL'}")
        success = success and matches
    if not success:
        raise MigrationError("Verification FAILED: content, count or next sequence mismatch")
    print("Verification PASSED")


def migrate(source, target, truncate=False, dry_run=False):
    occupied = [table for table in TABLES if target.execute(f"SELECT EXISTS (SELECT 1 FROM {table})")[0][0]]
    if occupied and not truncate:
        raise MigrationError("Refusing non-empty target; use --truncate to explicitly replace all three tables")
    if dry_run:
        for table in TABLES:
            count = source.execute(f"SELECT count(*) FROM {table}")[0][0]
            print(f"DRY RUN {table}: copy {count} rows" + (" (truncate target first)" if truncate else ""))
        print("DRY RUN: no rows or sequences changed; no verification of uncopied data")
        return
    if truncate:
        target.execute("TRUNCATE " + ", ".join(TABLES) + " RESTART IDENTITY")
    for table in TABLES:
        checksum = Checksum()
        for batch in pages(source, table):
            for offset in range(0, len(batch), target.page_size):
                target.insert(table, batch[offset:offset + target.page_size])
            for row in batch:
                checksum.add(row)
        if TABLES[table][0] == "id":
            value = checksum.next_id()
            target.execute(f"ALTER SEQUENCE {table}_id_seq MINVALUE {min(1, value)} RESTART WITH {value}")
        print(f"Copied {table}: {checksum.count} rows")
    verify(source, target)


class Transcript:
    def __init__(self, console, file):
        self.console, self.file = console, file

    def write(self, text):
        self.console.write(text)
        self.file.write(text)
        self.flush()

    def flush(self):
        self.console.flush()
        self.file.flush()


def run(args):
    source = target = None
    try:
        source = Postgres(args.source_url, readonly=True)
        target = (Postgres(args.target_url) if args.target_url else
                  DataAPI(os.environ["CLUSTER_ARN"], os.environ["SECRET_ARN"], os.environ["DATABASE"]))
        identity_sql = "SELECT current_database(), inet_server_addr()::text, inet_server_port()"
        if source.execute(identity_sql) == target.execute(identity_sql):
            raise MigrationError("Source and target must be different databases")
        target.execute("LOCK TABLE " + ", ".join(TABLES) + " IN ACCESS EXCLUSIVE MODE NOWAIT")
        if args.command == "verify":
            verify(source, target)
        else:
            migrate(source, target, args.truncate, args.dry_run)
        target.finish(commit=not args.dry_run and args.command == "migrate")
        target = None
    finally:
        if target:
            target.finish()
        if source:
            source.finish()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("migrate", "verify"))
    parser.add_argument("--run", default=os.getenv("RUN"))
    parser.add_argument("--source-url", default=os.getenv("SOURCE_URL"))
    parser.add_argument("--target-url", default=os.getenv("TARGET_URL"))
    parser.add_argument("--truncate", action="store_true", default=os.getenv("TRUNCATE") == "1")
    parser.add_argument("--dry-run", action="store_true", default=os.getenv("DRY_RUN") == "1")
    args = parser.parse_args(argv)
    if not args.run or not re.fullmatch(r"lp-[0-9]{8}-[a-z0-9]{2}", args.run):
        parser.error("RUN must look like lp-20261005-rh")
    if not args.source_url:
        parser.error("SOURCE_URL or --source-url is required")
    if not args.target_url and not all(os.getenv(k) for k in ("CLUSTER_ARN", "SECRET_ARN", "DATABASE")):
        parser.error("Set TARGET_URL or CLUSTER_ARN, SECRET_ARN and DATABASE")
    if args.command == "verify" and (args.truncate or args.dry_run):
        parser.error("verify does not accept --truncate / --dry-run")
    folder = ROOT / ".demo" / "legacy-portal" / args.run
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    path = folder / f"{args.command}-{stamp}.log"
    old_stdout = sys.stdout
    with path.open("x") as file:
        sys.stdout = Transcript(old_stdout, file)
        code = 0
        try:
            print(f"# lp-{args.command} run={args.run} started {stamp}")
            run(args)
        except Exception as error:
            # Driver diagnostics can include credentials, SQL and customer row values.
            print(f"ERROR: {error if isinstance(error, MigrationError) else type(error).__name__ + ' (details suppressed)'}")
            code = 1
        finally:
            print(f"# lp-{args.command} finished exit={code}")
            print(f"# transcript {path.relative_to(ROOT)}")
            sys.stdout = old_stdout
    return code


if __name__ == "__main__":
    sys.exit(main())
