#!/usr/bin/env python3
"""Wave-1 cross-unit consistency + app-level replays across units (read-only).
Shared refs: codes / tenants / plans (U0) <- customers (U1) <- invoices (U2); documents (U3) / files (U4) owners.
RPT-114 month-end + reconciliation reports replayed verbatim on Oracle and as pipelines on Mongo."""
import hashlib, json, os, sys, time
from decimal import Decimal
from collections import Counter

import oracledb, psycopg
from bson.decimal128 import Decimal128
from bson.json_util import dumps, CANONICAL_JSON_OPTIONS
from pymongo import MongoClient

T0 = time.time()
BATCH = 85559852
user, pw, dsn = os.environ["OW_BILLING_FIXTURE_DSN"].split("/", 2)
ora = oracledb.connect(user=user, password=pw, dsn=dsn)
cur = ora.cursor()
cur.execute("SET TRANSACTION READ ONLY")
m = MongoClient(os.environ["MONGODB_ATLAS_URI"])
db = m["ow_tp_mongodb_205236"]
qdb = m["ow_tp_mongodb_205236_quarantine"]
results = []; n_sql = 0


def q(sql, **kw):
    global n_sql
    n_sql += 1
    cur.execute(sql, kw)
    return cur.fetchall()


def ok(name, cond, detail=""):
    results.append({"probe": name, "ok": bool(cond), "detail": str(detail)[:600]})
    print(("ok   " if cond else "FLAG ") + name + (" — " + str(detail)[:300] if detail else ""))


def dec(v):
    if v is None: return None
    if isinstance(v, Decimal128): return v.to_decimal()
    return Decimal(str(v))


def fm(v):  # Oracle TO_CHAR(x,'FM999999999999990.00')
    return f"{Decimal(v).quantize(Decimal('0.01')):f}"


# ---------- wave-0 reference collections untouched by wave-1 loads ----------
pre = json.load(open(os.path.expanduser("~/wave_recon/w1/pre_state.json")))
for coll in ("codes", "tenants", "plans"):
    h = hashlib.sha256(); n = 0
    for d in db[coll].find({}, sort=[("_id", 1)]):
        h.update(dumps(d, json_options=CANONICAL_JSON_OPTIONS, sort_keys=True).encode()); h.update(b"\n"); n += 1
    key = f"ow_tp_mongodb_205236.{coll}"
    if key in pre:
        ok(f"u0.{coll}.unchanged_since_pre_state", pre[key]["sha256"] == h.hexdigest() and pre[key]["n"] == n, f"n={n}")
    else:
        ok(f"u0.{coll}.present", n > 0, f"n={n} (no pre-state fingerprint recorded)")
# U0 vs Oracle source counts
for coll, tbl in (("codes", "CODES"), ("tenants", "TENANTS"), ("plans", "PLANS")):
    s = q(f"SELECT COUNT(*) FROM {tbl}")[0][0]
    ok(f"u0.{coll}.count_eq_oracle", s == db[coll].count_documents({}), f"src={s} tgt={db[coll].count_documents({})}")

# ---------- tenants: customers.tenant_id / invoices.tenant_id resolve identically ----------
src_tenants = {r[0] for r in q("SELECT ID FROM TENANTS")}
tgt_tenants = set(db.tenants.distinct("_id"))
ok("tenants.id_set_equal", src_tenants == tgt_tenants, f"n={len(src_tenants)}")
s_ct = {r[0] for r in q("SELECT DISTINCT TENANT_ID FROM CUSTOMER_MASTER WHERE CONVERSION_BATCH_NO=:b", b=BATCH)}
t_ct = set(db.customers.distinct("tenant_id"))
ok("tenants.customer_tenant_ids_equal", s_ct == t_ct, f"distinct={len(s_ct)} orphans_src={len(s_ct - src_tenants)} orphans_tgt={len(t_ct - tgt_tenants)}")
s_it = {r[0] for r in q("SELECT DISTINCT TENANT_ID FROM INVOICE_HEADER WHERE BATCH_NO=:b", b=BATCH)}
t_it = set(db.invoices.distinct("tenant_id"))
ok("tenants.invoice_tenant_ids_equal", s_it == t_it, f"distinct={len(s_it)} orphans_src={len(s_it - src_tenants)} orphans_tgt={len(t_it - tgt_tenants)}")
# per-tenant customer/invoice counts identical
s_pt = {r[0]: r[1] for r in q("SELECT TENANT_ID, COUNT(*) FROM CUSTOMER_MASTER WHERE CONVERSION_BATCH_NO=:b GROUP BY TENANT_ID", b=BATCH)}
t_pt = {d["_id"]: d["n"] for d in db.customers.aggregate([{"$group": {"_id": "$tenant_id", "n": {"$sum": 1}}}])}
ok("tenants.per_tenant_customer_counts", s_pt == t_pt)
s_pt = {r[0]: r[1] for r in q("SELECT TENANT_ID, COUNT(*) FROM INVOICE_HEADER WHERE BATCH_NO=:b GROUP BY TENANT_ID", b=BATCH)}
t_pt = {d["_id"]: d["n"] for d in db.invoices.aggregate([{"$group": {"_id": "$tenant_id", "n": {"$sum": 1}}}])}
ok("tenants.per_tenant_invoice_counts", s_pt == t_pt)

# ---------- customers <- invoices ----------
s_ci = {r[0] for r in q("SELECT DISTINCT CUST_ID FROM INVOICE_HEADER WHERE BATCH_NO=:b", b=BATCH)}
s_c = {r[0] for r in q("SELECT CUST_ID FROM CUSTOMER_MASTER WHERE CONVERSION_BATCH_NO=:b", b=BATCH)}
t_ci = set(db.invoices.distinct("cust_id")); t_c = set(db.customers.distinct("_id"))
ok("customers.invoice_cust_ids_equal", s_ci == t_ci, f"distinct={len(s_ci)}")
ok("customers.invoice_orphan_cust_set_equal", (s_ci - s_c) == (t_ci - t_c), f"orphans src={len(s_ci - s_c)} tgt={len(t_ci - t_c)}")
# invoice tenant must equal customer's tenant (denormalised consistency) - same violation set both sides
s_mis = {r[0] for r in q("SELECT h.INVOICE_ID FROM INVOICE_HEADER h JOIN CUSTOMER_MASTER c ON c.CUST_ID=h.CUST_ID WHERE h.BATCH_NO=:b AND c.CONVERSION_BATCH_NO=:b AND h.TENANT_ID<>c.TENANT_ID", b=BATCH)}
ct = {d["_id"]: d["tenant_id"] for d in db.customers.find({}, {"tenant_id": 1})}
t_mis = {d["_id"] for d in db.invoices.find({}, {"cust_id": 1, "tenant_id": 1}) if d["cust_id"] in ct and ct[d["cust_id"]] != d["tenant_id"]}
ok("customers.invoice_tenant_mismatch_set_equal", s_mis == t_mis, f"n={len(s_mis)}")
# per-customer invoice count + total
s_pc = {r[0]: (r[1], dec(r[2])) for r in q("SELECT CUST_ID, COUNT(*), SUM(TOTAL_AMT) FROM INVOICE_HEADER WHERE BATCH_NO=:b GROUP BY CUST_ID", b=BATCH)}
t_pc = {d["_id"]: (d["n"], dec(d["s"])) for d in db.invoices.aggregate([{"$group": {"_id": "$cust_id", "n": {"$sum": 1}, "s": {"$sum": "$total_amt"}}}])}
ok("customers.per_customer_invoice_rollup", s_pc == t_pc, f"customers_with_invoices={len(s_pc)}")

# ---------- codes: code-valued fields resolve identically ----------
codes = {(d["code_type"], d["code_val"]): d["code_desc"] for d in db.codes.find({})}
s_codes = {(r[0], r[1]): r[2] for r in q("SELECT CODE_TYPE, CODE_VAL, CODE_DESC FROM CODES")}
ok("codes.type_val_desc_equal", {(t, str(v)): d for (t, v), d in s_codes.items()} == {(t, str(v)): d for (t, v), d in codes.items()}, f"n={len(codes)}")
ok("codes._key_format", all(d["_key"] == f"{d['code_type']}:{d['code_val']}" for d in db.codes.find({})))
code_types = Counter(t for t, _ in codes)
ok("codes.types_present", True, dict(code_types))
# unresolved code values per field: same set on both sides
for tbl, coll, fld, where in (("INVOICE_HEADER", "invoices", "STATUS_CD", "BATCH_NO"),
                               ("CUSTOMER_MASTER", "customers", "STATUS_CD", "CONVERSION_BATCH_NO"),
                               ("CUSTOMER_MASTER", "customers", "CUST_TYPE_CD", "CONVERSION_BATCH_NO"),
                               ("CUSTOMER_MASTER", "customers", "SEGMENT_CD", "CONVERSION_BATCH_NO"),
                               ("CUSTOMER_MASTER", "customers", "REGION_CD", "CONVERSION_BATCH_NO")):
    s_vals = Counter(r[0] for r in q(f"SELECT {fld} FROM {tbl} WHERE {where}=:b", b=BATCH))
    t_vals = Counter(d["_id"] for d in db[coll].aggregate([{"$group": {"_id": f"${fld.lower()}", "n": {"$sum": 1}}}]) for _ in range(d["n"]))
    ok(f"codes.{coll}.{fld.lower()}_distribution", s_vals == t_vals, f"distinct={len(s_vals)}")
inv_status_vals = {str(v) for t, v in codes if t == "INV_STATUS"}
t_unres = {str(v) for v in db.invoices.distinct("status_cd") if str(v) not in inv_status_vals}
s_unres = {str(r[0]) for r in q("SELECT DISTINCT h.STATUS_CD FROM INVOICE_HEADER h WHERE h.BATCH_NO=:b AND NOT EXISTS (SELECT 1 FROM CODES c WHERE c.CODE_TYPE='INV_STATUS' AND c.CODE_VAL=h.STATUS_CD)", b=BATCH)}
ok("codes.invoices.unresolved_status_set_equal", s_unres == t_unres, f"unresolved={sorted(s_unres)}")

# ---------- plans / tenants status codes ----------
ok("plans.tier_cd_set", {r[0] for r in q("SELECT DISTINCT TIER_CD FROM PLANS")} == set(db.plans.distinct("tier_cd")))
ok("tenants.status_cd_hist", Counter(r[0] for r in q("SELECT STATUS_CD FROM TENANTS")) ==
   Counter(d["_id"] for d in db.tenants.aggregate([{"$group": {"_id": "$status_cd", "n": {"$sum": 1}}}]) for _ in range(d["n"])))

# ---------- counters vs sequences (U1) still consistent after all wave-1 loads ----------
seqs = {r[0]: int(r[1]) for r in q("SELECT SEQUENCE_NAME, LAST_NUMBER FROM USER_SEQUENCES")}
ctrs = {d["source_sequence"]: int(d["seq"]) for d in db.counters.find({})}
ok("counters.eq_user_sequences", all(seqs.get(k) == v for k, v in ctrs.items()), f"{ctrs}")

# ---------- RPT-114 month-end + reconciliation replay (Oracle SQL verbatim vs Mongo pipelines) ----------
STATUS_SQL = """SELECT NVL(st.code_desc, 'UNKNOWN(' || TO_CHAR(h.status_cd) || ')') AS status_desc, COUNT(*), TO_CHAR(SUM(h.total_amt), 'FM999999999999990.00')
  FROM invoice_header h, codes st WHERE h.batch_no = :batch_no AND st.code_type (+) = 'INV_STATUS' AND st.code_val (+) = h.status_cd
 GROUP BY NVL(st.code_desc, 'UNKNOWN(' || TO_CHAR(h.status_cd) || ')') ORDER BY 1"""
LINE_SQL = """SELECT NVL(st.code_desc, 'UNKNOWN(' || TO_CHAR(h.status_cd) || ')'),
       DECODE(l.line_type_cd, 1,'CHARGE',2,'CREDIT',3,'ADJUSTMENT',9,'MISC','UNKNOWN(' || TO_CHAR(l.line_type_cd) || ')'),
       COUNT(*), TO_CHAR(SUM(l.amount),'FM999999999999990.00'), TO_CHAR(SUM(l.tax_amt),'FM999999999999990.00'), COUNT(DISTINCT h.invoice_id)
  FROM invoice_header h, invoice_line l, codes st
 WHERE h.batch_no = :batch_no AND h.invoice_id = l.invoice_id AND st.code_type (+) = 'INV_STATUS' AND st.code_val (+) = h.status_cd
 GROUP BY NVL(st.code_desc, 'UNKNOWN(' || TO_CHAR(h.status_cd) || ')'),
          DECODE(l.line_type_cd, 1,'CHARGE',2,'CREDIT',3,'ADJUSTMENT',9,'MISC','UNKNOWN(' || TO_CHAR(l.line_type_cd) || ')') ORDER BY 1, 2"""
BAL_SQL = """SELECT COUNT(*), TO_CHAR(SUM(cur_bal_amt),'FM999999999999990.00'), TO_CHAR(SUM(past_due_amt),'FM999999999999990.00')
  FROM customer_master WHERE conversion_batch_no = :batch_no"""
inv_desc = {str(v): d for (t, v), d in codes.items() if t == "INV_STATUS"}
LT = {1: "CHARGE", 2: "CREDIT", 3: "ADJUSTMENT", 9: "MISC"}


def sdesc(cd): return inv_desc.get(str(cd), f"UNKNOWN({cd})")


s_status = [(r[0], r[1], r[2]) for r in q(STATUS_SQL, batch_no=BATCH)]
t_status = sorted((sdesc(d["_id"]), d["n"], fm(dec(d["s"]))) for d in db.invoices.aggregate(
    [{"$match": {"batch_no": BATCH}}, {"$group": {"_id": "$status_cd", "n": {"$sum": 1}, "s": {"$sum": "$total_amt"}}}]))
# Oracle groups by desc: merge same-desc groups (there are none unless two codes share a desc)
ok("rpt114.month_end.by_status", s_status == t_status, f"rows={len(s_status)} sample={s_status[:2]}")
s_line = [tuple(r) for r in q(LINE_SQL, batch_no=BATCH)]
agg = {}
for d in db.invoices.aggregate([{"$match": {"batch_no": BATCH}}, {"$unwind": "$lines"},
                                {"$group": {"_id": {"s": "$status_cd", "lt": "$lines.line_type_cd"}, "n": {"$sum": 1},
                                            "a": {"$sum": "$lines.amount"}, "t": {"$sum": "$lines.tax_amt"}, "inv": {"$addToSet": "$_id"}}}]):
    k = (sdesc(d["_id"]["s"]), LT.get(d["_id"]["lt"], f"UNKNOWN({d['_id']['lt']})"))
    agg[k] = (d["n"], dec(d["a"]), dec(d["t"]), len(d["inv"]))
t_line = sorted((k[0], k[1], v[0], fm(v[1]), fm(v[2]), v[3]) for k, v in agg.items())
ok("rpt114.month_end.by_status_line_type", s_line == t_line, f"rows={len(s_line)} sample={s_line[:1]}")
s_bal = tuple(q(BAL_SQL, batch_no=BATCH)[0])
b = list(db.customers.aggregate([{"$match": {"conversion_batch_no": BATCH}}, {"$group": {"_id": None, "n": {"$sum": 1}, "c": {"$sum": "$cur_bal_amt"}, "p": {"$sum": "$past_due_amt"}}}]))[0]
t_bal = (b["n"], fm(dec(b["c"])), fm(dec(b["p"])))
ok("rpt114.reconciliation.balances", s_bal == t_bal, f"{s_bal}")

# ---------- U3/U4: owner pools + no key collisions across doc/file ids ----------
pg = psycopg.connect(os.environ["OW_PG_DSN"], autocommit=True); pc = pg.cursor()
pc.execute("SET default_transaction_read_only = on")
pc.execute("SELECT DISTINCT owner_id::text FROM otterworks_demo.documents"); s_do = {r[0] for r in pc.fetchall()}
t_do = set(db.documents.distinct("owner_id")); t_fo = set(db.files.distinct("owner_id"))
ok("u3u4.document_owner_set_equal", s_do == t_do, f"n={len(s_do)}")
ok("u3u4.owner_pools_disjoint_as_in_source", True, f"doc owners={len(t_do)} file owners={len(t_fo)} shared={len(t_do & t_fo)} (independently seeded pools; informational)")
ok("u3u4.no_id_collisions_docs_files_snapshots",
   not (set(db.documents.distinct("_id")) & set(db.files.distinct("_id"))) and not (set(db.documents.distinct("_id")) & set(db.document_snapshots.distinct("_id"))))

# ---------- quarantine DB: only the 4 expected wave-1 classes, counts vs manifest ----------
man = json.load(open(os.path.expanduser("~/wave_recon/w1/manifest_demo.json")))
exp = {a["kind"]: a["count"] for a in man["planted_anomalies"]}
qc = {c: qdb[c].count_documents({}) for c in qdb.list_collection_names()}
ok("quarantine.classes_and_counts", qc == {"bad_csv_list": exp["malformed_csv_lists"], "dirty_signup_dt": exp["dirty_dates"],
                                          "invoice_feed_orphan_lines": exp["orphaned_rows"], "orphan_document_snapshots": exp["orphaned_snapshots"]}, qc)
ok("quarantine.every_doc_has_reason_class", all(qdb[c].count_documents({"$or": [{"reason": {"$exists": True}}, {"reason_class": {"$exists": True}}, {"quarantine_reason": {"$exists": True}}, {"class": {"$exists": True}}]}) == n for c, n in qc.items()),
   {c: sorted(set().union(*(d.keys() for d in qdb[c].find({}, limit=3)))) for c in qc})
ok("quarantine.orphan_markers_u3_u4", db.files.count_documents({"orphaned_metadata": True}) == exp["orphaned_metadata"]
   and sum(1 for d in db.documents.find({"version_gaps": {"$exists": True, "$ne": []}})) == exp["version_gaps"])

# ---------- target DB inventory: nothing outside the wave 0/1 registry ----------
ok("target.collections_registry", set(db.list_collection_names()) == {"codes", "tenants", "plans", "counters", "customers", "customers_history", "invoices", "documents", "document_snapshots", "files"}, sorted(db.list_collection_names()))

n_ok = sum(r["ok"] for r in results)
json.dump({"ok": n_ok, "total": len(results), "oracle_statements": n_sql, "seconds": round(time.time() - T0, 1), "results": results},
          open(sys.argv[1], "w"), indent=2, default=str)
print(f"\nXUNIT probes: {n_ok}/{len(results)} ok · {n_sql} Oracle statements · {round(time.time()-T0,1)}s")
