"""Shared pipeline checks; retained staged files define the current feed set."""
import argparse
from dataclasses import dataclass
import json
import os
from pathlib import PurePosixPath

from sf import connect

RUN = "sfx-d1110"
MODEL = "stg_billing__usage_daily"


@dataclass
class Thresholds:
    row_drop: float = 0.05
    null_ratio: float = 0.01
    load_errors: int = 0
    lookback_hours: int = 24

    def __post_init__(self):
        if not (0 <= self.row_drop <= 1 and 0 <= self.null_ratio <= 1):
            raise ValueError("ratio thresholds must be between zero and one")
        if self.load_errors < 0 or not 1 <= self.lookback_hours <= 336:
            raise ValueError("load errors must be nonnegative; lookback must be 1–336 hours")


def add_arguments(parser):
    parser.add_argument("--row-drop", type=float, default=float(os.getenv("SFX_ROW_DROP_THRESHOLD", ".05")))
    parser.add_argument("--null-ratio", type=float, default=float(os.getenv("SFX_NULL_RATIO_THRESHOLD", ".01")))
    parser.add_argument("--load-errors", type=int, default=int(os.getenv("SFX_LOAD_ERROR_THRESHOLD", "0")))
    parser.add_argument("--lookback-hours", type=int, default=int(os.getenv("SFX_LOOKBACK_HOURS", "24")))


def thresholds(args):
    return Thresholds(args.row_drop, args.null_ratio, args.load_errors, args.lookback_hours)


def evaluate(days, history, retained_files, limits):
    latest = days[0] if days else None
    previous = days[1] if len(days) > 1 else None
    day = str(latest[0]) if latest else None
    file = f"pipeline/{day}.csv" if day else None
    rows = int(latest[1]) if latest else 0
    prior = int(previous[1]) if previous else 0
    drop = max(0, 1 - rows / prior) if prior else 0
    ratios = {name: int(latest[index] or 0) / rows if rows else 0
              for name, index in (("amount", 2), ("currency_code", 3))}
    # COPY_HISTORY is newest first: a successful replay supersedes an old failure.
    current = {}
    for filename, status, errors, loaded_at in history:
        normalized = "pipeline/" + PurePosixPath(filename).name
        if normalized in retained_files:
            current.setdefault(normalized, (status, int(errors or 0)))
    failures = [(name, status, errors) for name, (status, errors) in current.items()
                if status.upper().replace(" ", "_") != "LOADED" or errors > 0]
    errors = sum(item[2] for item in failures)
    failed_status = any(status.upper().replace(" ", "_") != "LOADED" for _, status, _ in failures)
    checks = {
        "load_failure": {"value": errors, "threshold": limits.load_errors,
                         "firing": failed_status or errors > limits.load_errors,
                         "day": PurePosixPath(failures[0][0]).stem if failures else day,
                         "file": failures[0][0] if failures else file},
        "row_count_drop": {"value": drop, "threshold": limits.row_drop,
                           "firing": drop > limits.row_drop, "day": day, "file": file},
        "null_spike": {"value": max(ratios.values()), "threshold": limits.null_ratio,
                       "firing": max(ratios.values()) > limits.null_ratio,
                       "day": day, "file": file, "columns": ratios},
    }
    return {"checks": checks, "rows": {"latest": rows, "previous": prior},
            "days": {"latest": day, "previous": str(previous[0]) if previous else None},
            "null_ratios": ratios, "load_errors": errors}


def run_checks(limits=None, connector=None):
    limits = limits or Thresholds()
    factory = connector or connect
    with factory("monitor", "SFX_D1110_OPS_WH") as connection:
        with connection.cursor() as cursor:
            cursor.execute("""SELECT s.USAGE_DATE,COUNT(*),COUNT_IF(s.AMOUNT IS NULL),
                COUNT_IF(s.CURRENCY_CODE IS NULL)
                FROM CORE_BILLING.STG_BILLING__USAGE_DAILY s
                JOIN RAW_BILLING.USAGE_DAILY r ON s.USAGE_ID=r.USAGE_ID
                WHERE r._SRC_FILE LIKE 'pipeline/%'
                GROUP BY 1 ORDER BY 1 DESC LIMIT 2""")
            days = cursor.fetchall()
            cursor.execute("""SELECT FILE_NAME,STATUS,ERROR_COUNT,LAST_LOAD_TIME
                FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(
                    TABLE_NAME=>'SFX_D1110_AFTER.RAW_BILLING.USAGE_DAILY',
                    START_TIME=>DATEADD('hour',-%s,CURRENT_TIMESTAMP())))
                WHERE FILE_NAME LIKE '%%pipeline/%%' ORDER BY LAST_LOAD_TIME DESC""",
                           (limits.lookback_hours,))
            history = cursor.fetchall()
            cursor.execute("LIST @LANDING.LANDING_STAGE/pipeline/")
            retained = {"pipeline/" + PurePosixPath(row[0]).name for row in cursor.fetchall()}
    return evaluate(days, history, retained, limits)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_arguments(parser)
    print(json.dumps(run_checks(thresholds(parser.parse_args())), indent=2))
