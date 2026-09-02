"""Wave 2b cross-unit consistency: shared references (codes/tenants/plans/subscriptions),
DECODE maps vs CODES, counter contracts of the two log_msg ports, golden + quarantine state."""
import json, os, sys, time
from pymongo import MongoClient
import oracledb

DB = "ow_tp_mongodb_205236"; QDB = DB + "_quarantine"
m = MongoClient(os.environ["MONGODB_ATLAS_URI"]); db = m[DB]
ora = oracledb.connect(user="ow_billing", password="ow_billing", dsn="localhost:52521/FREEPDB1"); cur = ora.cursor()
res = []
def probe(name, ok, detail=""):
    res.append({"probe": name, "ok": bool(ok), "detail": str(detail)[:600]}); print(("ok  " if ok else "FAIL"), name, "|", str(detail)[:200])
def ids(c, f="_id"): return {d[f] for d in db[c].find({}, {f: 1})}
def vals(c, f): return {d[f] for d in db[c].find({}, {f: 1}) if d.get(f) is not None}

# shared references inside the golden set, and in each unit's clone
for pre in ("", "replay_u6_", "replay_u7_"):
    probe(f"{pre or 'golden'}: subscriptions.plan_id ⊂ plans, subscriptions/usage_events/rating_periods.tenant_id ⊂ tenants, results.subscription_id ⊂ subscriptions",
          vals(pre + "subscriptions", "plan_id") <= ids(pre + "plans") and vals(pre + "subscriptions", "tenant_id") <= ids(pre + "tenants")
          and vals(pre + "usage_events", "tenant_id") <= ids(pre + "tenants") and vals(pre + "rating_periods", "tenant_id") <= ids(pre + "tenants")
          and {r["subscription_id"] for d in db[pre + "rating_periods"].find() for r in d["results"]} <= ids(pre + "subscriptions"),
          {c: db[pre + c].count_documents({}) for c in ("plans", "tenants", "subscriptions", "usage_events", "rating_periods")})
# the two clones start from the same golden docs
same = all(sorted(json.dumps(d, default=str, sort_keys=True) for d in db["replay_u6_" + c].find({}, {"_id": 0})) ==
           sorted(json.dumps(d, default=str, sort_keys=True) for d in db["replay_u7_" + c].find({}, {"_id": 0}))
           for c in ("plans", "tenants", "subscriptions", "usage_events", "rating_periods"))
probe("replay_u6_* and replay_u7_* shared collections are value-identical at baseline (plans/tenants/subscriptions/usage_events/rating_periods)", same)
# DECODE maps used by the two ports vs CODES (source + golden codes)
cur.execute("select code_type, code_val, code_desc from codes where code_type in ('PLAN_TIER','SUB_STATUS','USAGE_KIND') order by 1,2")
codes = {(t, int(v)): d for t, v, d in cur.fetchall()}
gcodes = {(d["code_type"], d["code_val"]): d["code_desc"] for d in db.codes.find({"code_type": {"$in": ["PLAN_TIER", "SUB_STATUS", "USAGE_KIND"]}})}
probe("golden codes == CODES for PLAN_TIER/SUB_STATUS/USAGE_KIND", codes == gcodes, codes)
sys.path.insert(0, os.path.expanduser("~/wave_recon/heads/u7/services/legacy-billing/app"))
from ow_billing import rating
probe("U7 KIND_DECODE {1:api,2:storage,3:compute} == CODES USAGE_KIND descriptions", {k: v for (t, k), v in codes.items() if t == "USAGE_KIND"} == rating.KIND_DECODE, rating.KIND_DECODE)
probe("U6 plans tier DECODE (1 starter,2 growth,3 scale) == CODES PLAN_TIER descriptions", {k: v for (t, k), v in codes.items() if t == "PLAN_TIER"} == {1: "starter", 2: "growth", 3: "scale"},
      {k: v for (t, k), v in codes.items() if t == "PLAN_TIER"})
cur.execute("select distinct status_cd from subscriptions union select distinct kind_cd from usage_events union select distinct tier_cd from plans")
probe("all status/kind/tier values in data have CODES rows (no UNKNOWN(...) branch live)", {int(r[0]) for r in cur.fetchall()} <= {v for (_, v) in codes}, sorted({v for (_, v) in codes}))
# counter contracts of the two PKG_OW_UTIL.log_msg ports
u6 = list(db.replay_u6_counters.find()); u7 = list(db.replay_u7_counters.find()); g = list(db.counters.find())
probe("FINDING: U6 and U7 port pkg_ow_util.log_msg with incompatible counter contracts on the shared `counters` shape "
      "(golden: {_id:lower seq, seq, source_sequence, ns}; U6: {_id:'seq_billing_audit_log', seq}; U7: {_id:'SEQ_BILLING_AUDIT_LOG', value, ns})",
      False, {"golden": g, "u6": u6, "u7": u7})
probe("shared golden `counters` has no SEQ_BILLING_AUDIT_LOG entry at all (neither port's key) -- U6 would raise LookupError, U7 self-seeds from max(log_id)",
      not [d for d in g if "audit" in d["_id"].lower()], [d["_id"] for d in g])
# golden state vs wave pre-fingerprint (byte-level via fingerprint.py output)
pre = json.load(open(os.path.expanduser("~/wave_recon/w2b/golden_pre_fingerprint.json")))
import hashlib
from bson.json_util import dumps, CANONICAL_JSON_OPTIONS
def fp(spec):
    d_, c = spec.split("."); h = hashlib.sha256(); n = 0
    for d in m[d_][c].find({}, sort=[("_id", 1)]):
        h.update(dumps(d, json_options=CANONICAL_JSON_OPTIONS, sort_keys=True).encode()); h.update(b"\n"); n += 1
    return n, h.hexdigest()
bad = [k for k, v in pre.items() if (v["n"], v["sha256"]) != fp(k)]
probe(f"golden + quarantine collections byte-identical to the wave pre-fingerprint ({len(pre)} collections)", not bad, bad)
qs = {c: m[QDB][c].count_documents({}) for c in m[QDB].list_collection_names()}
probe("quarantine SETS: {bad_csv_list:31, dirty_signup_dt:50, invoice_feed_orphan_lines:37, orphan_document_snapshots:6}; U6/U7 declare none",
      qs == {"bad_csv_list": 31, "dirty_signup_dt": 50, "invoice_feed_orphan_lines": 37, "orphan_document_snapshots": 6}, qs)
cur.execute("select count(*) from billing_audit_log"); a = cur.fetchone()[0]
cur.execute("select sequence_name, last_number from user_sequences"); s = dict(cur.fetchall())
cur.execute("select to_char(initialized_at,'YYYY-MM-DD HH24:MI:SS.FF6') from fixture_meta"); ia = cur.fetchone()[0]
probe("Oracle source identity unchanged across the wave: FIXTURE_META, BILLING_AUDIT_LOG=1, SEQ_BILLING_AUDIT_LOG.last_number=2",
      ia == "2026-09-01 20:53:10.961888" and a == 1 and s["SEQ_BILLING_AUDIT_LOG"] == 2, (ia, a, s["SEQ_BILLING_AUDIT_LOG"]))
json.dump(res, open(os.path.expanduser("~/wave_recon/w2b/cross_unit.json"), "w"), indent=1)
print(f"{sum(r['ok'] for r in res)}/{len(res)} ok")
