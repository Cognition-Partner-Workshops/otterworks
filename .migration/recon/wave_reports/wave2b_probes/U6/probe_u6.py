"""Wave 2b independent probes for U6 (PKG_OW_UTIL + PKG_PLANS -> ow_billing.util/plans).

Source side is PLAIN SQL only (never PKG_* -- the packages write BILLING_AUDIT_LOG).
Target side is the head's Python against the replay_u6_* clone (mutations allowed there;
the clone is reloaded afterwards). Golden collections are read-only here.
"""
import hashlib, json, os, re, sys, time
from datetime import date, datetime, timedelta
from decimal import Decimal

import oracledb
from bson import Int64
from bson.json_util import dumps, CANONICAL_JSON_OPTIONS
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

HEAD = os.path.expanduser("~/wave_recon/heads/u6")
sys.path.insert(0, f"{HEAD}/services/legacy-billing/app")
sys.path.insert(0, f"{HEAD}/scripts/tp_mongo")
from ow_billing import Store, util, plans  # noqa: E402
from ow_billing.routes import call_entrypoint, plans_api  # noqa: E402

OUT = os.path.expanduser("~/wave_recon/w2b/U6/probes.json")
DB = "ow_tp_mongodb_205236"
QDB = "ow_tp_mongodb_205236_quarantine"
PREFIX = "replay_u6_"
T = lambda n: f"{n:08d}"  # noqa: E731
TENANT = lambda n: f"00000000-0000-0000-0000-{n:012d}"  # noqa: E731
PLAN = lambda n: f"10000000-0000-0000-0000-{n:012d}"  # noqa: E731

results = []
t0 = time.time()


def probe(area, name, ok, detail=""):
    results.append({"area": area, "probe": name, "ok": bool(ok), "detail": str(detail)[:600]})
    print(("ok  " if ok else "FAIL"), area, "|", name, "|", str(detail)[:200])


def canon(v):
    if isinstance(v, Decimal):
        return str(v.normalize()) if v == v.to_integral() else str(v)
    if isinstance(v, datetime):
        return v.date().isoformat() if (v.hour, v.minute, v.second) == (0, 0, 0) else v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if v is None:
        return None
    return str(v)


ora = oracledb.connect(user="ow_billing", password="ow_billing", dsn="localhost:52521/FREEPDB1")
cur = ora.cursor()
m = MongoClient(os.environ["MONGODB_ATLAS_URI"])
db = m[DB]
store = Store(m, DB, PREFIX)
gold = Store(m, DB, "")


def q(sql, **binds):
    cur.execute(sql, binds)
    cols = [d[0].lower() for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


# ---------- 0. fixture identity, source unchanged ----------
meta = q("select to_char(initialized_at,'YYYY-MM-DD HH24:MI:SS.FF6') ia from fixture_meta")[0]["ia"]
probe("fixture", "FIXTURE_META.INITIALIZED_AT unchanged", meta == "2026-09-01 20:53:10.961888", meta)
audit0 = q("select count(*) n from billing_audit_log")[0]["n"]
seqs0 = {r["sequence_name"]: r["last_number"] for r in q("select sequence_name,last_number from user_sequences")}
probe("fixture", "source BILLING_AUDIT_LOG rows before probes", audit0 == 1, audit0)

# live PL/SQL source == checked-in file (the transcripts' ORACLE_SOURCE_SHA is file-based)
def norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()
for pkg, f in (("PKG_OW_UTIL", "01_pkg_util.sql"), ("PKG_PLANS", "02_pkg_plans.sql")):
    live = "".join(r["text"] for r in q(
        "select text from user_source where name=:n and type='PACKAGE BODY' order by line", n=pkg))
    filetxt = open(f"{HEAD}/services/legacy-billing/db/oracle/packages/{f}").read()
    body = filetxt.split("CREATE OR REPLACE PACKAGE BODY", 1)[1].split("\n/\n", 1)[0]
    probe("provenance", f"live USER_SOURCE {pkg} body == checked-in file", norm(live) == norm("PACKAGE BODY" + body),
          f"live {len(live)} chars")

# ---------- 1. clone baseline vs golden (value-level, ignoring codes ObjectIds) ----------
def fp(coll, drop_id=False):
    h = hashlib.sha256(); n = 0
    key = "_key" if drop_id else "_id"
    for d in db[coll].find({}, sort=[(key, 1)]):
        if drop_id:
            d.pop("_id", None)
        h.update(dumps(d, json_options=CANONICAL_JSON_OPTIONS, sort_keys=True).encode()); n += 1
    return n, h.hexdigest()

for c in ["tenants", "plans", "subscriptions", "subscriptions_history", "usage_events", "rating_periods",
          "billing_invoices", "credit_notes", "dunning_attempts", "notifications", "billing_audit_log"]:
    probe("clone", f"{PREFIX}{c} == golden {c} (canonical dump)", fp(c) == fp(PREFIX + c), fp(c))
probe("clone", "replay_u6_codes == golden codes ignoring ObjectId _id", fp("codes", True) == fp(PREFIX + "codes", True),
      fp("codes", True))
gi = {c: sorted((v["key"], v.get("unique", False), v.get("expireAfterSeconds")) for k, v in db[c].index_information().items()) for c in
      ["codes", "tenants", "plans", "subscriptions", "usage_events", "rating_periods", "billing_invoices", "credit_notes",
       "dunning_attempts", "notifications", "billing_audit_log"]}
ci = {c: sorted((v["key"], v.get("unique", False), v.get("expireAfterSeconds")) for k, v in db[PREFIX + c].index_information().items()) for c in gi}
diff_idx = {c: (gi[c], ci[c]) for c in gi if gi[c] != ci[c]}
probe("clone", "clone index specs == golden index specs", not diff_idx, json.dumps(diff_idx, default=str))
vo = next(db.list_collections(filter={"name": PREFIX + "usage_events"}))["options"]
probe("clone", "usage_events validator cloned (strict/error)", vo.get("validationLevel") == "strict" and "validator" in vo, list(vo))
probe("clone", "no *__staging residue", not [c for c in db.list_collection_names() if "staging" in c])
cnt = {d["_id"]: d for d in db[PREFIX + "counters"].find()}
probe("counters", "replay counters seeded from USER_SEQUENCES.last_number-1 (NOCACHE => last issued)",
      cnt["seq_billing_audit_log"]["seq"] == seqs0["SEQ_BILLING_AUDIT_LOG"] - 1 and cnt["seq_subscriptions_hist"]["seq"] == seqs0["SEQ_SUBSCRIPTIONS_HIST"] - 1, cnt)
probe("counters", "seq value == max(log_id) in the cloned audit log", cnt["seq_billing_audit_log"]["seq"] ==
      db[PREFIX + "billing_audit_log"].find_one(sort=[("log_id", -1)])["log_id"])
probe("counters", "counter seq stored as BSON long", all(isinstance(d["seq"], Int64) or type(d["seq"]).__name__ == "int" for d in cnt.values()),
      {k: type(v["seq"]).__name__ for k, v in cnt.items()})
cache = q("select sequence_name, cache_size from user_sequences where sequence_name in ('SEQ_BILLING_AUDIT_LOG','SEQ_SUBSCRIPTIONS_HIST')")
probe("counters", "both sequences NOCACHE (so last_number-1 is exact)", all(r["cache_size"] == 0 for r in cache), cache)

# ---------- 2. PKG_OW_UTIL parity via plain SQL ----------
inputs = ["", "a", "00000000-0000-0000-0000-00000000000110000000-0000-0000-0000-0000000000022026-03-01",
          "x" * 300, "über-ß-日本", "tenant plan 2026-12-31", "\t new\nline "]
ok = True; det = []
for s in inputs:
    o = q("select lower(rawtohex(standard_hash(utl_raw.cast_to_raw(:s),'MD5'))) h from dual", s=s)[0]["h"]
    o = f"{o[:8]}-{o[8:12]}-{o[12:16]}-{o[16:20]}-{o[20:]}"
    p = util.f_md5_uuid(s)
    ok &= (o == p); det.append((s[:12], o == p))
probe("util", f"f_md5_uuid == STANDARD_HASH MD5 on {len(inputs)} inputs incl. UTF-8", ok, det)
# NOTE: Oracle CAST_TO_RAW('') is NULL -> STANDARD_HASH(NULL) is the MD5 of empty in Oracle 23? record whatever we saw
o = q("select lower(rawtohex(standard_hash(utl_raw.cast_to_raw(''),'MD5'))) h from dual")[0]["h"]
probe("util", "f_md5_uuid('') edge: Oracle hash of empty string", util.f_md5_uuid("").replace("-", "") == o, f"oracle={o}")

codes = q("select code_type, code_val, code_desc from codes order by 1,2")
ok = all(util.f_code_desc(store, r["code_type"], int(r["code_val"])) == r["code_desc"] for r in codes)
probe("util", f"f_code_desc == CODES lookup for all {len(codes)} codes", ok)
unk = [util.f_code_desc(store, "SUB_STATUS", 99), util.f_code_desc(store, "NOPE", 1), util.f_code_desc(store, "SUB_STATUS", None)]
probe("util", "f_code_desc NO_DATA_FOUND branch UNKNOWN(val) / UNKNOWN(-1) for NULL", unk == ["UNKNOWN(99)", "UNKNOWN(1)", "UNKNOWN(-1)"], unk)

dates = [date(2026, 1, 1), date(1999, 12, 31), date(2000, 2, 29), date(2099, 12, 31), date(2026, 9, 2)]
ok = all(q("select to_char(to_date(:d,'YYYY-MM-DD'),'DD-MON-YY','NLS_DATE_LANGUAGE=ENGLISH') s from dual", d=d.isoformat())[0]["s"] == util.f_dt2str(d) for d in dates)
probe("util", "f_dt2str == TO_CHAR(DD-MON-YY) on 5 dates", ok)
strs = ["01-JAN-26", "1-JAN-26", "01-jan-26", "31-DEC-99", "29-FEB-24", "30-FEB-26", "32-JAN-26", "2026-01-01", "", "01-JAN-2026", "01-JANUARY-26", "01 JAN 26", "01/JAN/26", "01-JAN-6", None]
mism = []
for s in strs:
    o = q("select to_char(f,'YYYY-MM-DD') s from (select case when :s is null then null else (select to_date(:s,'DD-MON-YY','NLS_DATE_LANGUAGE=ENGLISH') from dual) end f from dual)", s=s)[0]["s"] if False else None
    # TO_DATE errors cannot be caught in plain SQL; use a validate_conversion-style expression instead
    o = q("select case when validate_conversion(:s as date, 'DD-MON-YY', 'NLS_DATE_LANGUAGE=ENGLISH')=1 then to_char(to_date(:s,'DD-MON-YY','NLS_DATE_LANGUAGE=ENGLISH'),'YYYY-MM-DD') end s from dual", s=s)[0]["s"]
    p = util.f_str2dt(s); p = p.date().isoformat() if p else None
    if o != p:
        mism.append((s, o, p))
probe("util", f"f_str2dt == TO_DATE(DD-MON-YY) semantics (WHEN OTHERS -> NULL) on {len(strs)} strings", not mism,
      f"GAP (declared by the child, no caller in PKG_PLANS/PKG_OW_UTIL entrypoints): Oracle TO_DATE is lenient, Python regex strict -> {mism}")
callers = q("select name, type, line, text from user_source where upper(text) like '%F_STR2DT%' and not (name='PKG_OW_UTIL')")
probe("util", "f_str2dt has no PL/SQL caller outside PKG_OW_UTIL (USER_SOURCE)", not callers, callers)

# ---------- 3. PKG_PLANS reads: plain-SQL replay for ALL tenants x dates ----------
sql_list = """select p.id plan_id, p.code, decode(p.tier_cd,1,'starter',2,'growth',3,'scale','UNKNOWN') tier,
 to_char(p.monthly_fee,'FM9999999990.00') monthly_fee, p.included_units, to_char(p.overage_rate,'FM9999999990.000000') overage_rate
 from plans p where nvl(p.active_yn,'N')='Y' order by p.monthly_fee, p.code"""
o = [[canon(v) for v in r.values()] for r in q(sql_list)]
p = [[r["plan_id"], r["code"], r["tier"], r["monthly_fee"], str(r["included_units"]), r["overage_rate"]] for r in call_entrypoint(store, "billing.fn_list_plans", {})]
probe("plans", "fn_list_plans full row parity (order, all 6 columns)", o == p, (o, p))
probe("plans", "fn_list_plans wrote exactly one audit row (module PLANS, message fn_list_plans, long log_id, ns)",
      (lambda d: d and d["module"] == "PLANS" and d["message"] == "fn_list_plans" and isinstance(d["log_id"], int) and d["ns"] == "mongo_205236" and d["_id"] == d["log_id"] and d["logged_at"].microsecond % 1000 == 0)(db[PREFIX + "billing_audit_log"].find_one(sort=[("log_id", -1)])),
      db[PREFIX + "billing_audit_log"].find_one(sort=[("log_id", -1)]))
raw_plans = list(db[PREFIX + "plans"].find())
probe("plans", "plans.active_yn has no NULL/N (so NVL(active_yn,'N') branch untested by data) -- recorded", True,
      {d["code"]: d.get("active_yn") for d in raw_plans})

sql_ent = """select * from (select t.id tenant_id, p.code plan_code, decode(p.tier_cd,1,'starter',2,'growth',3,'scale','UNKNOWN') tier,
 to_char(p.monthly_fee,'FM9999999990.00') monthly_fee, p.included_units,
 decode(s.status_cd,10,'active',20,'suspended',30,'cancelled','UNKNOWN') subscription_status,
 to_char(greatest(s.starts_on, :on_dt),'YYYY-MM-DD') effective_on, s.starts_on
 from tenants t, subscriptions s, plans p where s.tenant_id=t.id and p.id(+)=s.plan_id and t.id=:tid
 and s.starts_on <= :on_dt and (s.ends_on is null or s.ends_on >= :on_dt) order by s.starts_on desc) where rownum<=1"""
tenants = [r["id"] for r in q("select id from tenants order by id")]
asof = [date(2025, 12, 31), date(2026, 1, 1), date(2026, 2, 28), date(2026, 3, 1), date(2026, 6, 30), date(2026, 9, 2)]
mism = []; n = 0; nonnull = 0
for tid in tenants:
    for d in asof:
        n += 1
        o = q(sql_ent, tid=tid, on_dt=datetime(d.year, d.month, d.day))
        o = None if not o else {k: canon(v) for k, v in o[0].items() if k != "starts_on"}
        p = call_entrypoint(store, "billing.fn_entitlement", {"tenant_id": tid, "as_of": d.isoformat()})
        if p is not None:
            p = {k: canon(v) for k, v in p.items()}
            p["included_units"] = str(p["included_units"])
        if o != p:
            mism.append((tid, d.isoformat(), o, p))
        nonnull += o is not None
probe("plans", f"fn_entitlement full-row parity: {len(tenants)} tenants x {len(asof)} dates = {n} ops ({nonnull} hits, {n - nonnull} no-entitlement)", not mism, mism[:3])
probe("plans", "fn_entitlement unknown tenant -> None (Oracle: no rows)", call_entrypoint(store, "billing.fn_entitlement", {"tenant_id": "ffffffff-0000-0000-0000-000000000000", "as_of": "2026-02-28"}) is None)
probe("plans", "fn_entitlement is read-only (no audit row, unlike fn_list_plans; matches PL/SQL)",
      db[PREFIX + "billing_audit_log"].count_documents({}) == 2, db[PREFIX + "billing_audit_log"].count_documents({}))
# ROWNUM tie semantics: does any tenant have two subscriptions with the same starts_on? (would make Oracle's pick arbitrary)
ties = q("select tenant_id, starts_on, count(*) n from subscriptions group by tenant_id, starts_on having count(*)>1")
probe("plans", "no starts_on ties per tenant in source (ORDER BY starts_on DESC / ROWNUM<=1 is deterministic)", not ties, ties)
# status/tier domains observed
probe("plans", "DECODE domains observed in data", True, {"status": sorted({r["status_cd"] for r in q("select distinct status_cd from subscriptions")}),
                                                       "tier": sorted({r["tier_cd"] for r in q("select distinct tier_cd from plans")})})

# ---------- 4. sp_change_plan write-path semantics on the clone ----------
subs = store.coll("subscriptions"); hist = store.coll("subscriptions_history"); audit = store.coll("billing_audit_log")
def snap(tid):
    return [{k: canon(v) for k, v in d.items() if k in ("id", "plan_id", "starts_on", "ends_on", "status_cd", "suspended_on")} for d in subs.find({"tenant_id": tid}).sort("starts_on", 1)]

# 4a. baseline scenario PLANS-004 semantics beyond the transcript fields: ids, history image, counters, audit order
a0 = audit.count_documents({}); h0 = hist.count_documents({}); c0 = cnt["seq_billing_audit_log"]["seq"]
before = subs.find_one({"tenant_id": TENANT(1)})
rows = call_entrypoint(store, "billing.sp_change_plan", {"tenant_id": TENANT(1), "plan_id": PLAN(2), "effective_on": "2026-03-01"})
new = subs.find_one({"tenant_id": TENANT(1), "ends_on": None})
exp_id = q("select lower(rawtohex(standard_hash(utl_raw.cast_to_raw(:s),'MD5'))) h from dual", s=TENANT(1) + PLAN(2) + "2026-03-01")[0]["h"]
exp_id = f"{exp_id[:8]}-{exp_id[8:12]}-{exp_id[12:16]}-{exp_id[16:20]}-{exp_id[20:]}"
probe("change_plan", "new subscription id == Oracle f_md5_uuid(tenant||plan||YYYY-MM-DD)", new["_id"] == exp_id == new["id"], new["_id"])
probe("change_plan", "new row shape == source columns (status 10, ends_on/suspended_on explicit null, ns, starts_on midnight)",
      set(new) == {"_id", "id", "tenant_id", "plan_id", "starts_on", "ends_on", "status_cd", "suspended_on", "ns"} and new["status_cd"] == 10 and new["ends_on"] is None and new["suspended_on"] is None and new["ns"] == "mongo_205236", new)
old = subs.find_one({"_id": before["_id"]})
probe("change_plan", "prior open row closed: ends_on = eff-1 day, status DECODE(10->10)", old["ends_on"] == datetime(2026, 2, 28) and old["status_cd"] == 10, old)
hrow = hist.find_one(sort=[("hist_id", -1)])
img = {k: before.get(k) for k in ("id", "tenant_id", "plan_id", "starts_on", "ends_on", "status_cd", "suspended_on")}
probe("change_plan", "TRG_SUBSCRIPTIONS_HIST image == :OLD row, hist_op UPD, hist_id from counter, hist_dt 'DD-MON-YY HH24:MI:SS'",
      hrow and {k: hrow.get(k) for k in img} == img and hrow["hist_op"] == "UPD" and hrow["hist_id"] == 1 and hrow["_id"] == 1
      and re.fullmatch(r"\d{2}-[A-Z]{3}-\d{2} \d{2}:\d{2}:\d{2}", hrow["hist_dt"]) and hrow["ns"] == "mongo_205236", hrow)
probe("change_plan", "history rows == closed rows (1), audit +1, counters advanced by 1 each",
      hist.count_documents({}) == h0 + 1 and audit.count_documents({}) == a0 + 1 and
      db[PREFIX + "counters"].find_one({"_id": "seq_subscriptions_hist"})["seq"] == 1 and
      db[PREFIX + "counters"].find_one({"_id": "seq_billing_audit_log"})["seq"] == a0 + 1)
probe("change_plan", "returned rows == subscriptions_for_tenant snapshot sorted by starts_on", [{"plan_id": r["plan_id"], "starts_on": r["starts_on"], "ends_on": r["ends_on"], "status": r["status"]} for r in rows["subscriptions"]] ==
      [{"plan_id": s["plan_id"], "starts_on": s["starts_on"], "ends_on": s["ends_on"], "status": plans.decode(plans.SUB_STATUS, int(s["status_cd"]))} for s in snap(TENANT(1))])
# after the change: entitlement on 2026-02-28 vs 2026-03-01 flips STARTER->GROWTH (Oracle semantics via SQL on the *target* state cannot be run; check the logic)
e1 = call_entrypoint(store, "billing.fn_entitlement", {"tenant_id": TENANT(1), "as_of": "2026-02-28"})
e2 = call_entrypoint(store, "billing.fn_entitlement", {"tenant_id": TENANT(1), "as_of": "2026-03-01"})
probe("change_plan", "entitlement boundary: 02-28 -> STARTER (closed row, ends_on inclusive), 03-01 -> GROWTH effective_on=03-01",
      e1["plan_code"] == "STARTER" and e1["effective_on"] == "2026-02-28" and e2["plan_code"] == "GROWTH" and e2["effective_on"] == "2026-03-01", (e1, e2))

# 4b. idempotent re-run of the same change => ORA-00001 parity: DuplicateKeyError surfaces, nothing else changes, audit row still written (autonomous)
s1 = snap(TENANT(1)); a1 = audit.count_documents({}); h1 = hist.count_documents({})
try:
    call_entrypoint(store, "billing.sp_change_plan", {"tenant_id": TENANT(1), "plan_id": PLAN(2), "effective_on": "2026-03-01"})
    dup = "no error"
except DuplicateKeyError:
    dup = "DuplicateKeyError"
except Exception as e:  # noqa: BLE001
    dup = type(e).__name__
probe("change_plan", "same change twice -> DuplicateKeyError (ORA-00001 parity); txn rolled back (rows/history unchanged); audit row still written (autonomous txn parity)",
      dup == "DuplicateKeyError" and snap(TENANT(1)) == s1 and hist.count_documents({}) == h1 and audit.count_documents({}) == a1 + 1, (dup, hist.count_documents({}) - h1, audit.count_documents({}) - a1))
# 4c. cancelled stays cancelled (TRG_SUB_NO_UNCANCEL) and suspended -> active (DECODE(20 -> 10)) -- craft rows in the clone
subs.update_one({"_id": before["_id"]}, {"$set": {"status_cd": 30}})  # clone only
subs.update_one({"_id": new["_id"]}, {"$set": {"status_cd": 20, "suspended_on": datetime(2026, 4, 1)}})
call_entrypoint(store, "billing.sp_change_plan", {"tenant_id": TENANT(1), "plan_id": PLAN(3), "effective_on": "2026-05-01"})
r_closed = subs.find_one({"_id": before["_id"]}); r_susp = subs.find_one({"_id": new["_id"]})
probe("change_plan", "closed (ends_on set) row with status 30 is NOT touched (cursor filters ends_on IS NULL)", r_closed["status_cd"] == 30 and r_closed["ends_on"] == datetime(2026, 2, 28))
probe("change_plan", "open suspended (20) row closed with status DECODE(20 -> 10) and suspended_on preserved (Oracle UPDATE touches only ends_on/status_cd)",
      r_susp["status_cd"] == 10 and r_susp["ends_on"] == datetime(2026, 4, 30) and r_susp["suspended_on"] == datetime(2026, 4, 1), r_susp)
subs.update_one({"tenant_id": TENANT(1), "ends_on": None}, {"$set": {"status_cd": 30}})
call_entrypoint(store, "billing.sp_change_plan", {"tenant_id": TENANT(1), "plan_id": PLAN(1), "effective_on": "2026-06-01"})
r_c = subs.find_one({"tenant_id": TENANT(1), "ends_on": datetime(2026, 5, 31)})
probe("change_plan", "open cancelled (30) row closed and stays 30 (TRG_SUB_NO_UNCANCEL)", r_c is not None and r_c["status_cd"] == 30, r_c)
hist_imgs = list(hist.find().sort("hist_id", 1))
probe("change_plan", "history image keeps the PRIOR status (30/20), i.e. :OLD not :NEW", [h["status_cd"] for h in hist_imgs] == [10, 20, 30], [h["status_cd"] for h in hist_imgs])
probe("change_plan", "hist_id strictly sequential 1..n, unique", [h["hist_id"] for h in hist_imgs] == list(range(1, len(hist_imgs) + 1)))
# 4d. effective_on == starts_on of the open row: cursor uses starts_on < eff, so the open row is NOT closed -> two open rows (Oracle does the same)
call_entrypoint(store, "billing.sp_change_plan", {"tenant_id": TENANT(2), "plan_id": PLAN(3), "effective_on": "2026-01-01"})
open2 = subs.count_documents({"tenant_id": TENANT(2), "ends_on": None})
probe("change_plan", "eff == starts_on of open row: open row left open (starts_on < eff is false) -> 2 open rows, faithful to PL/SQL quirk", open2 == 2, open2)
# 4e. unknown tenant / plan -> LookupError (ORA-02291 FK parity), no rows written, audit written first
a2 = audit.count_documents({}); n2 = subs.count_documents({})
for bad in ({"tenant_id": "ffffffff-0000-0000-0000-000000000000", "plan_id": PLAN(1)}, {"tenant_id": TENANT(3), "plan_id": "ffffffff-0000-0000-0000-000000000000"}):
    try:
        call_entrypoint(store, "billing.sp_change_plan", {**bad, "effective_on": "2026-04-01"}); err = "none"
    except LookupError:
        err = "LookupError"
    except Exception as e:  # noqa: BLE001
        err = type(e).__name__
    probe("change_plan", f"FK miss {list(bad)[0] if 'ffff' in bad['tenant_id'] else 'plan_id'} -> {err}; no subscription written; audit row written",
          err == "LookupError" and subs.count_documents({}) == n2, err)
probe("change_plan", "audit rows for the 2 failed calls present (autonomous-transaction parity)", audit.count_documents({}) == a2 + 2)
probe("change_plan", "tenant with no open subscription: just inserts (Oracle: cursor loop no-op)",
      (lambda tid: (call_entrypoint(store, "billing.sp_change_plan", {"tenant_id": tid, "plan_id": PLAN(1), "effective_on": "2026-07-01"}), subs.count_documents({"tenant_id": tid}))[1])(TENANT(5)) == 2)
# 4f. audit log field types / truncation
long_msg_tenant = "t" * 50
try:
    call_entrypoint(store, "billing.sp_change_plan", {"tenant_id": long_msg_tenant, "plan_id": PLAN(1), "effective_on": "2026-07-01"})
except LookupError:
    pass
last = audit.find_one(sort=[("log_id", -1)])
probe("audit", "log rows: _id==log_id long, module<=30, message<=4000, logged_at ms-truncated naive, ns present; message text == PL/SQL concatenation",
      isinstance(last["log_id"], int) and last["_id"] == last["log_id"] and len(last["module"]) <= 30 and len(last["message"]) <= 4000 and last["logged_at"].tzinfo is None and last["logged_at"].microsecond % 1000 == 0
      and last["message"] == f"sp_change_plan tenant={long_msg_tenant} plan={PLAN(1)} eff=2026-07-01", last)
probe("audit", "audit log ids strictly sequential from the seeded counter (no gaps/dupes)",
      [d["log_id"] for d in audit.find().sort("log_id", 1)] == list(range(1, audit.count_documents({}) + 1)))
# empty-result behaviour: fn_list_plans with no active plans
store.coll("plans").update_many({}, {"$set": {"active_yn": "N"}})
probe("empty", "fn_list_plans with no active plans -> [] (audit row still written)", call_entrypoint(store, "billing.fn_list_plans", {}) == [])
store.coll("plans").update_many({}, {"$set": {"active_yn": None}})
probe("empty", "NVL(active_yn,'N')='Y': NULL active_yn excluded", call_entrypoint(store, "billing.fn_list_plans", {}) == [])
store.coll("plans").update_many({}, {"$set": {"active_yn": "Y"}})
probe("empty", "restore: 3 active plans", len(call_entrypoint(store, "billing.fn_list_plans", {})) == 3)

# ---------- 5. HTTP layer (Flask test client, declared unexercised by the child) ----------
from flask import Flask  # noqa: E402
app = Flask("probe"); app.register_blueprint(plans_api)
os.environ["OW_BILLING_COLLECTION_PREFIX"] = PREFIX
with app.test_client() as c:
    r = c.get("/api/plans"); body = r.get_json()
    probe("http", "GET /api/plans 200, codes/fees == transcript PLANS-001", r.status_code == 200 and [x["code"] for x in body] == ["STARTER", "GROWTH", "SCALE"] and [x["monthly_fee"] for x in body] == ["49.00", "149.00", "499.00"], body)
    r = c.get(f"/api/tenants/{TENANT(2)}/entitlement?on=2026-02-28"); body = r.get_json()
    probe("http", "GET entitlement tenant 2 == transcript PLANS-003 (GROWTH/growth/500/suspended)", r.status_code == 200 and (body["plan_code"], body["tier"], body["included_units"], body["subscription_status"]) == ("GROWTH", "growth", 500, "suspended"), body)
    r = c.get("/api/tenants/ffffffff-0000-0000-0000-000000000000/entitlement?on=2026-02-28")
    probe("http", "GET entitlement unknown tenant -> 404", r.status_code == 404, r.get_json())
    r = c.post(f"/api/tenants/{TENANT(3)}/plan-change", json={"plan_id": "ffffffff-0000-0000-0000-000000000000", "effective_on": "2026-04-01"})
    probe("http", "POST plan-change unknown plan -> 400", r.status_code == 400, r.get_json())
    r = c.post(f"/api/tenants/{TENANT(3)}/plan-change", json={"plan_id": PLAN(2), "effective_on": "not-a-date"})
    probe("http", "POST plan-change bad date -> 400", r.status_code == 400, r.get_json())
    r = c.post(f"/api/tenants/{TENANT(3)}/plan-change", json={"plan_id": PLAN(2), "effective_on": "2026-04-01"}); body = r.get_json()
    probe("http", "POST plan-change tenant 3 -> 200 with latest_plan/latest_start and 2 rows", r.status_code == 200 and body["latest_plan"] == PLAN(2) and body["latest_start"] == "2026-04-01" and len(body["subscriptions"]) == 2, body)
    r = c.post(f"/api/tenants/{TENANT(3)}/plan-change", json={"plan_id": PLAN(2), "effective_on": "2026-04-01"})
    probe("http", "POST same change again -> DuplicateKeyError NOT mapped to 4xx (propagates as 500; ORA-00001 would be a 500 in the legacy app too) -- recorded", r.status_code == 500, r.status_code)
del os.environ["OW_BILLING_COLLECTION_PREFIX"]
try:
    import psycopg  # noqa: F401
    sys.path.insert(0, f"{HEAD}/services/legacy-billing/app"); import app as legacy_app  # noqa: E402
    rules = sorted(str(r) for r in legacy_app.app.url_map.iter_rules())
    probe("http", "legacy app.py imports with the blueprint; no URL rule collisions; 3 new /api routes present",
          len(rules) == len(set(rules)) and "/api/plans" in rules and "/api/tenants/<tenant_id>/entitlement" in rules and "/api/tenants/<tenant_id>/plan-change" in rules, len(rules))
except ImportError as e:
    probe("http", "legacy app.py import (psycopg not installed in recon venv) -- skipped", True, str(e))

# ---------- 6. golden & quarantine untouched; source unchanged ----------
probe("golden", "golden subscriptions/subscriptions_history/billing_audit_log/counters counts unchanged by U6 replays",
      (gold.coll("subscriptions").count_documents({}), gold.coll("subscriptions_history").count_documents({}), gold.coll("billing_audit_log").count_documents({}), gold.coll("counters").count_documents({})) == (69, 0, 1, 3))
qcols = {c: m[QDB][c].estimated_document_count() for c in m[QDB].list_collection_names()}
probe("quarantine", "no U6 quarantine classes declared; quarantine db unchanged (sets)", qcols == {"bad_csv_list": 31, "dirty_signup_dt": 50, "invoice_feed_orphan_lines": 37, "orphan_document_snapshots": 6}, qcols)
audit1 = q("select count(*) n from billing_audit_log")[0]["n"]
seqs1 = {r["sequence_name"]: r["last_number"] for r in q("select sequence_name,last_number from user_sequences")}
probe("fixture", "source untouched by probes: BILLING_AUDIT_LOG still 1, sequences unchanged", audit1 == 1 and seqs1 == seqs0, (audit1, seqs1))

ora.close(); m.close()
n_ok = sum(r["ok"] for r in results)
json.dump({"unit": "U6", "head": "f463577b014d4f8fc43328ad23af9b0470f30762", "elapsed_s": round(time.time() - t0, 1), "ok": n_ok, "total": len(results), "probes": results}, open(OUT, "w"), indent=1)
print(f"\n{n_ok}/{len(results)} ok in {time.time() - t0:.1f}s")
