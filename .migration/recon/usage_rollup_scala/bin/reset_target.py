"""Drop the a01-owned target table so the fresh rerun leg starts empty.

oauth-m2m sql.connect hangs here; mints the same session SP's access token
via the SDK (identical to bin/recon_env.py) and uses the access_token path.
Literal statement; ow_tp.ow_tp_analytics.usage_rollup is this batch's
allowlisted write target. Run from the repo root.
"""
import os
from databricks.sdk.core import Config
import databricks.sql as dbsql

tok = Config().authenticate()["Authorization"].split(" ", 1)[1]
conn = dbsql.connect(
    server_hostname="dbc-8bc9474f-40ae.cloud.databricks.com",
    http_path="/sql/1.0/warehouses/565cd2fd713738c4",
    access_token=tok,
)
with conn.cursor() as cur:
    cur.execute("DROP TABLE IF EXISTS ow_tp.ow_tp_analytics.usage_rollup")
print("dropped usage_rollup")
