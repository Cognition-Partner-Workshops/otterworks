"""Disabled application-side billing jobs."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone

from . import Store, dunning, routes


@dataclass(frozen=True)
class JobSpec:
    name: str
    repeat_interval: str
    enabled: bool


NIGHTLY_DUNNING = JobSpec(
    name="JOB_NIGHTLY_DUNNING",
    repeat_interval="FREQ=DAILY;BYHOUR=2;BYMINUTE=0",
    enabled=False,
)


def run_nightly_dunning(store: Store, as_of: date | None = None) -> dict:
    day = as_of or datetime.now(timezone.utc).date()
    return {
        "scheduled": dunning.sp_schedule_dunning(store, day),
        "suspended": dunning.sp_suspend_overdue(store, day),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ow_billing.jobs")
    subparsers = parser.add_subparsers(dest="command")
    nightly = subparsers.add_parser("nightly-dunning")
    nightly.add_argument("--as-of", type=date.fromisoformat)
    args = parser.parse_args(argv)
    if args.command != "nightly-dunning":
        parser.error("a job command is required")
    if os.getenv("OW_BILLING_JOB_NIGHTLY_DUNNING_ENABLED") != "true":
        print(
            "JOB_NIGHTLY_DUNNING is disabled "
            "(set OW_BILLING_JOB_NIGHTLY_DUNNING_ENABLED=true to run)"
        )
        return 0
    store = routes._store()
    try:
        run_nightly_dunning(store, args.as_of)
    finally:
        store.client.close()
    return 0
