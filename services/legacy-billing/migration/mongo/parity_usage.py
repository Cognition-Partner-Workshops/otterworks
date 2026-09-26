#!/usr/bin/env python3
"""Unit u-04-usage-audit Tier-4 parity replay: Oracle facade reads vs mongo backend.

For every tenant present in USAGE_EVENTS, replays the two read paths of
GET /api/v1/billing/usage over the fixture's full date range:

* events  : the facade's literal SQL (facade.py usage()) through backends.oracle.rows
* summary : pkg_rating.fn_usage_summary through backends.oracle.rows

and compares the JSON bytes with backends.mongo.usage_events / usage_summary.
One Oracle connection is used for the whole replay (source concurrency 1).

    env -u MONGODB_ATLAS_URI python3 services/legacy-billing/migration/mongo/parity_usage.py \
        --source-dsn-secret OW_BILLING_FIXTURE_DSN --target-uri-secret MONGO_LOCAL_URI \
        --target-db ow_billing_migration --start 2026-02-01 --end 2026-02-28 --out parity.json

Secrets are read from the environment by NAME only. Read-only on both sides.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import oracledb

APP_DIR = Path(__file__).resolve().parents[2] / "app"
sys.path.insert(0, str(APP_DIR))

from backends import mongo, oracle


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-dsn-secret", required=True)
    ap.add_argument("--target-uri-secret", required=True)
    ap.add_argument("--target-db", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    conn_args = json.loads(os.environ[args.source_dsn_secret])
    os.environ["MONGO_URI"] = os.environ[args.target_uri_secret]
    os.environ["MONGO_DB"] = args.target_db
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)

    checks = 0
    mismatches = []
    tenants = 0
    events_total = 0
    with oracledb.connect(user=conn_args["user"], password=conn_args["password"],
                          dsn=conn_args["dsn"]) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT tenant_id FROM usage_events ORDER BY tenant_id")
            tenant_ids = [row[0] for row in cur]
        for tenant_id in tenant_ids:
            tenants += 1
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT * FROM (
                           SELECT u.id, u.occurred_at, u.units, c.code_desc AS kind
                             FROM usage_events u
                             JOIN codes c
                               ON c.code_type = 'USAGE_KIND'
                              AND c.code_val = u.kind_cd
                            WHERE u.tenant_id = :1
                              AND u.occurred_at >= :2
                              AND u.occurred_at < TO_DATE(:3, 'YYYY-MM-DD') + 1
                            ORDER BY u.occurred_at DESC, u.id DESC
                       ) WHERE ROWNUM <= 50""",
                    (tenant_id, start, end.isoformat()),
                )
                src_events = oracle.rows(cur)
            with conn.cursor() as cur:
                ref = cur.callfunc("pkg_rating.fn_usage_summary", oracledb.CURSOR,
                                   [tenant_id, start, end])
                src_summary = oracle.rows(ref)
            tgt_events = mongo.usage_events(tenant_id, start, end)
            tgt_summary = mongo.usage_summary(tenant_id, start, end)
            events_total += len(src_events)
            for name, src, tgt in (("events", src_events, tgt_events),
                                   ("summary", src_summary, tgt_summary)):
                checks += 1
                src_json = json.dumps(src, sort_keys=True)
                tgt_json = json.dumps(tgt, sort_keys=True)
                if src_json != tgt_json:
                    mismatches.append({"tenant_index": tenants, "check": name,
                                       "source_len": len(src), "target_len": len(tgt)})

    result = {
        "unit": "u-04-usage-audit",
        "tier": 4,
        "name": "app_parity_usage_reads",
        "mode": "fixture",
        "target_class": "local",
        "range": [args.start, args.end],
        "tenants": tenants,
        "checks_run": checks,
        "source_event_rows_compared": events_total,
        "mismatches": len(mismatches),
        "mismatch_detail": mismatches[:50],
        "passed": not mismatches,
        "non_merge_evidence": True,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=1) + "\n")
    print(f"parity {'PASS' if result['passed'] else 'FAIL'}: tenants={tenants} "
          f"checks={checks} mismatches={len(mismatches)}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
