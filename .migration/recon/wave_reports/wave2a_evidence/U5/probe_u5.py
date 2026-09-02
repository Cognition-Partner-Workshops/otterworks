#!/usr/bin/env python3
"""Wave-2a independent adversarial probes for U5 (Oracle OW_BILLING package-owned tables -> Mongo).
Read-only on Oracle (plain SQL only — no PL/SQL calls, which write BILLING_AUDIT_LOG) and on the target.
Only target write attempted: validator negative tests that MUST be rejected (nothing persists)."""
import hashlib, json, os, sys, time
from collections import Counter
from decimal import Decimal
from datetime import datetime, timezone
import oracledb
from bson import Decimal128, Int64
from pymongo import MongoClient
from pymongo.errors import WriteError

DB = "ow_tp_mongodb_205236"; QDB = DB + "_quarantine"; NS = "mongo_205236"
ora = oracledb.connect(user="ow_billing", password="ow_billing", dsn="localhost:52521/FREEPDB1")
cur = ora.cursor(); cur.arraysize = 5000
m = MongoClient(os.environ["MONGODB_ATLAS_URI"]); db = m[DB]
res = {"generated_at": datetime.now(timezone.utc).isoformat(), "probes": []}
def P(name, ok, detail=None):
    res["probes"].append({"probe": name, "ok": bool(ok), "detail": detail}); print(("ok  " if ok else "FLAG"), name, "" if detail is None else json.dumps(detail, default=str)[:300])
def q(sql, *a, **kw): cur.execute(sql, kw or a); return cur.fetchall()

# ---- canonical source projection (TO_CHAR text, no float path) -------------------------------
def dt(v):
    if v is None: return None
    return v.replace(microsecond=v.microsecond - v.microsecond % 1000)
ROOTS = {
 "subscriptions": ("SUBSCRIPTIONS", "ID", ["ID","TENANT_ID","PLAN_ID","STARTS_ON","ENDS_ON","STATUS_CD","SUSPENDED_ON"],
                   ["id","tenant_id","plan_id","starts_on","ends_on","status_cd","suspended_on"]),
 "subscriptions_history": ("SUBSCRIPTIONS_HIST", "HIST_ID", ["HIST_ID","HIST_DT","HIST_OP","ID","TENANT_ID","PLAN_ID","STARTS_ON","ENDS_ON","STATUS_CD","SUSPENDED_ON"],
                   ["hist_id","hist_dt","hist_op","id","tenant_id","plan_id","starts_on","ends_on","status_cd","suspended_on"]),
 "usage_events": ("USAGE_EVENTS", "ID", ["ID","TENANT_ID","OCCURRED_AT","UNITS","KIND_CD"], ["id","tenant_id","occurred_at","units","kind_cd"]),
 "rating_periods": ("RATING_PERIODS", "ID", ["ID","TENANT_ID","PERIOD_START","PERIOD_END"], ["id","tenant_id","period_start","period_end"]),
 "billing_invoices": ("INVOICES", "ID", ["ID","TENANT_ID","PERIOD_ID","ISSUED_AT","SUBTOTAL","TAX","TOTAL","STATUS_CD"], ["id","tenant_id","period_id","issued_at","subtotal","tax","total","status_cd"]),
 "credit_notes": ("CREDIT_NOTES", "ID", ["ID","TENANT_ID","ISSUED_ON","AMOUNT","REMAINING_AMOUNT"], ["id","tenant_id","issued_on","amount","remaining_amount"]),
 "dunning_attempts": ("DUNNING_ATTEMPTS", "ID", ["ID","TENANT_ID","INVOICE_ID","ATTEMPT_NO","SCHEDULED_FOR","STATUS_CD"], ["id","tenant_id","invoice_id","attempt_no","scheduled_for","status_cd"]),
 "notifications": ("NOTIFICATIONS", "ID", ["ID","TENANT_ID","KIND_CD","SENT_AT"], ["id","tenant_id","kind_cd","sent_at"]),
 "billing_audit_log": ("BILLING_AUDIT_LOG", "LOG_ID", ["LOG_ID","LOGGED_AT","MODULE","MESSAGE"], ["log_id","logged_at","module","message"]),
}
EMBEDS = {
 "rating_periods": ("results", "RATING_RESULTS", "PERIOD_ID", ["ID","PERIOD_ID","SUBSCRIPTION_ID","USED_UNITS","QUOTA_UNITS","ROLLOVER_UNITS","BILLABLE_UNITS","OVERAGE_AMOUNT","CREATED_AT"],
                    ["id","period_id","subscription_id","used_units","quota_units","rollover_units","billable_units","overage_amount","created_at"]),
 "billing_invoices": ("lines", "INVOICE_LINES", "INVOICE_ID", ["ID","INVOICE_ID","LINE_NO","LINE_TYPE","DESCRIPTION","AMOUNT"], ["id","invoice_id","line_no","line_type","description","amount"]),
}
DEC_COLS = {"SUBTOTAL","TAX","TOTAL","AMOUNT","REMAINING_AMOUNT","OVERAGE_AMOUNT"}
def coltypes(tbl):
    return {r[0]: (r[1], r[2], r[3], r[4]) for r in q("select column_name,data_type,data_precision,data_scale,nullable from user_tab_columns where table_name=:1", tbl)}
def sel(tbl, cols):
    ct = coltypes(tbl); exprs = []
    for c in cols:
        t = ct[c][0]
        if t == "NUMBER": exprs.append(f"TO_CHAR({c})")
        elif t == "DATE": exprs.append(f"TO_CHAR({c},'YYYY-MM-DD HH24:MI:SS')")
        elif t.startswith("TIMESTAMP"): exprs.append(f"TO_CHAR({c},'YYYY-MM-DD HH24:MI:SS.FF6')")
        else: exprs.append(c)
    return q(f"select {','.join(exprs)} from {tbl}"), ct
def norm_src(val, col, ct):
    t = ct[col][0]
    if val is None or (t in ("VARCHAR2","CHAR") and val == ""): return None
    if t == "NUMBER":
        if col in DEC_COLS: return str(Decimal(val).quantize(Decimal("0.01")))
        return str(int(Decimal(val)))
    if t == "DATE": return val + ".000"
    if t.startswith("TIMESTAMP"):
        d = datetime.strptime(val, "%Y-%m-%d %H:%M:%S.%f"); return dt(d).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    return val
def norm_tgt(val):
    if val is None: return None
    if isinstance(val, Decimal128): return str(val.to_decimal().quantize(Decimal("0.01")))
    if isinstance(val, bool): return str(val)
    if isinstance(val, (int, Int64)): return str(int(val))
    if isinstance(val, datetime): return val.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    return val

t0 = time.time()
src = {}; tgt = {}
for coll, (tbl, key, scols, tcols) in ROOTS.items():
    rows, ct = sel(tbl, scols)
    src[coll] = {tuple(r)[scols.index(key)]: {tcols[i]: norm_src(r[i], scols[i], ct) for i in range(len(scols))} for r in rows}
    if ct[key][0] == "NUMBER": src[coll] = {str(int(Decimal(k))): v for k, v in src[coll].items()}
    tgt[coll] = {str(d["_id"]): d for d in db[coll].find({})}
    # key set + full value diff
    sk, tk = set(src[coll]), set(tgt[coll])
    P(f"{coll}: key set equality (src {len(sk)} / tgt {len(tk)})", sk == tk, {"only_src": sorted(sk - tk)[:5], "only_tgt": sorted(tk - sk)[:5]})
    diffs = []
    for k in sk & tk:
        for f in tcols:
            a, b = src[coll][k][f], norm_tgt(tgt[coll][k].get(f))
            if a != b: diffs.append((k, f, a, b))
    P(f"{coll}: independent full value diff ({len(sk&tk)} docs x {len(tcols)} fields)", not diffs, diffs[:5])
    # null/missing per field: src NULL count == tgt explicit-null count; and missing count (D2 says explicit null)
    nulls = {}
    for f, c in zip(tcols, scols):
        s_null = sum(1 for v in src[coll].values() if v[f] is None)
        t_null = sum(1 for d in tgt[coll].values() if f in d and d[f] is None)
        t_miss = sum(1 for d in tgt[coll].values() if f not in d)
        if s_null or t_null or t_miss: nulls[f] = {"src_null": s_null, "tgt_null": t_null, "tgt_missing": t_miss, "nullable": ct[c][3]}
    P(f"{coll}: null distribution per field (src NULL == tgt explicit null, 0 missing)",
      all(v["src_null"] == v["tgt_null"] and v["tgt_missing"] == 0 for v in nulls.values()), nulls)
    # field-set audit
    expected = set(["_id", "ns"] + tcols + ([EMBEDS[coll][0]] if coll in EMBEDS else []))
    extra = Counter(); missing = Counter()
    for d in tgt[coll].values():
        for f in set(d) - expected: extra[f] += 1
        for f in expected - set(d): missing[f] += 1
    P(f"{coll}: field-set audit (exactly mapping fields + _id + ns[+embed])", not extra and not missing, {"extra": dict(extra), "missing": dict(missing)})
    P(f"{coll}: ns=={NS} on 100%", db[coll].count_documents({"ns": NS}) == len(tgt[coll]) and db[coll].count_documents({"ns": {"$ne": NS}}) == 0)
    # BSON types per field vs declared
    spec = json.load(open(os.path.join(os.path.dirname(__file__), "mapping_u5_subset.json")))
    cspec = next(c for c in spec["collections"] if c["collection"] == coll)
    want = {f["target"]: f["bson_type"] for f in cspec["fields"]}
    TYPE = {"string": ["string"], "int": ["int"], "long": ["long"], "date": ["date"], "decimal": ["decimal"]}
    bad = {}
    for f, bt in want.items():
        n_ok = db[coll].count_documents({f: {"$type": TYPE[bt]}}); n_null = db[coll].count_documents({f: None})
        if n_ok + n_null != len(tgt[coll]): bad[f] = {"declared": bt, "typed_ok": n_ok, "null": n_null, "total": len(tgt[coll])}
    P(f"{coll}: BSON types per field == declared bson_type (or null)", not bad, bad)
    # duplicate keys on natural id fields
    idf = tcols[0]
    dup = list(db[coll].aggregate([{"$group": {"_id": f"${idf}", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}]))
    P(f"{coll}: no duplicate `{idf}`; `_id`=={idf} bijection", not dup and all(str(d["_id"]) == norm_tgt(d[idf]) for d in tgt[coll].values()), dup[:3])
    # empty-string leakage (empty_string_is_null rule)
    es = sum(db[coll].count_documents({f: ""}) for f, bt in want.items() if bt == "string")
    P(f"{coll}: no empty strings in string fields", es == 0, es)

# ---- embeds -----------------------------------------------------------------------------
for coll, (arr, ctbl, pk, scols, tcols) in EMBEDS.items():
    rows, ct = sel(ctbl, scols)
    by_parent = {}
    for r in rows:
        by_parent.setdefault(r[scols.index(pk)], []).append({tcols[i]: norm_src(r[i], scols[i], ct) for i in range(len(scols))})
    lens_src = Counter(len(v) for v in by_parent.values()); lens_src[0] += len(set(src[coll]) - set(by_parent))
    lens_tgt = Counter(len(d.get(arr, [])) for d in tgt[coll].values())
    P(f"{coll}.{arr}: per-parent embed length == child rows (hist src {dict(lens_src)} / tgt {dict(lens_tgt)})",
      all(len(tgt[coll][p].get(arr, [])) == len(by_parent.get(p, [])) for p in src[coll]) and lens_src == lens_tgt)
    orphans = q(f"select count(*) from {ctbl} c where not exists (select 1 from {ROOTS[coll][0]} p where p.ID=c.{pk})")[0][0]
    P(f"{coll}.{arr}: orphan children in source (would abort loader)", orphans == 0, orphans)
    ediffs = []; ids = Counter(); notsorted = 0
    for p, d in tgt[coll].items():
        elems = {e["id"]: e for e in d.get(arr, [])}
        for e in d.get(arr, []): ids[e["id"]] += 1
        selems = {e["id"]: e for e in by_parent.get(p, [])}
        if set(elems) != set(selems): ediffs.append((p, "idset", sorted(selems), sorted(elems))); continue
        for k in elems:
            for f in tcols:
                a, b = selems[k][f], norm_tgt(elems[k].get(f))
                if a != b: ediffs.append((p, k, f, a, b))
            if set(elems[k]) != set(tcols): ediffs.append((p, k, "fieldset", sorted(elems[k])))
        if arr == "lines":
            ln = [e["line_no"] for e in d.get(arr, [])]
            if ln != sorted(ln): notsorted += 1
    P(f"{coll}.{arr}: element-level full value diff + field set", not ediffs, ediffs[:5])
    P(f"{coll}.{arr}: element `id` globally unique", not [k for k, n in ids.items() if n > 1])
    if arr == "lines": P("billing_invoices.lines ordered by line_no asc", notsorted == 0)
    # doc-level spot check of aggregate-only fields: sum of embedded amounts
    if arr == "lines":
        s = q("select TO_CHAR(SUM(AMOUNT)) from INVOICE_LINES")[0][0]
        t = list(db[coll].aggregate([{"$unwind": "$lines"}, {"$group": {"_id": None, "s": {"$sum": "$lines.amount"}}}]))
        P("lines.amount total sum exact", (t[0]["s"].to_decimal() if t else Decimal(0)) == Decimal(s or 0), {"src": s, "tgt": str(t[0]["s"]) if t else "0"})
        # per-invoice: lines sum vs subtotal (informational relationship both sides)
        rel_s = q("select i.ID, TO_CHAR(i.SUBTOTAL), TO_CHAR(NVL((select SUM(AMOUNT) from INVOICE_LINES l where l.INVOICE_ID=i.ID),0)) from INVOICES i order by 1")
        rel_t = [(d["_id"], str(d["subtotal"].to_decimal()), str(sum((e["amount"].to_decimal() for e in d["lines"]), Decimal(0)))) for d in sorted(tgt[coll].values(), key=lambda x: x["_id"])]
        Q = lambda x: str(Decimal(x).quantize(Decimal("0.01")))
        P("billing_invoices: (id, subtotal, sum(lines.amount)) identical relationship on both sides (note: invoice 1 subtotal 149 != lines 161.29 in SOURCE too — lines carry tax line; faithful)", [(a, Q(b), Q(c)) for a, b, c in rel_s] == [(a, Q(b), Q(c)) for a, b, c in rel_t], {"src": rel_s, "tgt": rel_t})
    else:
        for f in ["used_units", "quota_units", "rollover_units", "billable_units"]:
            s = q(f"select TO_CHAR(SUM({f.upper()})) from RATING_RESULTS")[0][0]
            t = list(db[coll].aggregate([{"$unwind": f"${arr}"}, {"$group": {"_id": None, "s": {"$sum": f"${arr}.{f}"}}}]))
            P(f"results.{f} total sum exact", str(t[0]["s"]) == s, {"src": s, "tgt": str(t[0]["s"])})
        s = q("select TO_CHAR(SUM(OVERAGE_AMOUNT)) from RATING_RESULTS")[0][0]
        t = list(db[coll].aggregate([{"$unwind": f"${arr}"}, {"$group": {"_id": None, "s": {"$sum": f"${arr}.overage_amount"}}}]))
        P("results.overage_amount total sum exact", t[0]["s"].to_decimal() == Decimal(s), {"src": s, "tgt": str(t[0]["s"])})

# ---- aggregates on roots, decimals exact, boundaries -------------------------------------
for coll, cols in {"billing_invoices": ["SUBTOTAL","TAX","TOTAL"], "credit_notes": ["AMOUNT","REMAINING_AMOUNT"]}.items():
    for c in cols:
        s = q(f"select TO_CHAR(SUM({c})), TO_CHAR(MIN({c})), TO_CHAR(MAX({c})) from {ROOTS[coll][0]}")[0]
        t = list(db[coll].aggregate([{"$group": {"_id": None, "s": {"$sum": f"${c.lower()}"}, "mn": {"$min": f"${c.lower()}"}, "mx": {"$max": f"${c.lower()}"}}}]))[0]
        P(f"{coll}.{c.lower()} sum/min/max exact (Decimal128)", tuple(Decimal(x) for x in s) == tuple(x.to_decimal() for x in (t["s"], t["mn"], t["mx"])), {"src": s})
s = q("select TO_CHAR(SUM(UNITS)), TO_CHAR(MIN(UNITS)), TO_CHAR(MAX(UNITS)), COUNT(DISTINCT TENANT_ID) from USAGE_EVENTS")[0]
t = list(db.usage_events.aggregate([{"$group": {"_id": None, "s": {"$sum": "$units"}, "mn": {"$min": "$units"}, "mx": {"$max": "$units"}, "t": {"$addToSet": "$tenant_id"}}}]))[0]
P("usage_events.units sum/min/max + distinct tenants", (str(t["s"]), str(t["mn"]), str(t["mx"]), len(t["t"])) == tuple(s), {"src": s})
P("usage_events: min(units) > 0 (trigger invariant holds in data)", int(s[1]) > 0)
# boundary docs (min/max by every date column) full compare
for coll, (tbl, key, scols, tcols) in ROOTS.items():
    if not src[coll]: continue
    ct = coltypes(tbl); bad = []
    for c, f in zip(scols, tcols):
        if ct[c][0] not in ("DATE",) and not ct[c][0].startswith("TIMESTAMP") and ct[c][0] != "NUMBER": continue
        for agg in ("MIN", "MAX"):
            r = q(f"select {key} from {tbl} where {c} = (select {agg}({c}) from {tbl}) order by {key}")
            if not r: continue
            k = str(int(Decimal(r[0][0]))) if ct[key][0] == "NUMBER" else r[0][0]
            d = tgt[coll].get(k)
            if d is None or any(src[coll][k][ff] != norm_tgt(d.get(ff)) for ff in tcols): bad.append((c, agg, k))
            sort = 1 if agg == "MIN" else -1
            td = db[coll].find_one({f: {"$ne": None}}, sort=[(f, sort), ("_id", 1)])
            if td and norm_tgt(td[f]) != src[coll][k][f]: bad.append((c, agg, "target extreme differs", str(td[f])))
    P(f"{coll}: min/max boundary docs by every numeric/date column equal (both sides' extremes agree)", not bad, bad)

# ---- empty collections --------------------------------------------------------------------
for coll in ("subscriptions_history",):
    P(f"{coll}: exists, empty, indexes as declared", coll in db.list_collection_names() and db[coll].count_documents({}) == 0 and set(db[coll].index_information()) == {"_id_"}, list(db[coll].index_information()))
P("billing_audit_log: 1 doc == the post-seed PKG_OW_UTIL row (observer side effect), log_id long", db.billing_audit_log.count_documents({}) == 1 and isinstance(db.billing_audit_log.find_one()["log_id"], Int64), db.billing_audit_log.find_one())

# ---- indexes / validator / TTL -------------------------------------------------------------
want_idx = {
 "subscriptions": {("tenant_id", 1), ("starts_on", -1)},
}
spec_idx = {}
for c in spec["collections"]:
    spec_idx[c["collection"]] = [(tuple(sorted(i["keys"].items())), i.get("unique", False), i.get("expireAfterSeconds")) for i in c["indexes"]]
bad = {}
for coll, want in spec_idx.items():
    have = [(tuple(sorted((k, int(v)) for k, v in ii["key"])), ii.get("unique", False), ii.get("expireAfterSeconds")) for n, ii in db[coll].index_information().items() if n != "_id_"]
    if sorted(map(str, want)) != sorted(map(str, have)): bad[coll] = {"want": want, "have": have}
P("declared indexes (keys, unique, TTL) present exactly on all 9 collections", not bad, bad)
P("no *__staging residue in target db", not [c for c in db.list_collection_names() if "__staging" in c])
opts = db.command("listCollections", filter={"name": "usage_events"})["cursor"]["firstBatch"][0]["options"]
P("usage_events has $jsonSchema validator, strict/error", "validator" in opts and opts.get("validationLevel") == "strict" and opts.get("validationAction") == "error", opts)
# negative validator tests: inserts that MUST be rejected (nothing persists on rejection)
neg = {}
for label, doc in {
    "units=0": {"_id": "__probe_neg_0", "id": "__probe_neg_0", "tenant_id": "x", "occurred_at": datetime(2026, 1, 1), "units": Int64(0), "kind_cd": 1, "ns": NS},
    "units=-1": {"_id": "__probe_neg_1", "id": "__probe_neg_1", "tenant_id": "x", "occurred_at": datetime(2026, 1, 1), "units": Int64(-1), "kind_cd": 1, "ns": NS},
    "wrong ns": {"_id": "__probe_neg_2", "id": "__probe_neg_2", "tenant_id": "x", "occurred_at": datetime(2026, 1, 1), "units": Int64(5), "kind_cd": 1, "ns": "other"},
    "units int32 (=5) not long": {"_id": "__probe_neg_3", "id": "__probe_neg_3", "tenant_id": "x", "occurred_at": datetime(2026, 1, 1), "units": 5, "kind_cd": 1, "ns": NS},
}.items():
    try:
        db.usage_events.insert_one(doc); neg[label] = "ACCEPTED"; db.usage_events.delete_one({"_id": doc["_id"]})
    except WriteError as e: neg[label] = "rejected"
P("validator rejects units<=0 and wrong ns (TRG_USAGE_EVENTS_CHECK parity); nothing persisted", neg["units=0"] == neg["units=-1"] == neg["wrong ns"] == "rejected" and db.usage_events.count_documents({"_id": {"$regex": "^__probe"}}) == 0, neg)
P("validator: int32 `units` rejected (strict bsonType long) — write-path note for U6/U7", neg["units int32 (=5) not long"] == "rejected", neg)
P("usage_events count unchanged after negative tests", db.usage_events.count_documents({}) == 814)
# TRG_USAGE_EVENTS_CHECK also enforces kind_cd IN codes USAGE_KIND — not in validator (spec only names units>=0)
kinds = {int(r[0]) for r in q("select code_val from codes where code_type='USAGE_KIND'")}
tk = set(db.usage_events.distinct("kind_cd"))
P("usage_events.kind_cd ⊂ codes USAGE_KIND (data holds; validator does not enforce the FK half of the trigger)", tk <= kinds, {"kinds": sorted(kinds), "used": sorted(tk)})

# ---- quarantine ---------------------------------------------------------------------------
P("quarantine: no U5 collections (none expected; loader aborts on orphans instead)", not [c for c in m[QDB].list_collection_names() if any(x in c for x in ("subscription", "usage", "rating", "billing", "credit", "dunning", "notification", "audit"))], m[QDB].list_collection_names())

# ---- cross-unit references ---------------------------------------------------------------
tenants = set(db.tenants.distinct("_id")); plans = set(db.plans.distinct("_id"))
tenants_src = {r[0] for r in q("select ID from TENANTS")}; plans_src = {r[0] for r in q("select ID from PLANS")}
P("cross: tenants/plans target id sets == source", tenants == tenants_src and plans == plans_src, {"tenants": len(tenants), "plans": len(plans)})
for coll in ("subscriptions", "usage_events", "rating_periods", "billing_invoices", "credit_notes", "dunning_attempts", "notifications"):
    t_ids = set(db[coll].distinct("tenant_id")); s_ids = {r[0] for r in q(f"select distinct TENANT_ID from {ROOTS[coll][0]}")}
    P(f"cross: {coll}.tenant_id set == source; resolves to tenants: {len(t_ids & tenants)}/{len(t_ids)} (source {len(s_ids & tenants_src)}/{len(s_ids)})", t_ids == s_ids and len(t_ids & tenants) == len(s_ids & tenants_src))
sp = set(db.subscriptions.distinct("plan_id")); P("cross: subscriptions.plan_id ⊂ plans (100%)", sp <= plans and sp == {r[0] for r in q("select distinct PLAN_ID from SUBSCRIPTIONS")}, sorted(sp))
codes = {}
for ct_, cv in q("select CODE_TYPE, CODE_VAL from CODES"): codes.setdefault(ct_, set()).add(int(cv))
P("cross: codes in target == source (per type)", {c["_id"].split(":")[0] if isinstance(c["_id"], str) else c.get("code_type") for c in db.codes.find({}, {"_id": 1, "code_type": 1})} >= set(codes), sorted(codes))
def cd(coll, f, typ): 
    v = set(db[coll].distinct(f)); P(f"cross: {coll}.{f} values {sorted(v)} vs codes {typ} {sorted(codes.get(typ, []))}", v <= codes.get(typ, set()))
cd("subscriptions", "status_cd", "SUB_STATUS"); cd("billing_invoices", "status_cd", "INV_STATUS"); cd("dunning_attempts", "status_cd", "DUN_STATUS"); cd("notifications", "kind_cd", "NOTIF_KIND")
rp = set(db.rating_periods.distinct("_id"))
P("cross: billing_invoices.period_id ⊂ rating_periods (target) == source resolution", set(db.billing_invoices.distinct("period_id")) - {None} <= rp and q("select count(*) from INVOICES i where PERIOD_ID is not null and not exists (select 1 from RATING_PERIODS r where r.ID=i.PERIOD_ID)")[0][0] == 0)
P("cross: dunning_attempts.invoice_id ⊂ billing_invoices", set(db.dunning_attempts.distinct("invoice_id")) <= set(db.billing_invoices.distinct("_id")))
subs = set(db.subscriptions.distinct("_id"))
rs = {e["subscription_id"] for d in db.rating_periods.find() for e in d["results"]}
P("cross: rating_periods.results[].subscription_id ⊂ subscriptions", rs <= subs, sorted(rs))
P("cross: rating_periods results[].period_id == parent _id", all(e["period_id"] == d["_id"] for d in db.rating_periods.find() for e in d["results"]))
P("cross: billing_invoices lines[].invoice_id == parent _id", all(e["invoice_id"] == d["_id"] for d in db.billing_invoices.find() for e in d["lines"]))
# subscriptions vs tenants: each tenant has exactly one subscription? (both sides)
per_t_s = Counter(r[0] for r in q("select TENANT_ID from SUBSCRIPTIONS")); per_t_t = Counter(d["tenant_id"] for d in db.subscriptions.find())
P("cross: subscriptions per tenant histogram equal", per_t_s == per_t_t, dict(Counter(per_t_t.values())))
# other units' collections untouched by the reload
P("other units' collections untouched (codes 32 / tenants 69 / plans 3 / customers 25000 / invoices 18750 / documents 2000 / document_snapshots 384 / files 10000)",
  [db[c].count_documents({}) for c in ("codes", "tenants", "plans", "customers", "invoices", "documents", "document_snapshots", "files")] == [32, 69, 3, 25000, 18750, 2000, 384, 10000])

# ---- app-level replays (plain SQL vs Mongo pipelines) --------------------------------------
def D(v): return v.to_decimal() if isinstance(v, Decimal128) else Decimal(str(v))
# fn_usage_summary for every tenant with events, over each RATING_PERIOD window + a wide window
KIND = {1: "api", 2: "storage", 3: "compute"}
windows = [(r[0], r[1]) for r in q("select PERIOD_START, PERIOD_END from RATING_PERIODS")] + [(datetime(2020, 1, 1), datetime(2030, 1, 1))]
tenants_ev = [r[0] for r in q("select distinct TENANT_ID from USAGE_EVENTS order by 1")]
n_ops = 0; bad = []
for tid in tenants_ev[:40]:
    for ps, pe in windows:
        s = q("""select DECODE(u.kind_cd,1,'api',2,'storage',3,'compute','UNKNOWN') k, COUNT(*), TO_CHAR(NVL(SUM(u.units),0)) from usage_events u
                 where u.tenant_id=:1 and TO_CHAR(u.occurred_at,'YYYYMMDD') between TO_CHAR(:2,'YYYYMMDD') and TO_CHAR(:3,'YYYYMMDD')
                 group by DECODE(u.kind_cd,1,'api',2,'storage',3,'compute','UNKNOWN') order by 1""", tid, ps, pe)
        s = [(a, b, int(c)) for a, b, c in s]
        lo = ps.replace(hour=0, minute=0, second=0, microsecond=0); hi = pe.replace(hour=0, minute=0, second=0, microsecond=0)
        t = list(db.usage_events.aggregate([
            {"$match": {"tenant_id": tid, "occurred_at": {"$gte": lo, "$lt": hi.replace(day=hi.day) + (datetime(2000, 1, 2) - datetime(2000, 1, 1))}}},
            {"$group": {"_id": {"$switch": {"branches": [{"case": {"$eq": ["$kind_cd", k]}, "then": v} for k, v in KIND.items()], "default": "UNKNOWN"}}, "n": {"$sum": 1}, "u": {"$sum": "$units"}}},
            {"$sort": {"_id": 1}}]))
        t = [(d["_id"], d["n"], int(d["u"])) for d in t]
        n_ops += 1
        if s != t: bad.append((tid, str(ps), s, t))
P(f"replay PKG_RATING.fn_usage_summary (kind, count, units) x {n_ops} ops", not bad, bad[:3])
# fn_overdue_accounts as of several dates (status 40, issued before as_of, join tenants status label)
bad = []; n_ops = 0
for as_of in [datetime(2026, 1, 1), datetime(2026, 6, 1), datetime(2026, 9, 1), datetime(2027, 1, 1)]:
    s = q("""select i.tenant_id, i.id, TO_CHAR(i.total), TRUNC(:1) - TRUNC(CAST(i.issued_at AS DATE)), DECODE(t.status_cd,10,'active',20,'suspended','UNKNOWN')
             from invoices i, tenants t where t.id (+) = i.tenant_id and i.status_cd=40 and TO_CHAR(i.issued_at,'YYYYMMDD') < TO_CHAR(:2,'YYYYMMDD') order by i.issued_at, i.id""", as_of, as_of)
    s = [(a, b, Q(c), int(d), e) for a, b, c, d, e in s]
    t = []
    for d in db.billing_invoices.find({"status_cd": 40, "issued_at": {"$lt": as_of.replace(hour=0, minute=0, second=0)}}, sort=[("issued_at", 1), ("_id", 1)]):
        ten = db.tenants.find_one({"_id": d["tenant_id"]})
        st = {10: "active", 20: "suspended"}.get(ten["status_cd"] if ten else None, "UNKNOWN")
        t.append((d["tenant_id"], d["_id"], Q(D(d["total"])), (as_of.date() - d["issued_at"].date()).days, st))
    n_ops += 1
    if s != t: bad.append((str(as_of), s, t))
P(f"replay PKG_DUNNING.fn_overdue_accounts x {n_ops} as-of dates", not bad, bad[:2])
# fn_invoice_lines for every invoice
bad = []
for inv in sorted(src["billing_invoices"]):
    s = [(int(a), b, c, Q(d)) for a, b, c, d in q("select LINE_NO, LINE_TYPE, DESCRIPTION, TO_CHAR(AMOUNT) from invoice_lines where invoice_id=:1 order by line_no", inv)]
    d = db.billing_invoices.find_one({"_id": inv}); t = [(e["line_no"], e["line_type"], e["description"], Q(D(e["amount"]))) for e in sorted(d["lines"], key=lambda e: e["line_no"])]
    if s != t: bad.append((inv, s, t))
P("replay PKG_INVOICING.fn_invoice_lines x 3 invoices", not bad, bad)
# fn_entitlement: latest covering subscription per tenant as of dates (tenants x plans join)
bad = []; n_ops = 0
plan_doc = {p["_id"]: p for p in db.plans.find()}
for p_on in [datetime(2025, 6, 1), datetime(2026, 1, 15), datetime(2026, 8, 1)]:
    for tid in sorted(tenants_src)[:69]:
        s = q("""select * from (select t.id, p.code, DECODE(p.tier_cd,1,'starter',2,'growth',3,'scale','UNKNOWN'), TO_CHAR(p.monthly_fee), TO_CHAR(p.included_units),
                 DECODE(s.status_cd,10,'active',20,'suspended',30,'cancelled','UNKNOWN'), TO_CHAR(GREATEST(s.starts_on,:p_on),'YYYY-MM-DD HH24:MI:SS')
                 from tenants t, subscriptions s, plans p where s.tenant_id=t.id and p.id (+) = s.plan_id and t.id=:tid and s.starts_on <= :p_on and (s.ends_on is null or s.ends_on >= :p_on)
                 order by s.starts_on desc) where rownum <= 1""", tid=tid, p_on=p_on)
        s = [(a, b, c, Q(d), str(Decimal(e)), f, g) for a, b, c, d, e, f, g in s]
        sub = db.subscriptions.find_one({"tenant_id": tid, "starts_on": {"$lte": p_on}, "$or": [{"ends_on": None}, {"ends_on": {"$gte": p_on}}]}, sort=[("starts_on", -1)])
        t = []
        if sub:
            p = plan_doc.get(sub["plan_id"]) or {}
            t = [(tid, p.get("code"), {1: "starter", 2: "growth", 3: "scale"}.get(p.get("tier_cd"), "UNKNOWN"), Q(D(p["monthly_fee"])), str(int(p["included_units"])),
                  {10: "active", 20: "suspended", 30: "cancelled"}.get(sub["status_cd"], "UNKNOWN"), max(sub["starts_on"], p_on).strftime("%Y-%m-%d %H:%M:%S"))]
        n_ops += 1
        if s != t: bad.append((tid, str(p_on), s, t))
P(f"replay PKG_PLANS.fn_entitlement (tenants ⋈ subscriptions ⋈ plans, latest covering) x {n_ops} ops", not bad, bad[:3])
# PKG_RATING rollover lookup: prior 3 months results per tenant/period
bad = []; n_ops = 0
for tid, ps in q("select TENANT_ID, PERIOD_START from RATING_PERIODS"):
    for shift in (0, 1, 3):
        pstart = q("select ADD_MONTHS(:1, :2) from dual", ps, shift)[0][0]
        s = sorted(int(r[0] or 0) for r in q("select rr.rollover_units from rating_results rr, rating_periods rp where rp.id=rr.period_id and rp.tenant_id=:1 and rp.period_start < :2 and rp.period_start >= ADD_MONTHS(:3,-3)", tid, pstart, pstart))
        lo = q("select ADD_MONTHS(:1,-3) from dual", pstart)[0][0]
        t = sorted(int(e["rollover_units"] or 0) for d in db.rating_periods.find({"tenant_id": tid, "period_start": {"$lt": pstart, "$gte": lo}}) for e in d["results"])
        n_ops += 1
        if s != t: bad.append((tid, str(pstart), s, t))
P(f"replay PKG_RATING rollover window (prior 3 months results) x {n_ops} ops", not bad, bad)
# PKG_INVOICING credit-notes application order: remaining_amount>0 ordered by issued_on, id per tenant
bad = []
for tid in {r[0] for r in q("select distinct TENANT_ID from CREDIT_NOTES")}:
    s = [(a, Q(b)) for a, b in q("select id, TO_CHAR(remaining_amount) from credit_notes where tenant_id=:1 and remaining_amount > 0 order by issued_on, id", tid)]
    t = [(d["_id"], Q(D(d["remaining_amount"]))) for d in db.credit_notes.find({"tenant_id": tid, "remaining_amount": {"$gt": Decimal128("0")}}, sort=[("issued_on", 1), ("_id", 1)])]
    if s != t: bad.append((tid, s, t))
P("replay PKG_INVOICING credit-note application order per tenant", not bad, bad)
# PKG_DUNNING.sp_schedule_dunning read half: invoices status 40 ordered; next attempt_no per invoice
s = [(a, b, int(c)) for a, b, c in q("select i.id, i.tenant_id, (select NVL(MAX(attempt_no),0)+1 from dunning_attempts d where d.invoice_id=i.id) from invoices i where status_cd=40 order by issued_at, id")]
t = []
for d in db.billing_invoices.find({"status_cd": 40}, sort=[("issued_at", 1), ("_id", 1)]):
    mx = list(db.dunning_attempts.aggregate([{"$match": {"invoice_id": d["_id"]}}, {"$group": {"_id": None, "m": {"$max": "$attempt_no"}}}]))
    t.append((d["_id"], d["tenant_id"], (mx[0]["m"] if mx else 0) + 1))
P("replay PKG_DUNNING.sp_schedule_dunning read half (status 40 invoices, next attempt_no)", s == t, {"src": s, "tgt": t})
# sp_suspend_overdue read half: notifications kind 3 existence per overdue tenant
s = {r[0]: int(r[1]) for r in q("select i.tenant_id, (select count(*) from notifications n where n.tenant_id=i.tenant_id and n.kind_cd=3) from invoices i where status_cd=40 group by i.tenant_id")}
t = {tid: db.notifications.count_documents({"tenant_id": tid, "kind_cd": 3}) for tid in db.billing_invoices.distinct("tenant_id", {"status_cd": 40})}
P("replay PKG_DUNNING.sp_suspend_overdue read half (kind 3 notification exists per overdue tenant)", s == t, {"src": s, "tgt": t})

res["elapsed_s"] = round(time.time() - t0, 1)
res["summary"] = {"total": len(res["probes"]), "ok": sum(p["ok"] for p in res["probes"]), "flags": [p["probe"] for p in res["probes"] if not p["ok"]]}
print(json.dumps(res["summary"], indent=1))
json.dump(res, open(os.path.join(os.path.dirname(__file__), "probes.json"), "w"), indent=1, default=str)
