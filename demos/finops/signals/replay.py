#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
import sqlite3
from contextlib import closing

from .forwarder import forward, webhook_sender


def sqlite_claims(ledger):
    ledger.execute("CREATE TABLE IF NOT EXISTS deliveries (dedupe_key TEXT PRIMARY KEY)")

    def claim(key):
        with ledger:
            result = ledger.execute("INSERT OR IGNORE INTO deliveries VALUES (?)", (key,))
        return result.rowcount == 1

    def release(key):
        with ledger:
            ledger.execute("DELETE FROM deliveries WHERE dedupe_key = ?", (key,))

    return claim, release


def main():
    parser = argparse.ArgumentParser(description="Forward a signed synthetic Cost Anomaly notification")
    parser.add_argument("fixture", nargs="+", type=Path)
    parser.add_argument("--state", required=True, type=Path, help="SQLite delivery ledger outside the repo")
    parser.add_argument("--run-tag", default="FINOPS_20261128")
    parser.add_argument("--environment", default="dev")
    args = parser.parse_args()

    url = os.environ.get("DEVIN_WEBHOOK_URL")
    secret = os.environ.get("DEVIN_WEBHOOK_SECRET")
    key = os.environ.get("FINOPS_REPLAY_KEY")
    if not (url and secret and key):
        parser.error("Set DEVIN_WEBHOOK_URL, DEVIN_WEBHOOK_SECRET and FINOPS_REPLAY_KEY")
    send = webhook_sender(url, secret, key.encode())
    failed = False
    with closing(sqlite3.connect(args.state)) as ledger:
        claim, release = sqlite_claims(ledger)
        for path in args.fixture:
            receipts = forward(
                json.loads(path.read_text()), claim, send, release=release,
                run_tag=args.run_tag, environment=args.environment, source="signed-sns-replay",
            )
            for receipt in receipts:
                print(json.dumps(receipt))
                failed |= receipt["result"] == "delivery_unconfirmed"
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
