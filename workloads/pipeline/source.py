from __future__ import annotations

import argparse
import hashlib
import json
import os
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parent
SOURCE_SCHEMA = "otterworks_sfext_20261105a"
TABLES = {
    "AUTH_USER_STATE_HISTORY": (
        "user_state_history",
        "id",
        {
            "id": "NUMBER(38,0)",
            "user_id": "VARCHAR(36)",
            "effective_at": "TIMESTAMP_NTZ",
            "created_at": "TIMESTAMP_NTZ",
            "last_login_at": "TIMESTAMP_NTZ",
        },
    ),
    "ADMIN_USER_STATE_HISTORY": (
        "admin_user_state_history",
        "id",
        {
            "id": "NUMBER(38,0)",
            "user_id": "VARCHAR(36)",
            "effective_at": "TIMESTAMP_NTZ",
            "status": "VARCHAR",
        },
    ),
    "AUTH_USERS": (
        "users",
        "id",
        {
            "id": "VARCHAR(36)",
            "created_at": "TIMESTAMP_NTZ",
            "last_login_at": "TIMESTAMP_NTZ",
        },
    ),
    "ADMIN_ADMIN_USERS": (
        "admin_users",
        "id",
        {"id": "VARCHAR(36)", "email": "VARCHAR(255)", "status": "VARCHAR"},
    ),
    "ADMIN_STORAGE_QUOTAS": (
        "storage_quotas",
        "user_id",
        {
            "user_id": "VARCHAR(36)",
            "quota_bytes": "NUMBER(38,0)",
            "used_bytes": "NUMBER(38,0)",
            "tier": "VARCHAR",
            "updated_at": "TIMESTAMP_NTZ",
        },
    ),
    "DOCUMENT_DOCUMENTS": (
        "documents",
        "id",
        {
            "id": "VARCHAR(36)",
            "title": "VARCHAR(500)",
            "owner_id": "VARCHAR(36)",
            "is_deleted": "BOOLEAN",
            "is_template": "BOOLEAN",
        },
    ),
    "DOCUMENT_DOCUMENT_VERSIONS": (
        "document_versions",
        "id",
        {
            "id": "VARCHAR(36)",
            "created_by": "VARCHAR(36)",
            "created_at": "TIMESTAMP_NTZ",
        },
    ),
    "ANALYTICS_ANALYTICS_EVENTS": (
        "analytics_events",
        "event_id",
        {
            "event_id": "VARCHAR",
            "event_type": "VARCHAR",
            "user_id": "VARCHAR(36)",
            "metadata": "VARCHAR",
            "occurred_at": "NUMBER(38,0)",
        },
    ),
}


def seed(conn):
    with conn, conn.cursor() as cur:
        cur.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                sql.Identifier(SOURCE_SCHEMA)
            )
        )
        cur.execute(
            sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(SOURCE_SCHEMA))
        )
        cur.execute((ROOT / "source.sql").read_text())
        cur.execute("SELECT count(*) FROM users")
        if cur.fetchone()[0] == 0:
            cur.execute((ROOT / "seed.sql").read_text())
        else:
            cur.execute(
                "SELECT EXISTS(SELECT 1 FROM user_state_history), "
                "EXISTS(SELECT 1 FROM admin_user_state_history)"
            )
            if cur.fetchone() != (True, True):
                raise ValueError(
                    "source history must start before source mutations; "
                    "current rows cannot reconstruct historical state"
                )
        cur.execute((ROOT / "generate.sql").read_text())
        cur.execute(
            "SELECT (SELECT count(*) FROM users), (SELECT count(*) FROM documents)"
        )
        assert cur.fetchone() == (2000, 50000), (
            "source must contain exactly 2,000 customers and 50,000 documents"
        )


def export(conn, output: Path, snapshot_date: date, exported_at: datetime):
    output.mkdir(parents=True, exist_ok=True)
    tables = {}
    # Source state and its history share one consistent snapshot.
    with conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cur.execute(
            sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(SOURCE_SCHEMA))
        )
        cur.execute("SET TIME ZONE 'UTC'")
        for target, (table, key, columns) in TABLES.items():
            cur.execute(
                sql.SQL(
                    "SELECT row_to_json(t) FROM (SELECT {} FROM {} ORDER BY {}) t"
                ).format(
                    sql.SQL(",").join(map(sql.Identifier, columns)),
                    sql.Identifier(table),
                    sql.Identifier(key),
                )
            )
            tables[target] = [row[0] for row in cur.fetchall()]
            (output / f"{target.lower()}.json").write_text(
                json.dumps(tables[target], sort_keys=True) + "\n"
            )
    payload = {
        "snapshot_date": snapshot_date.isoformat(),
        "exported_at": exported_at.astimezone(timezone.utc).isoformat(),
        "tables": tables,
    }
    content = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(content.encode()).hexdigest()
    bundle = output / f"snapshot_{digest}.json"
    bundle.write_text(content + "\n")
    print(
        json.dumps(
            {
                "snapshot_date": str(snapshot_date),
                "sha256": digest,
                "rows": {k: len(v) for k, v in tables.items()},
            }
        )
    )
    return bundle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--snapshot-date",
        type=date.fromisoformat,
        default=datetime.now(timezone.utc).date(),
    )
    args = parser.parse_args()
    with closing(psycopg2.connect(os.environ["POSTGRES_DSN"])) as conn:
        if args.seed:
            seed(conn)
        export(conn, args.output, args.snapshot_date, datetime.now(timezone.utc))


if __name__ == "__main__":
    main()
