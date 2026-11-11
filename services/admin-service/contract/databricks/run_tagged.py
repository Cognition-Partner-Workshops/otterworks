"""Run one consumer statement on the live target and print its statement_id with the result or error.

Usage: python run_tagged.py STEP < statement.sql   (DATABRICKS_HOST/TOKEN/WAREHOUSE_ID from the environment)
Evidence helper only: the consumer itself reads through consumers/contract-kit/databricks_bridge.py.
"""
import json
import os
import re
import sys
from datetime import date
from decimal import Decimal


def main():
    from databricks import sql
    step = sys.argv[1]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", step):
        raise ValueError("invalid step")
    host = os.environ["DATABRICKS_HOST"].removeprefix("https://").rstrip("/")
    statement = f"/* run=dbx-d1111 act=consumers step={step} consumer=admin-service */\n" + sys.stdin.read()
    with sql.connect(server_hostname=host, http_path="/sql/1.0/warehouses/" + os.environ["DATABRICKS_WAREHOUSE_ID"],
                     access_token=os.environ["DATABRICKS_TOKEN"], catalog="cpw", schema="dbx_d1111_after") as conn:
        with conn.cursor() as cursor:
            out = {"step": step}
            try:
                cursor.execute(statement)
                out["columns"] = [c[0].upper() for c in cursor.description]
                out["rows"] = [list(r) for r in cursor.fetchall()]
                out["outcome"] = "pass"
            except Exception as error:  # report the live failure verbatim (first line)
                out["outcome"] = "fail"
                out["error"] = str(error).strip().splitlines()[0][:300]
            out["statement_id"] = cursor.query_id
    print(json.dumps(out, default=lambda v: str(v) if isinstance(v, (Decimal, date)) else repr(v)))


if __name__ == "__main__":
    main()
