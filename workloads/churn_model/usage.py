"""Report tagged query evidence and separate compute/Cortex usage for one run."""

import argparse
import json
import re

from workloads.churn_model.provision import EP, admin_connection, sf


def cortex_detection(query_id, text, usage_ids, recorded_ids):
    if query_id in usage_ids:
        return True, "usage_history"
    if query_id in recorded_ids:
        return True, "recorded_query_id"
    if not text or "<redacted>" in text.lower():
        return "unknown", "redacted_or_missing_text"
    if re.search(r"\b(?:SNOWFLAKE\.CORTEX\.\w+|AI_\w+)\s*\(", text, re.IGNORECASE):
        return True, "function_call"
    return False, "query_text"


def report(conn, run_id):
    # Recent history closes the ACCOUNT_USAGE latency gap without inventing credits.
    sql = """WITH history AS (
      SELECT query_id,query_tag,warehouse_name,query_text FROM TABLE(
        INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER(USER_NAME => %s, RESULT_LIMIT => 10000))
      UNION ALL SELECT query_id,query_tag,warehouse_name,query_text FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
      WHERE start_time >= DATEADD(day,-7,CURRENT_TIMESTAMP()))
      SELECT query_id,query_tag,warehouse_name,query_text
      FROM history WHERE TRY_PARSE_JSON(query_tag):run_id::string=%s
      QUALIFY ROW_NUMBER() OVER (PARTITION BY query_id ORDER BY query_id)=1"""
    with conn.cursor() as cur:
        cur.execute(sql, (EP.service_user, run_id))
        queries = cur.fetchall()
        ids = [row[0] for row in queries]
        cur.execute("SELECT DISTINCT CORTEX_QUERY_ID FROM APP.CHURN_DOCUMENT_LABELS WHERE RUN_ID=%s "
                    "UNION SELECT ERROR_QUERY_ID FROM APP.CHURN_MODEL_RUNS WHERE RUN_ID=%s AND STATUS='failed_at_document_labels'",
                    (run_id, run_id))
        recorded_ids = {row[0] for row in cur.fetchall() if row[0]}
        usage_ids = set()
        if ids:
            marks = ",".join("%s" for _ in ids)
            cur.execute(f"SELECT DISTINCT QUERY_ID FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY WHERE QUERY_ID IN ({marks})", ids)
            usage_ids = {row[0] for row in cur.fetchall()}
        for query_id, query_tag, warehouse, text in queries:
            cortex, evidence = cortex_detection(query_id, text, usage_ids, recorded_ids)
            print(json.dumps(dict(query_id=query_id, query_tag=query_tag, warehouse=warehouse,
                                  is_cortex=cortex, cortex_evidence=evidence)))
        for label, view, expressions in (
            ("warehouse_compute", "QUERY_ATTRIBUTION_HISTORY", "SUM(credits_attributed_compute),SUM(credits_used_query_acceleration)"),
            ("cortex", "CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY", "SUM(token_credits),SUM(tokens)"),
        ):
            values = (None, None)
            if ids:
                marks = ",".join("%s" for _ in ids)
                cur.execute(f"SELECT {expressions} FROM SNOWFLAKE.ACCOUNT_USAGE.{view} WHERE query_id IN ({marks})", ids)
                values = cur.fetchone()
            print(json.dumps(dict(kind=label, credits=sf.usage_value(values[0]),
                                  **{"query_acceleration_credits" if label == "warehouse_compute" else "tokens": sf.usage_value(values[1])})))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    args = parser.parse_args()
    with admin_connection() as conn:
        report(conn, args.run_id)


if __name__ == "__main__":
    main()
