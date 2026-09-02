"""Read-only source watermark probe: Oracle counts + FIXTURE_META + sequences, Postgres counts,
DynamoDB ns histogram. Plain SQL only (never PL/SQL). Writes JSON to argv[1]."""
import json, os, sys, time, datetime as dt
import oracledb, psycopg, boto3

out = sys.argv[1]
ORA_TABLES = ["CODES", "TENANTS", "PLANS", "CUSTOMER_MASTER", "CUSTOMER_MASTER_HIST", "ENTITY_ATTR_VALUE",
              "INVOICE_HEADER", "INVOICE_LINE", "SUBSCRIPTIONS", "SUBSCRIPTIONS_HIST", "USAGE_EVENTS",
              "RATING_PERIODS", "RATING_RESULTS", "INVOICES", "INVOICE_LINES", "CREDIT_NOTES",
              "DUNNING_ATTEMPTS", "NOTIFICATIONS", "BILLING_AUDIT_LOG"]
res = {"utc": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), "oracle": {}, "postgres": {}, "dynamodb": {}}
user, pw, rest = os.environ["OW_BILLING_FIXTURE_DSN"].split("/", 2)
t0 = time.time()
with oracledb.connect(user=user, password=pw, dsn=rest) as con:
    cur = con.cursor()
    for t in ORA_TABLES:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        res["oracle"][t] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM CUSTOMER_MASTER WHERE conversion_batch_no = 85559852")
    res["oracle"]["CUSTOMER_MASTER@batch"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM INVOICE_HEADER WHERE batch_no = 85559852")
    res["oracle"]["INVOICE_HEADER@batch"] = cur.fetchone()[0]
    cur.execute("SELECT TO_CHAR(initialized_at,'YYYY-MM-DD HH24:MI:SS.FF6') FROM FIXTURE_META")
    res["oracle"]["FIXTURE_META.INITIALIZED_AT"] = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT sequence_name, last_number FROM USER_SEQUENCES ORDER BY 1")
    res["oracle"]["USER_SEQUENCES"] = {r[0]: r[1] for r in cur.fetchall()}
res["oracle_seconds"] = round(time.time() - t0, 2)
t0 = time.time()
with psycopg.connect(os.environ["OW_PG_DSN"]) as con:
    cur = con.cursor()
    for t in ["documents", "document_versions", "document_snapshots"]:
        cur.execute(f"SELECT COUNT(*) FROM otterworks_demo.{t}")
        res["postgres"][t] = cur.fetchone()[0]
res["postgres_seconds"] = round(time.time() - t0, 2)
t0 = time.time()
ddb = boto3.client("dynamodb", endpoint_url=os.environ["AWS_ENDPOINT_URL"], region_name="us-east-1",
                   aws_access_key_id="test", aws_secret_access_key="test")
hist, kwargs = {}, {"TableName": "otterworks-file-metadata", "ProjectionExpression": "ns"}
while True:
    page = ddb.scan(**kwargs)
    for it in page["Items"]:
        k = it.get("ns", {}).get("S", "<none>"); hist[k] = hist.get(k, 0) + 1
    if "LastEvaluatedKey" not in page: break
    kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
res["dynamodb"]["otterworks-file-metadata.ns_histogram"] = hist
res["dynamodb_seconds"] = round(time.time() - t0, 2)
json.dump(res, open(out, "w"), indent=2, default=str)
print(json.dumps(res, default=str))
