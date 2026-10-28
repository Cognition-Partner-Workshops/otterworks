"""Drop the a02-owned target tables so the fresh rerun leg starts empty.

oauth-m2m sql.connect hangs here; mints the same session SP's access token
via the SDK (identical to bin/recon_env.py) and uses the access_token path.
Literal statements; ow_tp.ow_tp_analytics.search_index_docs and
ow_tp.ow_tp_analytics.search_reindex_report are this batch's allowlisted
write targets. Run from the repo root.
"""
from databricks.sdk.core import Config
import databricks.sql as dbsql

tok = Config().authenticate()["Authorization"].split(" ", 1)[1]
conn = dbsql.connect(
    server_hostname="dbc-8bc9474f-40ae.cloud.databricks.com",
    http_path="/sql/1.0/warehouses/565cd2fd713738c4",
    access_token=tok,
)
with conn.cursor() as cur:
    cur.execute("DROP TABLE IF EXISTS ow_tp.ow_tp_analytics.search_index_docs")
    cur.execute("DROP TABLE IF EXISTS ow_tp.ow_tp_analytics.search_reindex_report")
print("dropped search_index_docs, search_reindex_report")
