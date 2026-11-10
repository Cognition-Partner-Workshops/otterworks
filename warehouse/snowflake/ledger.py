"""Allocate metered warehouse compute to tagged execution time."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json

from sfx_conn import WORKLOADS, connect


def records(cursor, sql, params=()):
    cursor.execute(sql, params)
    columns = [col[0].lower() for col in cursor.description]
    return [dict(zip(columns, [value.astimezone(timezone.utc)
                              if isinstance(value, datetime) and value.tzinfo is not None
                              else value for value in row])) for row in cursor.fetchall()]


def read_usage(cursor, token, days):
    warehouses = tuple(WORKLOADS.values())
    slots = ", ".join(["%s"] * len(warehouses))
    queries = records(cursor, f"""
        WITH hours AS (
            SELECT WAREHOUSE_NAME, DATE_TRUNC('hour', START_TIME) AS HOUR,
                   SUM(EXECUTION_TIME) AS HOUR_EXECUTION
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= DATEADD('day', -%s, CURRENT_TIMESTAMP())
              AND WAREHOUSE_NAME IN ({slots})
            GROUP BY 1, 2
        )
        SELECT Q.QUERY_ID, Q.START_TIME, Q.WAREHOUSE_NAME,
               DATE_TRUNC('hour', Q.START_TIME) AS HOUR,
               TRY_PARSE_JSON(Q.QUERY_TAG):workload::VARCHAR AS WORKLOAD,
               TRY_PARSE_JSON(Q.QUERY_TAG):phase::VARCHAR AS PHASE,
               TRY_PARSE_JSON(Q.QUERY_TAG):executed_by::VARCHAR AS EXECUTED_BY,
               TRY_PARSE_JSON(Q.QUERY_TAG):built_with::VARCHAR AS BUILT_WITH,
               Q.EXECUTION_TIME, Q.CREDITS_USED_CLOUD_SERVICES,
               H.HOUR_EXECUTION
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY Q
        LEFT JOIN hours H ON Q.WAREHOUSE_NAME=H.WAREHOUSE_NAME
                        AND DATE_TRUNC('hour', Q.START_TIME)=H.HOUR
        WHERE Q.START_TIME >= DATEADD('day', -%s, CURRENT_TIMESTAMP())
          AND Q.QUERY_TAG ILIKE %s
          AND (TRY_PARSE_JSON(Q.QUERY_TAG):run_token::VARCHAR = %s
               OR TRY_PARSE_JSON(Q.QUERY_TAG):run::VARCHAR = %s)
    """, (days, *warehouses, days, "%" + token + "%", token, token))
    meters = records(cursor, f"""
        SELECT WAREHOUSE_NAME, START_TIME AS HOUR, END_TIME,
               CREDITS_USED_COMPUTE
        FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
        WHERE START_TIME >= DATEADD('day', -%s, CURRENT_TIMESTAMP())
          AND WAREHOUSE_NAME IN ({slots})
    """, (days, *warehouses))
    freshness = records(cursor, """
        SELECT MAX(START_TIME) AS QUERY_MAX_START
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME >= DATEADD('day', -%s, CURRENT_TIMESTAMP())
    """, (days,))[0]["query_max_start"]
    recent = records(cursor, """
        SELECT QUERY_ID, START_TIME, WAREHOUSE_NAME,
               TRY_PARSE_JSON(QUERY_TAG):workload::VARCHAR AS WORKLOAD,
               TRY_PARSE_JSON(QUERY_TAG):phase::VARCHAR AS PHASE,
               TRY_PARSE_JSON(QUERY_TAG):executed_by::VARCHAR AS EXECUTED_BY,
               TRY_PARSE_JSON(QUERY_TAG):built_with::VARCHAR AS BUILT_WITH
        FROM TABLE(SFX_D1110_AFTER.INFORMATION_SCHEMA.QUERY_HISTORY(
            END_TIME_RANGE_START=>DATEADD('hour', -3, CURRENT_TIMESTAMP()),
            RESULT_LIMIT=>10000))
        WHERE QUERY_TAG ILIKE %s
          AND (TRY_PARSE_JSON(QUERY_TAG):run_token::VARCHAR = %s
               OR TRY_PARSE_JSON(QUERY_TAG):run::VARCHAR = %s)
    """, ("%" + token + "%", token, token))
    return queries, meters, recent, freshness


def summarize(queries, meters, recent, query_freshness):
    metering = {(r["warehouse_name"], r["hour"]): r for r in meters}
    known = {q["query_id"] for q in queries}
    pending_recent = [q for q in recent if q["query_id"] not in known]
    meter_end = max((r["end_time"] for r in meters), default=None)
    groups = {}
    for dimension in ("total", "executed_by", "built_with"):
        cells = defaultdict(lambda: {"credits": 0.0, "pending": False, "queries": 0,
                                     "recent_not_in_account_usage": 0})
        for query in queries:
            value = "all" if dimension == "total" else (query.get(dimension) or "unknown")
            key = (query.get("workload") or "unknown", query.get("phase") or "unknown", value)
            cell = cells[key]
            cell["queries"] += 1
            meter = metering.get((query["warehouse_name"], query["hour"]))
            cloud = query.get("credits_used_cloud_services")
            if meter is None or cloud is None:
                cell["pending"] = True
                continue
            denominator = float(query.get("hour_execution") or 0)
            execution = float(query.get("execution_time") or 0)
            if denominator == 0 and execution != 0:
                cell["pending"] = True
                continue
            cell["credits"] += (float(meter["credits_used_compute"]) * execution / denominator
                                if denominator else 0) + float(cloud)
        for query in recent:
            value = "all" if dimension == "total" else (query.get(dimension) or "unknown")
            key = (query.get("workload") or "unknown", query.get("phase") or "unknown", value)
            cell = cells[key]
            if query["query_id"] not in known:
                cell["recent_not_in_account_usage"] += 1
                cell["pending"] = True
            if (query_freshness is None or query["start_time"] > query_freshness
                    or meter_end is None or query["start_time"] > meter_end):
                cell["pending"] = True
        groups[dimension] = [
            {"workload": key[0], "phase": key[1], dimension: key[2],
             "credits": "pending" if cell["pending"] else round(cell["credits"], 9),
             "account_usage_queries": cell["queries"],
             "recent_not_in_account_usage": cell["recent_not_in_account_usage"]}
            for key, cell in sorted(cells.items())
        ]
    return {
        "freshness": {
            "account_usage_query_max_start": query_freshness,
            "metering_max_start": max((r["hour"] for r in meters), default=None),
            "metering_max_end": meter_end,
            "newest_recent_tagged_activity": max((q["start_time"] for q in recent), default=None),
            "note": "ACCOUNT_USAGE lags up to ~3h; recent history covers 3h, at most 10000 visible queries",
        },
        "recent_tagged_queries": len(recent),
        "recent_not_in_account_usage": len(pending_recent),
        "groups": groups,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", default="sfx-d1110")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.days <= 365:
        parser.error("--days must be between 1 and 365")
    with connect("ops", "ledger") as conn:
        with conn.cursor() as cur:
            report = summarize(*read_usage(cur, args.token, args.days))
    if args.json:
        print(json.dumps(report, default=str, indent=2))
        return
    freshness = report["freshness"]
    print("ACCOUNT_USAGE freshness: query max start="
          f"{freshness['account_usage_query_max_start']}; metering max start="
          f"{freshness['metering_max_start']}; ACCOUNT_USAGE lags up to ~3h")
    print(f"Recent tagged queries (3h): {report['recent_tagged_queries']}; "
          f"not yet in ACCOUNT_USAGE: {report['recent_not_in_account_usage']}")
    for dimension, rows in report["groups"].items():
        print(f"Dimension: {dimension}")
        for row in rows:
            print(f"  {row['workload']} / {row['phase']} / {dimension}={row[dimension]}: "
                  f"credits={row['credits']} queries={row['account_usage_queries']} "
                  f"recent_unaccounted={row['recent_not_in_account_usage']}")


if __name__ == "__main__":
    main()
