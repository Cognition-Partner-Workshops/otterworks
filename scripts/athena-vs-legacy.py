#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["psycopg[binary]==3.2.9", "boto3==1.35.99"]
# ///
"""Compare the Athena usage_summary named queries with legacy billing.fn_usage_summary.

Legacy side: ``billing.fn_usage_summary(tenant, start, end)`` for every tenant in
``billing.tenants`` and every period (connection as in billing-baseline.py:
``--legacy-url`` / ``LEGACY_BILLING_DATABASE_URL`` or ``DB_*``). With
``--baseline FILE`` (markdown written by billing-baseline.py) the live legacy rows
are also checked against that recorded baseline.

Athena side, in ``--workgroup``: the named query ``usage_summary_all_tenants``
for every period (params start, end, start, end) and ``usage_summary`` per
tenant for each ``--per-tenant-period`` (params tenant, start, end, start, end).
Queries use boto3 with the caller's credentials; the observer role
cannot StartQueryExecution, so run this under a role that can.

Prints one markdown table (tenant, kind, legacy, Athena, match) per period plus
grand totals and the query execution ids. Exits 1 on any mismatch.

Usage:
    uv run scripts/athena-vs-legacy.py --workgroup lp-<token>-billing \
        [--period 2026-02-01:2026-02-28 ...] [--per-tenant-period 2026-02-01:2026-02-28] \
        [--baseline baseline.md] [--output FILE]
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from datetime import date

import boto3
import psycopg

DEFAULT_PERIODS = ("2026-02-01:2026-02-28", "2026-09-01:2026-09-30")
DEFAULT_PER_TENANT = ("2026-02-01:2026-02-28",)
ALL_TENANTS_QUERY = "usage_summary_all_tenants"
PER_TENANT_QUERY = "usage_summary"


def parse_period(value: str) -> tuple[date, date]:
    start, _, end = value.partition(":")
    try:
        period = (date.fromisoformat(start), date.fromisoformat(end))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD:YYYY-MM-DD, got {value!r}") from exc
    if period[1] < period[0]:
        raise argparse.ArgumentTypeError(f"period end before start: {value!r}")
    return period


def connect(url: str | None) -> psycopg.Connection:
    if url:
        return psycopg.connect(url, connect_timeout=10)
    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "55432")),
        dbname=os.getenv("DB_NAME", f"billing_{os.getenv('NS', 'dev')}"),
        user=os.getenv("DB_USER", "billing"),
        password=os.getenv("DB_PASSWORD", "billing"),
        connect_timeout=10,
    )


# --- legacy -----------------------------------------------------------------

def legacy_summary(conn, tenants, start: date, end: date) -> dict[tuple[str, str], tuple[int, int]]:
    rows = {}
    for tenant_id, _ in tenants:
        for kind, count, units in conn.execute(
            "SELECT kind, event_count, units FROM billing.fn_usage_summary(%s, %s, %s)",
            (tenant_id, start, end),
        ):
            rows[(tenant_id, kind)] = (int(count), int(units))
    return rows


def parse_baseline(path: str) -> dict[tuple[date, date], dict[tuple[str, str], tuple[int, int]]]:
    """Per-tenant rows of each ``### billing.fn_usage_summary start..end`` section."""
    periods: dict = {}
    current = None
    heading = re.compile(r"^### billing\.fn_usage_summary (\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})")
    row = re.compile(r"^\|\s*([0-9a-f-]{36})\s*\|[^|]*\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|")
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if m := heading.match(line):
                current = periods.setdefault((date.fromisoformat(m[1]), date.fromisoformat(m[2])), {})
            elif line.startswith("#"):
                current = None
            elif current is not None and (m := row.match(line)) and m[2] != "(no rows)":
                current[(m[1], m[2])] = (int(m[3]), int(m[4]))
    return periods


# --- athena -----------------------------------------------------------------

def named_queries(athena, workgroup: str) -> dict[str, dict]:
    ids = athena.list_named_queries(WorkGroup=workgroup)["NamedQueryIds"]
    found = athena.batch_get_named_query(NamedQueryIds=ids)["NamedQueries"] if ids else []
    return {q["Name"]: q for q in found}


def run_query(athena, workgroup: str, query: dict, params: list[str]) -> tuple[str, list[list[str]]]:
    """Execution parameters are substituted as SQL literals, so strings go in quoted."""
    qid = athena.start_query_execution(
        QueryString=query["QueryString"],
        QueryExecutionContext={"Database": query["Database"]},
        WorkGroup=workgroup,
        ExecutionParameters=["'" + p.replace("'", "''") + "'" for p in params],
    )["QueryExecutionId"]
    while True:
        status = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]
        if status["State"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1)
    if status["State"] != "SUCCEEDED":
        raise RuntimeError(f"{query['Name']} {qid} {status['State']}: {status.get('StateChangeReason', '')}")
    rows = []
    for page in athena.get_paginator("get_query_results").paginate(QueryExecutionId=qid):
        rows += [[c.get("VarCharValue", "") for c in r["Data"]] for r in page["ResultSet"]["Rows"]]
    return qid, rows[1:]  # drop the header row


# --- report -----------------------------------------------------------------

def fmt(value: tuple[int, int] | None) -> str:
    return "0 / 0 (no rows)" if value is None else f"{value[0]} / {value[1]}"


def compare_period(start, end, tenants, legacy, athena, qid) -> tuple[list[str], bool]:
    out = [f"### {start}..{end} (Athena `{ALL_TENANTS_QUERY}` `{qid}`)", "",
           "| tenant | kind | legacy event_count / units | Athena event_count / units | match |",
           "| --- | --- | ---: | ---: | :---: |"]
    ok = True
    totals: dict[str, list[int]] = {}
    known = {t for t, _ in tenants}
    for tenant_id, name in tenants + [(t, "(not in billing.tenants)") for t in sorted({t for t, _ in athena} - known)]:
        kinds = sorted({k for t, k in legacy if t == tenant_id} | {k for t, k in athena if t == tenant_id})
        if not kinds:
            out.append(f"| {name} (`{tenant_id}`) | (no rows) | 0 / 0 | 0 / 0 | yes |")
        for kind in kinds:
            lv, av = legacy.get((tenant_id, kind)), athena.get((tenant_id, kind))
            match = lv == av
            ok &= match
            out.append(f"| {name} (`{tenant_id}`) | {kind} | {fmt(lv)} | {fmt(av)} | {'yes' if match else '**NO**'} |")
            for side, value in ((0, lv), (1, av)):
                acc = totals.setdefault(kind, [0, 0, 0, 0])
                if value:
                    acc[2 * side] += value[0]
                    acc[2 * side + 1] += value[1]
    grand = [sum(v[i] for v in totals.values()) for i in range(4)]
    for kind, acc in sorted(totals.items()) + [("**all**", grand)]:
        match = acc[:2] == acc[2:]
        ok &= match
        out.append(f"| **total** | {kind} | {acc[0]} / {acc[1]} | {acc[2]} / {acc[3]} | {'yes' if match else '**NO**'} |")
    out.append("")
    return out, ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workgroup", required=True)
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"))
    parser.add_argument("--legacy-url", default=os.getenv("LEGACY_BILLING_DATABASE_URL"))
    parser.add_argument("--period", action="append", type=parse_period,
                        help="YYYY-MM-DD:YYYY-MM-DD, repeatable (default: Feb 2026 and Sep 2026)")
    parser.add_argument("--per-tenant-period", action="append", type=parse_period,
                        help="periods to also run usage_summary per tenant (default: Feb 2026)")
    parser.add_argument("--baseline", help="billing-baseline.py markdown to check the live legacy rows against")
    parser.add_argument("--output", help="also write the markdown to this file")
    args = parser.parse_args()
    periods = args.period or [parse_period(p) for p in DEFAULT_PERIODS]
    per_tenant_periods = args.per_tenant_period or [parse_period(p) for p in DEFAULT_PER_TENANT]

    with connect(args.legacy_url) as conn:
        tenants = [(str(t), n) for t, n in conn.execute("SELECT id, name FROM billing.tenants ORDER BY id")]
        legacy = {p: legacy_summary(conn, tenants, *p) for p in sorted(set(periods) | set(per_tenant_periods))}

    client = boto3.client("athena", region_name=args.region)
    queries = named_queries(client, args.workgroup)
    missing = {ALL_TENANTS_QUERY, PER_TENANT_QUERY} - set(queries)
    if missing:
        print(f"athena-vs-legacy: named queries missing in {args.workgroup}: {sorted(missing)}", file=sys.stderr)
        return 3

    ok = True
    out = ["## Athena vs legacy fn_usage_summary", "",
           f"Workgroup `{args.workgroup}`, named queries `{ALL_TENANTS_QUERY}` "
           f"({queries[ALL_TENANTS_QUERY]['NamedQueryId']}) and `{PER_TENANT_QUERY}` "
           f"({queries[PER_TENANT_QUERY]['NamedQueryId']}), database `{queries[ALL_TENANTS_QUERY]['Database']}`.", ""]

    if args.baseline:
        recorded = parse_baseline(args.baseline)
        out += ["### Live legacy vs recorded baseline", "", "| period | recorded rows | live rows | equal |",
                "| --- | ---: | ---: | :---: |"]
        for period in sorted(legacy):
            rec = recorded.get(period)
            equal = rec == legacy[period]
            ok &= equal
            out.append(f"| {period[0]}..{period[1]} | {'missing' if rec is None else len(rec)} | "
                       f"{len(legacy[period])} | {'yes' if equal else '**NO**'} |")
        out.append("")

    for start, end in periods:
        s, e = start.isoformat(), end.isoformat()
        qid, rows = run_query(client, args.workgroup, queries[ALL_TENANTS_QUERY], [s, e, s, e])
        athena = {(t, k): (int(c), int(u)) for t, k, c, u in rows}
        section, match = compare_period(start, end, tenants, legacy[(start, end)], athena, qid)
        ok &= match
        out += section

    for start, end in per_tenant_periods:
        s, e = start.isoformat(), end.isoformat()
        out += [f"### `{PER_TENANT_QUERY}` per tenant {s}..{e}", "",
                "| tenant | Athena execution id | rows (kind event_count/units) | equals legacy |",
                "| --- | --- | --- | :---: |"]
        for tenant_id, name in tenants:
            qid, rows = run_query(client, args.workgroup, queries[PER_TENANT_QUERY], [tenant_id, s, e, s, e])
            athena = {(tenant_id, k): (int(c), int(u)) for k, c, u in rows}
            expected = {key: v for key, v in legacy[(start, end)].items() if key[0] == tenant_id}
            match = athena == expected
            ok &= match
            shown = ", ".join(f"{k} {c}/{u}" for (_, k), (c, u) in sorted(athena.items())) or "(no rows)"
            out.append(f"| {name} | `{qid}` | {shown} | {'yes' if match else '**NO**'} |")
        out.append("")

    out.append(f"Result: {'every row and total matches' if ok else 'MISMATCH'}.")
    text = "\n".join(out)
    print(text)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
