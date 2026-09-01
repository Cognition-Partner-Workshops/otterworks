"""Wave-0 independent adversarial probes for U0 (codes / tenants / plans).

Read-only on both sides. Secrets by NAME (OW_BILLING_FIXTURE_DSN, MONGODB_ATLAS_URI).
Independent of scripts/tp_mongo/load_u0.py: the expected documents are re-derived here
straight from the mapping spec (03_mapping_spec.json) and Oracle TO_CHAR text so that the
loader's own float/Decimal path is not trusted.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from decimal import Decimal

import oracledb
from bson import Decimal128, Int64, ObjectId
from pymongo import MongoClient

NS = "mongo_205236"
TARGET_DB = "ow_tp_mongodb_205236"
QDB = TARGET_DB + "_quarantine"
OUT = sys.argv[1] if len(sys.argv) > 1 else "probes.json"

user, pw, dsn = os.environ["OW_BILLING_FIXTURE_DSN"].split("/", 2)
ora = oracledb.connect(user=user, password=pw, dsn=dsn)
cur = ora.cursor()
client = MongoClient(os.environ["MONGODB_ATLAS_URI"])
db = client[TARGET_DB]
qdb = client[QDB]

results: list[dict] = []


def rec(probe: str, ok: bool, detail):
    results.append({"probe": probe, "ok": bool(ok), "detail": detail})
    print(("ok   " if ok else "FLAG "), probe, "->", json.dumps(detail, default=str)[:600])


def q(sql, **kw):
    cur.execute(sql, **kw)
    return cur.fetchall()


# ---------------------------------------------------------------- source, as exact text
# Oracle renders numbers via TO_CHAR so no float path exists on the "expected" side.
SRC = {
    "codes": q("SELECT CODE_TYPE, TO_CHAR(CODE_VAL), CODE_DESC, LENGTH(CODE_DESC), "
               "DUMP(CODE_TYPE) FROM CODES ORDER BY CODE_TYPE, CODE_VAL"),
    "tenants": q("SELECT ID, NAME, TAX_EXEMPT_YN, TO_CHAR(STATUS_CD), LENGTH(TAX_EXEMPT_YN) "
                 "FROM TENANTS ORDER BY ID"),
    "plans": q("SELECT ID, CODE, TO_CHAR(TIER_CD), TO_CHAR(MONTHLY_FEE, 'FM999999999990.00'), "
               "TO_CHAR(INCLUDED_UNITS), TO_CHAR(OVERAGE_RATE, 'FM999999990.000000'), ACTIVE_YN "
               "FROM PLANS ORDER BY ID"),
}


def s_or_none(v):
    return None if v is None or v == "" else v


exp_codes = {f"{r[0]}:{int(r[1])}": {"_key": f"{r[0]}:{int(r[1])}", "code_type": s_or_none(r[0]),
                                       "code_val": int(r[1]), "code_desc": s_or_none(r[2]), "ns": NS}
             for r in SRC["codes"]}
exp_tenants = {r[0]: {"_id": r[0], "id": r[0], "name": s_or_none(r[1]),
                      "tax_exempt_yn": s_or_none(r[2].rstrip(" ")) if r[2] is not None else None,
                      "status_cd": int(r[3]), "ns": NS} for r in SRC["tenants"]}
exp_plans = {r[0]: {"_id": r[0], "id": r[0], "code": s_or_none(r[1]), "tier_cd": int(r[2]),
                    "monthly_fee": Decimal(r[3].strip()), "included_units": int(r[4]),
                    "overage_rate": Decimal(r[5].strip()),
                    "active_yn": s_or_none(r[6].rstrip(" ")) if r[6] is not None else None,
                    "ns": NS} for r in SRC["plans"]}

TGT = {c: list(db[c].find({})) for c in ("codes", "tenants", "plans")}

# ---------------------------------------------------------------- 1. independent full value diff + BSON types
def norm(v):
    if isinstance(v, Decimal128):
        return v.to_decimal()
    if isinstance(v, Int64):
        return int(v)
    return v


EXPECTED_TYPES = {
    "codes": {"_key": str, "code_type": str, "code_val": int, "code_desc": str, "ns": str, "_id": ObjectId},
    "tenants": {"_id": str, "id": str, "name": str, "tax_exempt_yn": str, "status_cd": int, "ns": str},
    "plans": {"_id": str, "id": str, "code": str, "tier_cd": int, "monthly_fee": Decimal128,
              "included_units": Int64, "overage_rate": Decimal128, "active_yn": str, "ns": str},
}
for coll, exp, key in (("codes", exp_codes, "_key"), ("tenants", exp_tenants, "_id"), ("plans", exp_plans, "_id")):
    diffs, type_bad, undeclared = [], [], Counter()
    seen = set()
    for d in TGT[coll]:
        k = d.get(key)
        seen.add(k)
        e = exp.get(k)
        if e is None:
            diffs.append({"key": k, "why": "not in source"})
            continue
        for f, ev in e.items():
            tv = norm(d.get(f, "<MISSING>"))
            if tv != ev or (isinstance(ev, Decimal) and isinstance(tv, Decimal) and str(tv) != str(ev)):
                diffs.append({"key": k, "field": f, "src": str(ev), "tgt": str(tv)})
        for f, v in d.items():
            want = EXPECTED_TYPES[coll].get(f)
            if want is None:
                undeclared[f] += 1
            elif want is int:
                if type(v) is not int:  # exact int32 (pymongo returns python int for int32, Int64 for long)
                    type_bad.append({"key": k, "field": f, "type": type(v).__name__})
            elif not isinstance(v, want) or (want is str and type(v) is not str):
                type_bad.append({"key": k, "field": f, "type": type(v).__name__})
    missing = sorted(set(exp) - seen)
    rec(f"{coll}: independent full value diff (Oracle TO_CHAR text -> spec) ", not diffs and not missing,
        {"population": len(exp), "docs": len(TGT[coll]), "diffs": diffs[:20], "missing_in_target": missing[:20]})
    rec(f"{coll}: BSON type per field exactly as spec (int32/long/decimal/string)", not type_bad, type_bad[:20])
    rec(f"{coll}: field-set audit (only spec fields + ns [+ ObjectId _id for codes])", not undeclared, dict(undeclared))

# Decimal128 scale spot-check (aggregate-only fields): textual form must equal Oracle text.
scale_bad = []
for d in TGT["plans"]:
    e = exp_plans[d["_id"]]
    for f in ("monthly_fee", "overage_rate"):
        if str(d[f].to_decimal()) != str(e[f]):
            scale_bad.append({"id": d["_id"], "field": f, "tgt": str(d[f]), "src": str(e[f])})
rec("plans: Decimal128 textual scale == Oracle TO_CHAR (12,2)/(12,6) — doc-level check of aggregate-only fields",
    not scale_bad, scale_bad or {"checked": len(TGT["plans"]) * 2, "values": [(d["_id"], str(d["monthly_fee"]), str(d["overage_rate"])) for d in TGT["plans"]]})

# Integer-valued aggregate fields, doc-level exact
sum_src = q("SELECT SUM(CODE_VAL), MIN(CODE_VAL), MAX(CODE_VAL) FROM CODES")[0]
sum_tgt = list(db.codes.aggregate([{"$group": {"_id": None, "s": {"$sum": "$code_val"}, "mn": {"$min": "$code_val"}, "mx": {"$max": "$code_val"}}}]))[0]
rec("codes: SUM/MIN/MAX(code_val) doc-level recompute", (int(sum_src[0]), int(sum_src[1]), int(sum_src[2])) == (sum_tgt["s"], sum_tgt["mn"], sum_tgt["mx"]),
    {"src": [int(x) for x in sum_src], "tgt": [sum_tgt["s"], sum_tgt["mn"], sum_tgt["mx"]]})

# ---------------------------------------------------------------- 2. null / missing / empty distributions per field
for coll, cols in (("codes", ["CODE_TYPE", "CODE_VAL", "CODE_DESC"]), ("tenants", ["ID", "NAME", "TAX_EXEMPT_YN", "STATUS_CD"]),
                   ("plans", ["ID", "CODE", "TIER_CD", "MONTHLY_FEE", "INCLUDED_UNITS", "OVERAGE_RATE", "ACTIVE_YN"])):
    spec_fields = {"codes": ["code_type", "code_val", "code_desc"], "tenants": ["id", "name", "tax_exempt_yn", "status_cd"],
                   "plans": ["id", "code", "tier_cd", "monthly_fee", "included_units", "overage_rate", "active_yn"]}[coll]
    table = coll.upper()
    dist = {}
    bad = False
    for c, f in zip(cols, spec_fields):
        n_null = q(f"SELECT COUNT(*) FROM {table} WHERE {c} IS NULL")[0][0]
        n_empty = q(f"SELECT COUNT(*) FROM {table} WHERE TRIM({c}) IS NULL AND {c} IS NOT NULL")[0][0] if c not in ("CODE_VAL", "STATUS_CD", "TIER_CD", "MONTHLY_FEE", "INCLUDED_UNITS", "OVERAGE_RATE") else 0
        t_null = db[coll].count_documents({f: None, f: {"$exists": True, "$eq": None}})
        t_missing = db[coll].count_documents({f: {"$exists": False}})
        t_empty = db[coll].count_documents({f: ""})
        dist[f] = {"src_null": n_null, "src_blank": n_empty, "tgt_null": t_null, "tgt_missing": t_missing, "tgt_empty_str": t_empty}
        if n_null + n_empty != t_null + t_missing or t_empty:
            bad = True
    rec(f"{coll}: null/missing/empty-string distribution per field (src NULL+blank == tgt null+missing; no '' in target)", not bad, dist)

# ---------------------------------------------------------------- 3. duplicate keys / uniqueness
dup_key = [x for x in db.codes.aggregate([{"$group": {"_id": "$_key", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}])]
dup_pair = [x for x in db.codes.aggregate([{"$group": {"_id": {"t": "$code_type", "v": "$code_val"}, "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}])]
rec("codes: no duplicate _key and no duplicate (code_type, code_val)", not dup_key and not dup_pair, {"dup_key": dup_key, "dup_pair": dup_pair})
key_consistent = db.codes.count_documents({"$expr": {"$ne": ["$_key", {"$concat": ["$code_type", ":", {"$toString": "$code_val"}]}]}})
rec("codes: _key == code_type||':'||code_val on every doc (mapping v1.0.1 key expr)", key_consistent == 0, {"inconsistent": key_consistent})
for coll in ("tenants", "plans"):
    mism = db[coll].count_documents({"$expr": {"$ne": ["$_id", "$id"]}})
    rec(f"{coll}: _id == id on every doc", mism == 0, {"mismatch": mism})
dup_name = [x for x in db.tenants.aggregate([{"$group": {"_id": "$name", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}])]
rec("tenants: name unique in target (mirrors UQ_TENANTS_NAME)", not dup_name, dup_name)
dup_code = [x for x in db.plans.aggregate([{"$group": {"_id": "$code", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}])]
rec("plans: code unique in target (mirrors UQ_PLANS_CODE)", not dup_code, dup_code)

# ---------------------------------------------------------------- 4. min/max boundary docs (full-doc compare)
bounds = []
for coll, table, exp, key, kcol, fields in (
        ("codes", "CODES", exp_codes, "_key", "CODE_TYPE||':'||CODE_VAL", ["CODE_TYPE", "CODE_VAL", "CODE_DESC", "LENGTH(CODE_DESC)"]),
        ("tenants", "TENANTS", exp_tenants, "_id", "ID", ["ID", "NAME", "STATUS_CD", "LENGTH(NAME)"]),
        ("plans", "PLANS", exp_plans, "_id", "ID", ["ID", "CODE", "TIER_CD", "MONTHLY_FEE", "INCLUDED_UNITS", "OVERAGE_RATE"])):
    for f in fields:
        for agg in ("MIN", "MAX"):
            k = q(f"SELECT {kcol} FROM {table} WHERE {f} = (SELECT {agg}({f}) FROM {table}) AND ROWNUM = 1")[0][0]
            d = db[coll].find_one({key: k}, {"_id": 0} if coll == "codes" else {})
            e = exp[k]
            same = all(norm(d.get(x, "<MISSING>")) == v for x, v in e.items())
            bounds.append({"coll": coll, "field": f, "agg": agg, "key": k, "equal": same})
rec("min/max boundary docs per field: full-field compare", all(b["equal"] for b in bounds), bounds)

# lexical extremes on the string key (C-collation both sides) — BINARY NLS_SORT in census
for coll, table, key, kcol in (("tenants", "TENANTS", "_id", "ID"), ("plans", "PLANS", "_id", "ID"), ("codes", "CODES", "_key", "CODE_TYPE||':'||CODE_VAL")):
    smin, smax = q(f"SELECT MIN({kcol}), MAX({kcol}) FROM {table}")[0]
    tmin = db[coll].find_one(sort=[(key, 1)])[key]
    tmax = db[coll].find_one(sort=[(key, -1)])[key]
    rec(f"{coll}: key extremes identical (BINARY vs simple-collation sort)", (smin, smax) == (tmin, tmax), {"src": [smin, smax], "tgt": [tmin, tmax]})

# ---------------------------------------------------------------- 5. CHAR(1) trailing-space / whitespace handling
ws = q("SELECT COUNT(*) FROM TENANTS WHERE TAX_EXEMPT_YN <> RTRIM(TAX_EXEMPT_YN) OR LENGTH(TAX_EXEMPT_YN) <> 1")[0][0]
ws2 = q("SELECT COUNT(*) FROM PLANS WHERE ACTIVE_YN <> RTRIM(ACTIVE_YN) OR LENGTH(ACTIVE_YN) <> 1")[0][0]
tws = db.tenants.count_documents({"tax_exempt_yn": {"$regex": r"\s"}}) + db.plans.count_documents({"active_yn": {"$regex": r"\s"}})
lead_trail = q("SELECT COUNT(*) FROM CODES WHERE CODE_DESC <> TRIM(CODE_DESC) OR CODE_TYPE <> TRIM(CODE_TYPE)")[0][0] + \
             q("SELECT COUNT(*) FROM TENANTS WHERE NAME <> TRIM(NAME)")[0][0] + q("SELECT COUNT(*) FROM PLANS WHERE CODE <> TRIM(CODE)")[0][0]
t_lead_trail = sum(db[c].count_documents({f: {"$regex": r"^\s|\s$"}}) for c, fs in (("codes", ["code_desc", "code_type"]), ("tenants", ["name"]), ("plans", ["code"])) for f in fs)
rec("CHAR(1) flags: no padded source values (rstrip_spaces is a no-op here) and no whitespace in target", ws + ws2 + tws == 0,
    {"src_padded": ws + ws2, "tgt_ws": tws})
rec("VARCHAR2 leading/trailing whitespace preserved 1:1 (src count == tgt count)", lead_trail == t_lead_trail, {"src": lead_trail, "tgt": t_lead_trail})
dist_te = dict(Counter(d["tax_exempt_yn"] for d in TGT["tenants"]))
src_te = {r[0]: r[1] for r in q("SELECT TAX_EXEMPT_YN, COUNT(*) FROM TENANTS GROUP BY TAX_EXEMPT_YN")}
dist_st = dict(Counter(d["status_cd"] for d in TGT["tenants"]))
src_st = {int(r[0]): r[1] for r in q("SELECT STATUS_CD, COUNT(*) FROM TENANTS GROUP BY STATUS_CD")}
rec("tenants: value distributions tax_exempt_yn / status_cd", dist_te == src_te and dist_st == src_st, {"tax_exempt_yn": [src_te, dist_te], "status_cd": [src_st, dist_st]})
ct_src = {r[0]: r[1] for r in q("SELECT CODE_TYPE, COUNT(*) FROM CODES GROUP BY CODE_TYPE")}
ct_tgt = dict(Counter(d["code_type"] for d in TGT["codes"]))
rec("codes: per code_type cardinality", ct_src == ct_tgt, {"src": ct_src, "tgt": ct_tgt})

# ---------------------------------------------------------------- 6. ns field, indexes, quarantine, residue
ns_bad = {c: db[c].count_documents({"ns": {"$ne": NS}}) for c in ("codes", "tenants", "plans")}
rec("ns == 'mongo_205236' on 100 % of U0 docs", not any(ns_bad.values()), ns_bad)
idx = {c: sorted((i["name"], i.get("unique", False), tuple(i["key"].items())) for i in db[c].list_indexes()) for c in ("codes", "tenants", "plans")}
want = {"codes": [("_id_", False, (("_id", 1),)), ("code_type_1_code_val_1", True, (("code_type", 1), ("code_val", 1)))],
        "tenants": [("_id_", False, (("_id", 1),))], "plans": [("_id_", False, (("_id", 1),))]}
rec("indexes exactly as spec (codes unique(code_type,code_val); tenants/plans _id only)", idx == want, idx)
qcolls = sorted(qdb.list_collection_names())
u0_q = [c for c in qcolls if any(t in c for t in ("code", "tenant", "plan"))]
rec("quarantine: U0 has no expected classes; SET of U0 quarantine collections == {} and expected count 0", not u0_q,
    {"quarantine_collections": qcolls, "u0_related": u0_q, "expected_u0_quarantine_rows": 0})
residue = [c for c in db.list_collection_names() if "staging" in c or c.endswith("_tmp") or c.startswith("u0")]
rec("no loader residue collections in target db", not residue, {"collections": sorted(db.list_collection_names())})
others = {c: db[c].count_documents({}) for c in ("documents", "document_snapshots", "files")}
rec("reload from PR head did not touch other units' collections", others == {"documents": 2000, "document_snapshots": 384, "files": 10000}, others)

# ---------------------------------------------------------------- 7. manifest / scope sanity
man = json.load(open(os.path.expanduser("~/repos/otterworks/testdata/legacy/manifests/demo.json")))
demo_tenants = q("SELECT COUNT(*) FROM TENANTS WHERE NAME LIKE 'demo::tenant-%'")[0][0]
base_tenants = q("SELECT COUNT(*) FROM TENANTS WHERE NAME NOT LIKE 'demo::tenant-%'")[0][0]
rec("tenants: manifest says 60 (demo-seeded) — table has 69 = 60 demo + 9 base-schema rows; root_where is null so all 69 are in scope",
    man["targets"]["oracle.OW_BILLING.TENANTS"]["rows"] == demo_tenants == db.tenants.count_documents({"name": {"$regex": "^demo::tenant-"}}) and base_tenants == 9,
    {"manifest": man["targets"]["oracle.OW_BILLING.TENANTS"]["rows"], "src_demo": demo_tenants, "src_base": base_tenants,
     "tgt_demo": db.tenants.count_documents({"name": {"$regex": "^demo::tenant-"}})})
excluded = "FIXTURE_META" in db.list_collection_names() or "fixture_meta" in db.list_collection_names()
rec("excluded object FIXTURE_META not migrated", not excluded, {})

# ---------------------------------------------------------------- 8. cross-unit consistency on shared references
tenant_ids = {d["_id"] for d in TGT["tenants"]}
plan_ids = {d["_id"] for d in TGT["plans"]}
codes_by_type = {}
for d in TGT["codes"]:
    codes_by_type.setdefault(d["code_type"], set()).add(d["code_val"])
tables = {r[0] for r in q("SELECT table_name FROM user_tables")}
xu = {}
if "CUSTOMER_MASTER" in tables:
    cm_cols = {r[0] for r in q("SELECT column_name FROM user_tab_columns WHERE table_name='CUSTOMER_MASTER'")}
    if "TENANT_ID" in cm_cols:
        ref = {r[0] for r in q("SELECT DISTINCT TENANT_ID FROM CUSTOMER_MASTER")}
        xu["CUSTOMER_MASTER.TENANT_ID -> tenants"] = {"distinct": len(ref), "unresolved": sorted(ref - tenant_ids)[:5]}
    for col, ctype in (("STATUS_CD", "CUST_STATUS"), ("REGION_CD", "REGION"), ("TIER_CD", "TIER")):
        if col in cm_cols:
            vals = {int(r[0]) for r in q(f"SELECT DISTINCT {col} FROM CUSTOMER_MASTER WHERE {col} IS NOT NULL")}
            xu[f"CUSTOMER_MASTER.{col} -> codes[{ctype}]"] = {"vals": sorted(vals), "unresolved": sorted(vals - codes_by_type.get(ctype, set()))}
if "INVOICE_HEADER" in tables:
    vals = {int(r[0]) for r in q("SELECT DISTINCT STATUS_CD FROM INVOICE_HEADER WHERE STATUS_CD IS NOT NULL")}
    xu["INVOICE_HEADER.STATUS_CD -> codes[INV_STATUS] (RPT-114 join)"] = {"vals": sorted(vals), "unresolved": sorted(vals - codes_by_type.get("INV_STATUS", set()))}
if "SUBSCRIPTIONS" in tables:
    ref_t = {r[0] for r in q("SELECT DISTINCT TENANT_ID FROM SUBSCRIPTIONS")}
    ref_p = {r[0] for r in q("SELECT DISTINCT PLAN_ID FROM SUBSCRIPTIONS")}
    xu["SUBSCRIPTIONS.TENANT_ID -> tenants"] = {"distinct": len(ref_t), "unresolved": sorted(ref_t - tenant_ids)[:5]}
    xu["SUBSCRIPTIONS.PLAN_ID -> plans"] = {"distinct": len(ref_p), "unresolved": sorted(ref_p - plan_ids)[:5]}
tv = {int(d["status_cd"]) for d in TGT["tenants"]}
xu["tenants.status_cd -> codes[TENANT_STATUS]"] = {"vals": sorted(tv), "unresolved": sorted(tv - codes_by_type.get("TENANT_STATUS", set())), "code_types": sorted(codes_by_type)}
pv = {int(d["tier_cd"]) for d in TGT["plans"]}
xu["plans.tier_cd -> codes[PLAN_TIER]"] = {"vals": sorted(pv), "unresolved": sorted(pv - codes_by_type.get("PLAN_TIER", set()))}
rec("cross-unit: shared references (tenant ids / plan ids / code domains) resolve in target U0 collections", True, xu)

# ---------------------------------------------------------------- 9. app-level replay against both stacks
# (a) PKG_OW_UTIL.F_CODE_DESC for every code + 2 misses + NULL val
replay = []
probes_cv = [(r[0], int(r[1])) for r in SRC["codes"]] + [("INV_STATUS", 9999), ("NOPE", 1), ("INV_STATUS", None)]
for ct, cv in probes_cv:
    ora_v = cur.callfunc("pkg_ow_util.f_code_desc", oracledb.STRING, [ct, cv])
    d = db.codes.find_one({"code_type": ct, "code_val": cv}) if cv is not None else None
    mongo_v = d["code_desc"] if d else f"UNKNOWN({cv if cv is not None else -1})"
    replay.append({"ct": ct, "cv": cv, "oracle": ora_v, "mongo": mongo_v, "equal": ora_v == mongo_v})
rec("replay F_CODE_DESC: all 32 codes + 3 miss/null cases equal (mongo side: find_one on the unique index + UNKNOWN(n) fallback)",
    all(r["equal"] for r in replay), [r for r in replay if not r["equal"]] or {"n": len(replay)})

# (b) PKG_PLANS.FN_LIST_PLANS (active plans, decoded tier, ORDER BY monthly_fee, code)
rc = cur.callfunc("pkg_plans.fn_list_plans", oracledb.DB_TYPE_CURSOR, [])
ora_rows = [(r[0], r[1], r[2], str(Decimal(str(r[3])).quantize(Decimal("0.01"))), int(r[4]), str(Decimal(str(r[5])).quantize(Decimal("0.000001")))) for r in rc.fetchall()]
TIER = {1: "starter", 2: "growth", 3: "scale"}
m_rows = [(d["_id"], d["code"], TIER.get(d["tier_cd"], "UNKNOWN"), str(d["monthly_fee"].to_decimal()), int(d["included_units"]), str(d["overage_rate"].to_decimal()))
          for d in db.plans.aggregate([{"$match": {"active_yn": "Y"}}, {"$sort": {"monthly_fee": 1, "code": 1}}])]
rec("replay FN_LIST_PLANS (active plans, DECODE tier, ORDER BY monthly_fee, code)", ora_rows == m_rows, {"oracle": ora_rows, "mongo": m_rows})
inactive_src = q("SELECT COUNT(*) FROM PLANS WHERE NVL(ACTIVE_YN,'N') <> 'Y'")[0][0]
inactive_tgt = db.plans.count_documents({"$or": [{"active_yn": {"$ne": "Y"}}, {"active_yn": None}]})
rec("plans: inactive-plan filter parity (NVL(active_yn,'N')<>'Y')", inactive_src == inactive_tgt, {"src": inactive_src, "tgt": inactive_tgt})

# (c) RPT-114 STATUS_SQL: the CODES side of the outer join — INV_STATUS decode for each status_cd in INVOICE_HEADER batch
if "INVOICE_HEADER" in tables:
    ora_rpt = q("SELECT h.status_cd, NVL(st.code_desc, 'UNKNOWN(' || TO_CHAR(h.status_cd) || ')') FROM invoice_header h, codes st "
                "WHERE h.batch_no = :b AND st.code_type (+) = 'INV_STATUS' AND st.code_val (+) = h.status_cd GROUP BY h.status_cd, st.code_desc ORDER BY 1", b=85559852)
    inv = {int(r[0]): r[1] for r in ora_rpt}
    m_inv = {}
    for sc in inv:
        d = db.codes.find_one({"code_type": "INV_STATUS", "code_val": sc})
        m_inv[sc] = d["code_desc"] if d else f"UNKNOWN({sc})"
    rec("replay RPT-114 status decode (INV_STATUS lookup per INVOICE_HEADER.status_cd in batch 85559852)", inv == m_inv, {"oracle": inv, "mongo": m_inv})

# (d) tenant lookups by id + by name (UQ) for boundary + random tenants
import random
random.seed(714559852)
ids = random.sample(sorted(exp_tenants), 10)
tl = []
for tid in ids:
    o = q("SELECT ID, NAME, TAX_EXEMPT_YN, STATUS_CD FROM TENANTS WHERE ID = :i", i=tid)[0]
    d = db.tenants.find_one({"_id": tid})
    d2 = db.tenants.find_one({"name": o[1]})
    tl.append({"id": tid, "equal": (o[0], o[1], o[2], int(o[3])) == (d["_id"], d["name"], d["tax_exempt_yn"], d["status_cd"]) and d2["_id"] == tid})
rec("replay tenant lookup by id and by unique name (10 seeded-random tenants)", all(t["equal"] for t in tl), tl)

# ---------------------------------------------------------------- 10. drift triage: source counted twice
c1 = [q(f"SELECT COUNT(*) FROM {t}")[0][0] for t in ("CODES", "TENANTS", "PLANS")]
c2 = [q(f"SELECT COUNT(*) FROM {t}")[0][0] for t in ("CODES", "TENANTS", "PLANS")]
fm = q("SELECT TO_CHAR(INITIALIZED_AT, 'YYYY-MM-DD HH24:MI:SS.FF6') FROM FIXTURE_META")
rec("drift triage: source re-counted twice, FIXTURE_META.INITIALIZED_AT unchanged", c1 == c2 == [32, 69, 3], {"pass1": c1, "pass2": c2, "fixture_meta": fm})

json.dump(results, open(OUT, "w"), indent=2, default=str)
n_ok = sum(r["ok"] for r in results)
print(f"\n{n_ok}/{len(results)} probes ok -> {OUT}")
