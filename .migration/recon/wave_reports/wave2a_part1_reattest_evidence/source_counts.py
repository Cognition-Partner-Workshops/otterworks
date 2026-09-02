# one serial pass, 11 COUNT(*) + FIXTURE_META + sequence read; read-only; cap 1 honoured
import oracledb, json, os, datetime
u="ow_billing"; p="ow_billing"; d="localhost:52521/FREEPDB1"
c = oracledb.connect(user=u, password=p, dsn=d); cur=c.cursor()
out={"at": datetime.datetime.utcnow().isoformat()+"Z"}
for t in ["SUBSCRIPTIONS","SUBSCRIPTIONS_HIST","USAGE_EVENTS","RATING_PERIODS","RATING_RESULTS","INVOICES","INVOICE_LINES","CREDIT_NOTES","DUNNING_ATTEMPTS","NOTIFICATIONS","BILLING_AUDIT_LOG"]:
    cur.execute(f"select count(*) from {t}"); out[t]=cur.fetchone()[0]
cur.execute("select to_char(initialized_at,'YYYY-MM-DD HH24:MI:SS.FF6') from fixture_meta"); out["FIXTURE_META"]=cur.fetchone()[0]
cur.execute("select sequence_name,last_number from user_sequences where sequence_name in ('SEQ_BILLING_AUDIT_LOG','SEQ_SUBSCRIPTIONS_HIST')"); out["sequences"]=dict(cur.fetchall())
cur.execute("select log_id, to_char(logged_at,'YYYY-MM-DD HH24:MI:SS'), module, message from billing_audit_log"); out["audit_rows"]=cur.fetchall()
print(json.dumps(out,indent=1,default=str))
