"""Land the committed ensure_objects.sql DDL (verbatim literals) on the
warehouse - the prior-shape step of the rerun proof (DDL-only state before
the evolved job run). Same SP token via the SDK. Run from the repo root."""
from databricks.sdk.core import Config
import databricks.sql as dbsql

tok = Config().authenticate()["Authorization"].split(" ", 1)[1]
conn = dbsql.connect(server_hostname="dbc-8bc9474f-40ae.cloud.databricks.com",
                     http_path="/sql/1.0/warehouses/565cd2fd713738c4", access_token=tok)
with conn.cursor() as cur:
    cur.execute("CREATE SCHEMA IF NOT EXISTS ow_tp.ow_tp_analytics")
    cur.execute("""CREATE TABLE IF NOT EXISTS ow_tp.ow_tp_analytics.audit_archive (
    event_id STRING,
    action STRING,
    actor STRING,
    resource STRING,
    tenant STRING,
    timestamp STRING,
    archived_at TIMESTAMP,
    archive_s3_key STRING
)
USING DELTA""")
    cur.execute("""CREATE TABLE IF NOT EXISTS ow_tp.ow_tp_analytics.audit_archive_report (
    metric STRING,
    metric_value STRING,
    report_date DATE,
    generated_at TIMESTAMP
)
USING DELTA""")
print("ensure_objects done")
