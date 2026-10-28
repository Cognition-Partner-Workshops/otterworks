"""Re-create the a03-owned target tables in committed DDL shape (evolved leg
pre-state). oauth-m2m sql.connect hangs here; mints the same session SP's
access token via the SDK (identical to bin/recon_env.py). Literal statements
mirroring etl/dbx-storage-cleanup/src/ensure_objects.sql; targets are this
batch's allowlisted writes. Run from the repo root."""
from databricks.sdk.core import Config
import databricks.sql as dbsql

tok = Config().authenticate()["Authorization"].split(" ", 1)[1]
conn = dbsql.connect(
    server_hostname="dbc-8bc9474f-40ae.cloud.databricks.com",
    http_path="/sql/1.0/warehouses/565cd2fd713738c4",
    access_token=tok,
)
with conn.cursor() as cur:
    cur.execute("CREATE SCHEMA IF NOT EXISTS ow_tp.ow_tp_analytics")
    cur.execute("CREATE VOLUME IF NOT EXISTS ow_tp.ow_tp_analytics.storage_drop")
    cur.execute("""CREATE TABLE IF NOT EXISTS ow_tp.ow_tp_analytics.storage_quarantine_actions (
    s3_key STRING, size_bytes BIGINT, quarantine_key STRING, quarantined_at DATE
) USING DELTA""")
    cur.execute("""CREATE TABLE IF NOT EXISTS ow_tp.ow_tp_analytics.storage_cleanup_report (
    metric STRING, metric_value STRING, report_date DATE, generated_at TIMESTAMP
) USING DELTA""")
print("created storage_quarantine_actions + storage_cleanup_report")
