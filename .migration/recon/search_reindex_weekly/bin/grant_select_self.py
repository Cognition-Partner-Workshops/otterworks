"""GRANT SELECT to the session SP on this batch's two target tables.

The recon grant-parity tier compares source grants (session SP holds
SELECT + ALL_PRIVILEGES on the staged legacy tables) with target grants;
as table owner the SP carries ALL_PRIVILEGES but no literal SELECT row,
which the harness reads as grant_missing. This adds the literal SELECT on
the allowlisted targets only. Literal statements; run from the repo root.
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
    cur.execute("GRANT SELECT ON TABLE ow_tp.ow_tp_analytics.search_index_docs TO `d9d1c4ec-29da-4ec7-9aa0-e932710d61e2`")
    cur.execute("GRANT SELECT ON TABLE ow_tp.ow_tp_analytics.search_reindex_report TO `d9d1c4ec-29da-4ec7-9aa0-e932710d61e2`")
print("granted SELECT on search_index_docs, search_reindex_report")
