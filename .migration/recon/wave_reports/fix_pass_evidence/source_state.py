import json, os, sys, oracledb
dsn=os.environ["OW_BILLING_FIXTURE_DSN"]; u,p,d = dsn.split("/",2)
out={}
with oracledb.connect(user=u,password=p,dsn=d) as c:
    cur=c.cursor()
    for t in ["RATING_PERIODS","RATING_RESULTS","INVOICES","INVOICE_LINES","CREDIT_NOTES","DUNNING_ATTEMPTS","NOTIFICATIONS","SUBSCRIPTIONS","SUBSCRIPTIONS_HIST","USAGE_EVENTS","TENANTS","PLANS","BILLING_AUDIT_LOG","CODES"]:
        cur.execute(f"SELECT COUNT(*) FROM {t}"); out[t]=cur.fetchone()[0]
    cur.execute("SELECT SEQUENCE_NAME, LAST_NUMBER FROM USER_SEQUENCES ORDER BY 1"); out["USER_SEQUENCES"]={r[0]:int(r[1]) for r in cur}
    try:
        cur.execute("SELECT * FROM FIXTURE_META"); out["FIXTURE_META"]=[[str(x) for x in r] for r in cur]
    except Exception as e: out["FIXTURE_META"]=str(e)
    cur.execute("SELECT LOG_ID, MODULE, MESSAGE FROM BILLING_AUDIT_LOG ORDER BY LOG_ID"); out["BILLING_AUDIT_LOG_ROWS"]=[list(r) for r in cur]
json.dump(out, open(sys.argv[1],"w"), indent=1, default=str); print(json.dumps(out, default=str))
