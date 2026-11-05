from __future__ import annotations

import argparse
import copy
import hashlib
import json
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import snowflake.connector

import runtime


def save_bundle(directory, payload):
    directory.mkdir(parents=True, exist_ok=True)
    payload["exported_at"] = datetime.now(timezone.utc).isoformat()
    content = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    path = directory / f"snapshot_{hashlib.sha256(content.encode()).hexdigest()}.json"
    path.write_text(content + "\n")
    return path


def refresh():
    for workload in runtime.WORKLOADS:
        with (
            closing(
                snowflake.connector.connect(**runtime.parameters(workload))
            ) as conn,
            conn.cursor() as cur,
        ):
            cur.execute(f"CALL {runtime.procedure_name(workload)}()")
            assert cur.fetchone()[0] == f"{runtime.sf.RUN_TOKEN}_ANALYST"


def fingerprints():
    results = {}
    for workload in runtime.WORKLOADS:
        with (
            closing(
                snowflake.connector.connect(**runtime.parameters(workload))
            ) as conn,
            conn.cursor() as cur,
        ):
            db = runtime.sf.database_name(workload)
            for table, (_, _, columns) in runtime.TABLES.items():
                cur.execute(
                    f"SELECT COUNT(*), HASH_AGG({', '.join(columns)}) FROM {db}.RAW.{table} WHERE _snapshot_date IS NOT NULL"
                )
                results[f"{workload}.RAW.{table}"] = cur.fetchone()
            cur.execute(
                f"SELECT COUNT(*), HASH_AGG(*) FROM {db}.APP.{runtime.MODELS[workload]}"
            )
            results[f"{workload}.APP"] = cur.fetchone()
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    args = parser.parse_args()
    payload = runtime.validate_bundle(args.bundle)
    refresh()
    baseline = fingerprints()
    runtime.load(force=True)
    refresh()
    assert fingerprints() == baseline, "forced file replay changed raw/reporting rows"
    print(
        "PASS: forced replay of the same files preserves raw and reporting fingerprints"
    )

    duplicates = copy.deepcopy(payload)
    for rows in duplicates["tables"].values():
        rows.extend(copy.deepcopy(rows[:2]))
    runtime.publish(save_bundle(args.artifacts, duplicates))
    refresh()
    assert fingerprints() == baseline, (
        "duplicate source rows changed raw/reporting rows"
    )
    print(
        "PASS: duplicate rows in a newly named snapshot preserve raw and reporting fingerprints"
    )

    late = copy.deepcopy(payload)
    account = hashlib.md5(b"SFEXT_20261105A:customer:1").hexdigest()
    account = f"{account[:8]}-{account[8:12]}-{account[12:16]}-{account[16:20]}-{account[20:]}"
    event_time = datetime.fromisoformat(payload["snapshot_date"]).replace(
        tzinfo=timezone.utc
    ) - timedelta(hours=12)
    late["tables"]["ANALYTICS_ANALYTICS_EVENTS"].append(
        {
            "event_id": "SFEXT_20261105A-day-late-event",
            "event_type": "search.performed",
            "user_id": account,
            "metadata": json.dumps(
                {
                    "query": "pipeline day late",
                    "result_count": "0",
                    "document_hit_ids": "",
                }
            ),
            "occurred_at": int(event_time.timestamp()) * 1_000_000_000,
        }
    )
    runtime.publish(save_bundle(args.artifacts, late))
    refresh()
    with (
        closing(
            snowflake.connector.connect(**runtime.parameters("doc_search_api"))
        ) as conn,
        conn.cursor() as cur,
    ):
        cur.execute(
            f"SELECT SEARCH_COUNT, ZERO_RESULT_COUNT FROM {runtime.sf.database_name('doc_search_api')}.APP.TOP_SEARCH_ITEMS WHERE ACCOUNT_ID=%s AND TERM='pipeline day late' AND WINDOW_END_DATE=%s",
            (account, event_time.date()),
        )
        assert cur.fetchall() == [(1, 1)], "a day-late event was lost or counted twice"
    print(
        "PASS: event dated the day before export backfills the historical search window exactly once"
    )
    args.artifacts.joinpath("resilience-results.json").write_text(
        json.dumps(
            {
                "forced_file_replay": "passed",
                "duplicate_rows_new_file": "passed",
                "day_late_event": "passed",
                "baseline_fingerprints": baseline,
                "executing_role": f"{runtime.sf.RUN_TOKEN}_ANALYST",
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
