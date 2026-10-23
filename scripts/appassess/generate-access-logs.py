#!/usr/bin/env python3
"""Write 90 days of synthetic access logs per portfolio application.

Rows are deterministic (seeded from the application name and the day) and
carry "synthetic": true. Output goes to a local directory and, with --s3,
under s3://<bucket>/appassess/<run token>/access-logs/<application>/.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path

END_DATE = dt.date(2026, 10, 22)

PROFILES = {
    "legacy-portal": {"source": "legacy-portal", "daily": 1800, "paths": ["/portal/accounts", "/portal/orders", "/portal/catalog", "/portal/login"]},
    "report-service": {"source": "api-gateway", "daily": 140, "paths": ["/api/v1/reports", "/api/v1/reports/scheduled"], "status": 404},
    "legacy-billing": {"source": "legacy-billing", "daily": 650, "paths": ["/billing/invoices", "/billing/usage", "/billing/dunning"]},
    "db2-retention-archive": {"source": "db2-archive-batch", "daily": 24, "paths": ["DOCARCH:SELECT", "FILEAUD:SELECT"]},
    "legacy-share-links": {"source": "legacy-share-links", "daily": 0, "paths": []},
}

AGENTS = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5)", "okhttp/4.12.0"]


def rows_for(app: str, day: dt.date):
    profile = PROFILES[app]
    rng = random.Random(hashlib.sha256(f"{app}:{day.isoformat()}".encode()).hexdigest())
    for _ in range(profile["daily"]):
        ts = dt.datetime.combine(day, dt.time()) + dt.timedelta(seconds=rng.randrange(86400))
        yield {
            "ts": ts.isoformat() + "Z",
            "source": profile["source"],
            "client_ip": f"10.20.{rng.randrange(256)}.{rng.randrange(1, 255)}",
            "method": "GET",
            "path": rng.choice(profile["paths"]),
            "status": profile.get("status", rng.choice([200] * 19 + [500])),
            "user_agent": rng.choice(AGENTS),
            "synthetic": True,
        }
    if app == "legacy-share-links":
        yield {
            "ts": dt.datetime.combine(day, dt.time(2, 15, 3)).isoformat() + "Z",
            "source": "legacy-share-links",
            "client_ip": "10.20.9.14",
            "method": "POST",
            "path": "/share-links/admin/purge-expired",
            "status": 200,
            "user_agent": "otterworks-nightly/2.3",
            "synthetic": True,
        }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="build/appassess/access-logs")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--apps", type=int, default=5, help="cap on applications, in inventory order")
    ap.add_argument("--run-token", default="local")
    ap.add_argument("--bucket", default="otterworks-data-lake-dev")
    ap.add_argument("--s3", action="store_true", help="upload after writing")
    args = ap.parse_args()

    out = Path(args.out)
    apps = list(PROFILES)[: args.apps]
    for app in apps:
        for offset in range(args.days):
            day = END_DATE - dt.timedelta(days=offset)
            path = out / app / f"{day:%Y/%m/%d}.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            rows = sorted(rows_for(app, day), key=lambda r: r["ts"])
            path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    print(f"wrote {len(apps)} applications x {args.days} days under {out}")

    if args.s3:
        dest = f"s3://{args.bucket}/appassess/{args.run_token}/access-logs/"
        subprocess.run(["aws", "s3", "sync", "--only-show-errors", str(out), dest], check=True)
        print(f"uploaded to {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
