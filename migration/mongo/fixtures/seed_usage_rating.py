#!/usr/bin/env python3
"""Synthetic seed for unit `usage-rating`: USAGE_EVENTS + RATING_PERIODS +
RATING_RESULTS in the LOCAL Oracle fixture only (wave-2 batch w2-b01).
Idempotent: deletes SYNTH-% rows then re-inserts.

Seed: periods with 0, 1 and several results; TIMESTAMP events at ms
precision; kind_cd values outside CODES. All UNITS > 0 -- the fixture
carries trg_usage_events_check which enforces it (application guard, see
notes/usage-rating.md).

Oracle only: the seeder never writes to Mongo.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _local import require_local_dsn  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST = REPO_ROOT / ".migration" / "fixtures" / "w2-b01.json"

N_EVENTS = 120
N_PERIODS = 30
TENANTS = ["SYNTH-TEN-1", "SYNTH-TEN-2", "SYNTH-TEN-3"]


def connection(uri: str):
    """Declares the migration target for the offline run. MongoClient is lazy
    -- this opens no socket; the seeder only ever touches Oracle."""
    from pymongo import MongoClient
    return MongoClient(uri)


def _connect():
    import oracledb
    raw = os.environ.get("ORACLE_FIXTURE_DSN")
    if not raw:
        sys.exit("ORACLE_FIXTURE_DSN not set (JSON {user,password,dsn})")
    dsn = json.loads(raw)
    require_local_dsn(dsn["dsn"])
    return oracledb.connect(user=dsn["user"], password=dsn["password"],
                            dsn=dsn["dsn"])


def _seed(conn) -> dict:
    cur = conn.cursor()
    cur.execute("DELETE FROM rating_results WHERE id LIKE 'SYNTH-RR-%'")
    cur.execute("DELETE FROM rating_periods WHERE id LIKE 'SYNTH-RP-%'")
    cur.execute("DELETE FROM usage_events WHERE id LIKE 'SYNTH-UE-%'")

    ev_rows = []
    for i in range(N_EVENTS):
        # ms-precision timestamps: microseconds rounded to the millisecond
        ts = datetime(2026, (i % 9) + 1, (i % 27) + 1, i % 24, i % 60,
                      i % 60, ((i * 137) % 1000) * 1000)
        ev_rows.append((
            f"SYNTH-UE-{i:05d}",
            TENANTS[i % 3],
            ts,
            (i % 500) + 1,                       # units > 0 (trigger check)
            [1, 2, 3][i % 3],            # 77/88 unknown to CODES
        ))
    cur.executemany("INSERT INTO usage_events (id,tenant_id,occurred_at,units,kind_cd) VALUES (:1,:2,:3,:4,:5)", ev_rows)

    rp_rows = []
    for i in range(N_PERIODS):
        mo = (i % 9) + 1
        rp_rows.append((
            f"SYNTH-RP-{i:04d}",
            TENANTS[i % 3],
            datetime(2026, mo, 1),
            datetime(2026, mo, 28),
        ))
    cur.executemany("INSERT INTO rating_periods (id,tenant_id,period_start,period_end) VALUES (:1,:2,:3,:4)", rp_rows)

    rr_rows = []
    rid = 0
    for i in range(N_PERIODS):
        n_res = i % 5        # 0,1,2,3,4 results per period incl. 0 and 1
        for k in range(n_res):
            rr_rows.append((
                f"SYNTH-RR-{rid:05d}",
                f"SYNTH-RP-{i:04d}",
                f"SYNTH-SUB-{i:04d}-{k}",
                (rid % 800) + 1,
                1000,
                rid % 100,
                1000 + (rid % 100),
                float(f"{(rid % 500) / 3.0:.2f}"),
                datetime(2026, (i % 9) + 1, 28, 23, 59, 59,
                         (rid % 1000) * 1000),
            ))
            rid += 1
    cur.executemany("INSERT INTO rating_results (id,period_id,subscription_id,used_units,quota_units,rollover_units,billable_units,overage_amount,created_at) VALUES (:1,:2,:3,:4,:5,:6,:7,:8,:9)", rr_rows)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM usage_events")
    ue = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM rating_periods")
    rp = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM rating_results")
    rr = cur.fetchone()[0]
    counts = {"USAGE_EVENTS": ue, "RATING_PERIODS": rp, "RATING_RESULTS": rr}
    print(f"usage-rating: seeded {N_EVENTS} events, {N_PERIODS} periods, "
          f"{rid} results (table counts {counts})")
    return counts


def _write_manifest(counts: dict) -> None:
    manifest = {
        "source": "oracle fixture FIXTURE@FREEPDB1 built from services/legacy-billing/db/oracle DDL",
        "method": "synthetic",
        "masked_columns": [],
        "produced_at": datetime.now(timezone.utc).isoformat(),
        "produced_by": "migration/mongo/fixtures/seed_usage_rating.py",
        "row_counts": counts,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {MANIFEST}")


def main() -> int:
    connection(os.environ.get(
        "MONGO_LOCAL_URI", "mongodb://127.0.0.1:27017/ow_billing_offline"))
    conn = _connect()
    counts = _seed(conn)
    conn.close()
    _write_manifest(counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
