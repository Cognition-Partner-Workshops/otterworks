import oracledb, os, json, sys
u,p,rest=os.environ["OW_BILLING_FIXTURE_DSN"].split("/",2)
c=oracledb.connect(user=u,password=p,dsn=rest); cur=c.cursor()
out={}
for t in ["CODES","TENANTS","PLANS"]:
    cur.execute(f"select count(*) from {t}"); out[t]=cur.fetchone()[0]
cur.execute("select to_char(max(initialized_at),'YYYY-MM-DD HH24:MI:SS.FF6') from FIXTURE_META"); out["FIXTURE_META.INITIALIZED_AT"]=cur.fetchone()[0]
cur.execute("select ora_hash(listagg(code_type||':'||code_val||'|'||code_desc,';') within group (order by code_type,code_val)) from CODES"); out["codes_hash"]=cur.fetchone()[0]
cur.execute("select sum(ora_hash(id||'|'||name||'|'||status_cd||'|'||tax_exempt_yn)) from TENANTS"); out["tenants_hash"]=cur.fetchone()[0]
cur.execute("select ora_hash(listagg(id||'|'||code||'|'||monthly_fee||'|'||included_units||'|'||overage_rate||'|'||tier_cd||'|'||active_yn,';') within group (order by id)) from PLANS"); out["plans_hash"]=cur.fetchone()[0]
print(json.dumps(out)); c.close()
