# one serial read-only Oracle pass (cap 1): COUNT(*) on the U6/U7 graded tables + FIXTURE_META + sequences + audit rows
import oracledb, json, datetime
c = oracledb.connect(user="ow_billing", password="ow_billing", dsn="localhost:52521/FREEPDB1"); cur=c.cursor()
out={"at": datetime.datetime.utcnow().isoformat()+"Z"}
for t in ["CODES","TENANTS","PLANS","SUBSCRIPTIONS","SUBSCRIPTIONS_HIST","USAGE_EVENTS","RATING_PERIODS","RATING_RESULTS","INVOICES","INVOICE_LINES","CREDIT_NOTES","DUNNING_ATTEMPTS","NOTIFICATIONS","BILLING_AUDIT_LOG"]:
    cur.execute(f"select count(*) from {t}"); out[t]=cur.fetchone()[0]
cur.execute("select to_char(initialized_at,'YYYY-MM-DD HH24:MI:SS.FF6') from fixture_meta"); out["FIXTURE_META"]=cur.fetchone()[0]
cur.execute("select sequence_name,last_number from user_sequences where sequence_name in ('SEQ_BILLING_AUDIT_LOG','SEQ_SUBSCRIPTIONS_HIST')"); out["sequences"]=dict(cur.fetchall())
cur.execute("select log_id, to_char(logged_at,'YYYY-MM-DD HH24:MI:SS'), module, message from billing_audit_log order by log_id"); out["audit_rows"]=cur.fetchall()
import hashlib
out["pkg_body_sha256"]={}
for n in ('PKG_OW_UTIL','PKG_PLANS','PKG_RATING','PKG_INVOICING','PKG_DUNNING'):
    cur.execute("select text from user_source where name=:n and type='PACKAGE BODY' order by line",n=n)
    out["pkg_body_sha256"][n]=hashlib.sha256("".join(r[0] for r in cur.fetchall()).encode()).hexdigest()
cur.execute("select object_name, status from user_objects where object_name in ('PKG_OW_UTIL','PKG_PLANS','PKG_RATING','PKG_INVOICING','PKG_DUNNING') and object_type='PACKAGE BODY'"); out["pkg_status"]=dict(cur.fetchall())
print(json.dumps(out,indent=1,default=str))
