"""Wave 2b independent probes for U7 (PKG_RATING -> ow_billing.rating, D10).

Source side is PLAIN SQL only (never PKG_RATING -- compute_rating/sp_finalize write
BILLING_AUDIT_LOG through pkg_ow_util.log_msg). The PL/SQL arithmetic is re-expressed as
one Oracle SQL statement (so NVL/LEAST/GREATEST/ROUND/ADD_MONTHS/date-subtraction keep
Oracle semantics) and compared to the head's Python against the replay_u7_* clone.
Golden collections are read-only here; the clone is mutated (finalize) and reloaded after.
"""
import hashlib, json, os, re, sys, time
from datetime import date, datetime, timedelta
from decimal import Decimal

import oracledb
import yaml
from bson import Decimal128, Int64
from bson.json_util import dumps, CANONICAL_JSON_OPTIONS
from pymongo import MongoClient

HEAD = os.path.expanduser("~/wave_recon/heads/u7")
sys.path.insert(0, f"{HEAD}/services/legacy-billing/app")
from ow_billing import rating  # noqa: E402

OUT = os.path.expanduser("~/wave_recon/w2b/U7/probes.json")
DB = "ow_tp_mongodb_205236"
QDB = "ow_tp_mongodb_205236_quarantine"
PREFIX = "replay_u7_"
TENANT = lambda n: f"00000000-0000-0000-0000-{n:012d}"  # noqa: E731
results = []
t0 = time.time()


def probe(area, name, ok, detail=""):
    results.append({"area": area, "probe": name, "ok": bool(ok), "detail": str(detail)[:600]})
    print(("ok  " if ok else "FAIL"), area, "|", name, "|", str(detail)[:200], flush=True)


def canon(v):
    if isinstance(v, Decimal128):
        v = v.to_decimal()
    if isinstance(v, Decimal):
        return str(int(v)) if v == v.to_integral() else str(v.normalize())
    if isinstance(v, (int, Int64)):
        return str(v)
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
store = rating.RatingStore(db, PREFIX)


def q(sql, **binds):
    cur.execute(sql, binds)
    cols = [d[0].lower() for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


# ---------- 0. fixture identity / provenance ----------
meta = q("select to_char(initialized_at,'YYYY-MM-DD HH24:MI:SS.FF6') ia from fixture_meta")[0]["ia"]
probe("fixture", "FIXTURE_META.INITIALIZED_AT unchanged", meta == "2026-09-01 20:53:10.961888", meta)
audit0 = q("select count(*) n from billing_audit_log")[0]["n"]
seqs0 = {r["sequence_name"]: r["last_number"] for r in q("select sequence_name,last_number from user_sequences")}
probe("fixture", "source BILLING_AUDIT_LOG rows before probes", audit0 == 1, audit0)


def norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()


live = "".join(r["text"] for r in q("select text from user_source where name='PKG_RATING' and type='PACKAGE BODY' order by line"))
filetxt = open(f"{HEAD}/services/legacy-billing/db/oracle/packages/03_pkg_rating.sql").read()
body = filetxt.split("CREATE OR REPLACE PACKAGE BODY", 1)[1].split("\n/\n", 1)[0]
probe("provenance", "live USER_SOURCE PKG_RATING body == checked-in file (the transcripts' file-based ORACLE_SOURCE_SHA is therefore live-valid)",
      norm(live) == norm("PACKAGE BODY" + body), f"live {len(live)} chars")
sys.path.insert(0, f"{HEAD}/procs/harness")
from oracle_record import oracle_source_sha  # noqa: E402
sha = oracle_source_sha()
tr_sha = {json.load(open(f"{HEAD}/procs/oracle/transcripts/rating/RATING-{i:03d}.json"))["oracle_source_sha"] for i in range(1, 9)}
probe("provenance", "8 rating transcripts carry the current ORACLE_SOURCE_SHA", tr_sha == {sha} and open(f"{HEAD}/procs/oracle/transcripts/ORACLE_SOURCE_SHA").read().strip() == sha, sha[:16])

# ---------- 1. clone baseline vs golden ----------
def fp(coll):
    h = hashlib.sha256(); n = 0
    for d in db[coll].find({}, sort=[("_id", 1)]):
        h.update(dumps(d, json_options=CANONICAL_JSON_OPTIONS, sort_keys=True).encode()); h.update(b"\n"); n += 1
    return n, h.hexdigest()


SRC = ["subscriptions", "subscriptions_history", "usage_events", "rating_periods", "billing_invoices", "credit_notes",
       "dunning_attempts", "notifications", "billing_audit_log", "plans", "tenants"]
for c in SRC:
    probe("clone", f"{PREFIX}{c} == golden {c} (canonical dump)", fp(c) == fp(PREFIX + c), fp(c))
gi = {c: sorted((v["key"], v.get("unique", False), v.get("expireAfterSeconds")) for k, v in db[c].index_information().items()) for c in SRC}
ci = {c: sorted((v["key"], v.get("unique", False), v.get("expireAfterSeconds")) for k, v in db[PREFIX + c].index_information().items()) for c in SRC}
diff_idx = {c: (gi[c], ci[c]) for c in gi if gi[c] != ci[c]}
probe("clone", "clone index specs == golden index specs", not diff_idx, json.dumps(diff_idx, default=str))
gu = {c: [k for k, v in db[c].index_information().items() if v.get("unique")] for c in SRC}
probe("clone", "golden/clone have NO unique index on rating_periods (tenant_id, period_start) -- uq_rating_periods relies on _id=md5 only -- recorded",
      True, {c: u for c, u in gu.items() if u})
vo = {c: next(db.list_collections(filter={"name": PREFIX + c}))["options"] for c in SRC}
gvo = {c: next(db.list_collections(filter={"name": c}))["options"] for c in SRC}
probe("clone", "validators cloned identically for all 11 collections", all(vo[c].get("validator") == gvo[c].get("validator") for c in SRC),
      [c for c in SRC if "validator" in gvo[c]])
probe("clone", "no *__staging residue", not [c for c in db.list_collection_names() if "staging" in c])
cnt = list(db[PREFIX + "counters"].find())
probe("counters", "replay_u7_counters seeded {SEQ_BILLING_AUDIT_LOG: max(log_id)} == USER_SEQUENCES.last_number-1 (NOCACHE)",
      len(cnt) == 1 and cnt[0]["_id"] == "SEQ_BILLING_AUDIT_LOG" and cnt[0]["value"] == seqs0["SEQ_BILLING_AUDIT_LOG"] - 1
      and cnt[0]["value"] == db[PREFIX + "billing_audit_log"].find_one(sort=[("log_id", -1)])["log_id"], cnt)
probe("counters", "counter value stored as BSON long", isinstance(cnt[0]["value"], (Int64, int)), type(cnt[0]["value"]).__name__)

# ---------- 2. Tier-1..3 style checks the U7 gate does NOT cover: billing_audit_log & rating_results ----------
src_audit = q("select log_id, to_char(logged_at,'YYYY-MM-DD HH24:MI:SS') la, module, message from billing_audit_log order by log_id")
tgt_audit = [{"log_id": d["log_id"], "la": d["logged_at"].strftime("%Y-%m-%d %H:%M:%S"), "module": d["module"], "message": d["message"]}
             for d in db[PREFIX + "billing_audit_log"].find(sort=[("log_id", 1)])]
probe("ungraded", "replay_u7_billing_audit_log == BILLING_AUDIT_LOG (keyed, all columns) -- child left it ungraded T1-T3",
      [(r["log_id"], r["la"], r["module"], r["message"]) for r in src_audit] == [(r["log_id"], r["la"], r["module"], r["message"]) for r in tgt_audit],
      (src_audit, tgt_audit))
rr = q("""select rr.id, rr.period_id, rr.subscription_id, rr.used_units, rr.quota_units, rr.rollover_units, rr.billable_units,
          to_char(rr.overage_amount,'FM9999999990.00') overage_amount, to_char(rr.created_at,'YYYY-MM-DD HH24:MI:SS') created_at
          from rating_results rr order by rr.period_id, rr.id""")
emb = []
for d in db[PREFIX + "rating_periods"].find(sort=[("_id", 1)]):
    for r in sorted(d["results"], key=lambda r: r["id"]):
        emb.append({**{k: canon(r[k]) for k in ("id", "period_id", "subscription_id", "used_units", "quota_units", "rollover_units", "billable_units")},
                    "overage_amount": str(r["overage_amount"].to_decimal()), "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M:%S")})
srr = [{k: canon(v) if k not in ("overage_amount", "created_at") else v for k, v in r.items()} for r in rr]
probe("embed", f"rating_periods.results[] == RATING_RESULTS row-for-row ({len(rr)} rows, 9 columns, keyed by id)", srr == emb, (srr[:1], emb[:1]))
lens = list(db[PREFIX + "rating_periods"].aggregate([{"$group": {"_id": {"$size": "$results"}, "n": {"$sum": 1}}}]))
per_period = q("select rp.id, count(rr.id) n from rating_periods rp left join rating_results rr on rr.period_id=rp.id group by rp.id")
probe("embed", "results[] length distribution == child rows per period (all 1)", lens == [{"_id": 1, "n": 3}] and all(r["n"] == 1 for r in per_period), lens)
probe("embed", "results[].overage_amount is Decimal128 (2dp), unit counts are int/long, created_at is date",
      all(isinstance(r["overage_amount"], Decimal128) and isinstance(r["used_units"], int) and isinstance(r["created_at"], datetime)
          for d in db[PREFIX + "rating_periods"].find() for r in d["results"]))

# null distribution / dup keys / min-max per graded collection
for tbl, coll, cols in (("usage_events", "usage_events", ["units", "kind_cd", "occurred_at"]), ("subscriptions", "subscriptions", ["ends_on", "suspended_on", "status_cd", "plan_id"]),
                        ("rating_periods", "rating_periods", ["period_end"]), ("plans", "plans", ["active_yn", "overage_rate"])):
    sn = {c: q(f"select count(*) n from {tbl} where {c} is null")[0]["n"] for c in cols}
    tn = {c: db[PREFIX + coll].count_documents({"$or": [{c: None}, {c: {"$exists": False}}]}) for c in cols}
    probe("nulls", f"{coll}: NULL counts per field source==target", sn == tn, (sn, tn))
    dup = list(db[PREFIX + coll].aggregate([{"$group": {"_id": "$id", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}]))
    probe("dupes", f"{coll}: no duplicate business id; _id==id everywhere", not dup and db[PREFIX + coll].count_documents({"$expr": {"$ne": ["$_id", "$id"]}}) == 0, dup)
mm = q("select to_char(min(occurred_at),'YYYY-MM-DD HH24:MI:SS') mn, to_char(max(occurred_at),'YYYY-MM-DD HH24:MI:SS') mx, min(units) mnu, max(units) mxu, sum(units) su, count(distinct tenant_id) nt from usage_events")[0]
tm = list(db[PREFIX + "usage_events"].aggregate([{"$group": {"_id": None, "mn": {"$min": "$occurred_at"}, "mx": {"$max": "$occurred_at"}, "mnu": {"$min": "$units"}, "mxu": {"$max": "$units"}, "su": {"$sum": "$units"}, "nt": {"$addToSet": "$tenant_id"}}}]))[0]
probe("boundary", "usage_events min/max occurred_at, min/max/sum units, distinct tenants source==target",
      (mm["mn"], mm["mx"], mm["mnu"], mm["mxu"], mm["su"], mm["nt"]) == (tm["mn"].strftime("%Y-%m-%d %H:%M:%S"), tm["mx"].strftime("%Y-%m-%d %H:%M:%S"), tm["mnu"], tm["mxu"], tm["su"], len(tm["nt"])), mm)
dupk = list(db[PREFIX + "rating_periods"].aggregate([{"$group": {"_id": {"t": "$tenant_id", "s": "$period_start"}, "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}]))
probe("dupes", "rating_periods: (tenant_id, period_start) unique in clone (uq_rating_periods)", not dupk, dupk)
kinds_s = {r["kind_cd"]: r["n"] for r in q("select kind_cd, count(*) n from usage_events group by kind_cd")}
kinds_t = {r["_id"]: r["n"] for r in db[PREFIX + "usage_events"].aggregate([{"$group": {"_id": "$kind_cd", "n": {"$sum": 1}}}])}
probe("dist", "usage_events.kind_cd distribution source==target (DECODE domain 1/2/3, no UNKNOWN in data -- recorded)", kinds_s == kinds_t, kinds_s)

# ---------- 3. compute_rating parity: Oracle SQL re-expression vs Python, ALL tenants x windows ----------
SQL_RATE = """
with sub as (
  select * from (select s.id, s.status_cd, s.suspended_on, s.plan_id from subscriptions s
                 where s.tenant_id = :t and s.starts_on <= :pe and (s.ends_on is null or s.ends_on >= :ps)
                 order by s.starts_on desc) where rownum <= 1),
pl as (select p.included_units inc, p.overage_rate rate from plans p, sub where p.id = sub.plan_id),
used as (select nvl(sum(nvl(u.units,0)),0) used from usage_events u where u.tenant_id = :t
          and to_char(u.occurred_at,'YYYYMMDD') >= to_char(:ps,'YYYYMMDD') and to_char(u.occurred_at,'YYYYMMDD') <= to_char(:pe,'YYYYMMDD')),
pri as (select nvl(sum(nvl(rr.rollover_units,0)),0) prior0 from rating_results rr, rating_periods rp
         where rp.id = rr.period_id and rp.tenant_id = :t and rp.period_start < :ps and rp.period_start >= add_months(:ps, -3)),
a as (select (select inc from pl) inc, (select rate from pl) rate, used.used, least(nvl(2*(select inc from pl), pri.prior0), pri.prior0) prior1,
             (select status_cd from sub) st, (select suspended_on from sub) susp, (select id from sub) sub_id from used, pri),
b as (select a.*, least(prior1, nvl(inc*2, prior1)) rollover,
             greatest(nvl(used - least(prior1, nvl(inc*2, prior1)) - inc, 0), 0) billable from a),
c as (select b.*, least(billable, 101) ft, greatest(billable - 101, 0) st2,
             round(least(billable,101)*rate + greatest(billable-101,0)*rate*1.5, 2) ov,
             case when st = 20 and susp is not null and susp between :ps and :pe then (:pe - susp + 1)/(:pe - :ps + 1) end factor from b)
select sub_id, used, inc quota, rollover,
       case when factor is not null then round(billable*factor) else billable end billable,
       ft, st2, case when factor is not null then round(ov*factor, 2) else ov end overage, factor
from c"""


def ora_rate(t, ps, pe):
    r = q(SQL_RATE, t=t, ps=ps, pe=pe)[0]
    return {"used_units": canon(r["used"]), "quota_units": canon(r["quota"]), "rollover_units": canon(r["rollover"]),
            "billable_units": canon(r["billable"]), "first_tier_units": canon(r["ft"]), "second_tier_units": canon(r["st2"]),
            "overage_amount": canon(r["overage"])}, r


def py_rate(t, ps, pe):
    row = rating.fn_usage_rating(store, t, ps, pe)[0]
    return {k: canon(row[k]) for k in ("used_units", "quota_units", "rollover_units", "billable_units", "first_tier_units", "second_tier_units", "overage_amount")}, row


tenants = [r["id"] for r in q("select id from tenants order by id")]
WINDOWS = [(date(2026, 2, 1), date(2026, 2, 28)), (date(2026, 1, 1), date(2026, 1, 31)), (date(2026, 3, 1), date(2026, 3, 31)),
           (date(2026, 2, 15), date(2026, 3, 15)), (date(2025, 12, 1), date(2025, 12, 31)), (date(2026, 2, 28), date(2026, 2, 28)),
           (date(2026, 2, 1), date(2026, 2, 1)), (date(2026, 1, 15), date(2026, 2, 14))]
audit_before = db[PREFIX + "billing_audit_log"].count_documents({})
mism = []; hits = 0; nosub = 0; factor_hits = 0; nonzero_ov = 0
for t in tenants:
    for ps, pe in WINDOWS:
        o, oraw = ora_rate(t, ps, pe)
        p, praw = py_rate(t, ps, pe)
        if o != p:
            mism.append((t, str(ps), str(pe), o, p))
        hits += 1
        nosub += oraw["sub_id"] is None
        factor_hits += oraw["factor"] is not None
        nonzero_ov += bool(oraw["overage"])
probe("rating", f"fn_usage_rating parity: {len(tenants)} tenants x {len(WINDOWS)} windows = {hits} ops (all 7 numeric outputs; {nosub} no-covering-sub, {factor_hits} suspension-factor, {nonzero_ov} non-zero overage)",
      not mism, mism[:3])
probe("rating", "period_start/period_end/tenant_id echoed back as naive midnight datetimes",
      all(isinstance(praw[k], datetime) and praw[k].time() == datetime.min.time() for k in ("period_start", "period_end")) and praw["tenant_id"] == t)
n_after = db[PREFIX + "billing_audit_log"].count_documents({})
n_re = db[PREFIX + "billing_audit_log"].count_documents({"module": "RATING", "message": {"$regex": r"^compute tenant=\S+ used=-?\d+ billable=-?\d+$"}})
probe("rating", f"each compute wrote exactly one audit row (module RATING, 'compute tenant=.. used=.. billable=..')",
      n_after == audit_before + hits and n_re == hits,
      (audit_before, hits, n_after, n_re, db[PREFIX + "billing_audit_log"].find_one({"module": "RATING", "message": {"$not": {"$regex": r"^compute tenant=\S+ used=-?\d+ billable=-?\d+$"}}})))
# unknown tenant / tenant with zero events / boundary day-string semantics
o, _ = ora_rate("no-such-tenant", date(2026, 2, 1), date(2026, 2, 28)); p, _ = py_rate("no-such-tenant", date(2026, 2, 1), date(2026, 2, 28))
probe("rating", "unknown tenant: used 0, quota NULL, rollover 0, billable 0, overage NULL (Oracle NULL propagation) == Python", o == p, (o, p))
zero = [r["id"] for r in q("select t.id from tenants t where not exists (select 1 from usage_events u where u.tenant_id=t.id)")]
probe("rating", f"{len(zero)} tenants without usage events (empty-aggregate path covered by the Jan/Dec windows and the unknown tenant instead) -- recorded", True, zero[:3])
# time-of-day boundary: events are at 10:00; a window ending on the event day must include them (string compare), a window ending the day before must not
t1 = q("select tenant_id t, to_char(min(occurred_at),'YYYY-MM-DD') d, count(*) n from usage_events group by tenant_id order by 3 desc fetch first 1 row only")[0]
d0 = date.fromisoformat(t1["d"])
o1, _ = ora_rate(t1["t"], d0, d0); p1, _ = py_rate(t1["t"], d0, d0)
o2, _ = ora_rate(t1["t"], d0 - timedelta(days=1), d0 - timedelta(days=1)); p2, _ = py_rate(t1["t"], d0 - timedelta(days=1), d0 - timedelta(days=1))
probe("rating", "day-string window boundary: window ending on the event day counts the 10:00 events, previous day does not (both stacks)",
      o1 == p1 and o2 == p2 and o1["used_units"] != "0" and o2["used_units"] == "0", (o1["used_units"], o2["used_units"]))
# tz-aware input handled (as_datetime) same as naive
from datetime import timezone
pa, _ = py_rate(TENANT(1), datetime(2026, 2, 1, tzinfo=timezone.utc), datetime(2026, 2, 28, tzinfo=timezone.utc))
pb, _ = py_rate(TENANT(1), date(2026, 2, 1), date(2026, 2, 28))
probe("rating", "tz-aware UTC datetimes rate identically to dates", pa == pb)
# rollover cap exercised: tenant 1 has 3 prior periods (Nov, Dec 2025, Jan 2026) x 100 -> Feb prior=300 capped to 2*100
o, _ = ora_rate(TENANT(1), date(2026, 2, 1), date(2026, 2, 28))
probe("rating", "rollover double-cap exercised on tenant 1 Feb-2026 (prior 300 -> 200 = 2*included)", o["rollover_units"] == "200", o)
o, _ = ora_rate(TENANT(1), date(2026, 3, 1), date(2026, 3, 31))
probe("rating", "ADD_MONTHS(-3) window: tenant 1 Mar-2026 sees Dec+Jan (+Feb none) = 200, Nov excluded", o["rollover_units"] == "200", o)
# ADD_MONTHS end-of-month semantics vs the Python port
for d0 in (datetime(2026, 5, 31), datetime(2026, 3, 31), datetime(2026, 2, 28), datetime(2026, 3, 30), datetime(2024, 2, 29)):
    o = q("select to_char(add_months(:d,-3),'YYYY-MM-DD') x from dual", d=d0)[0]["x"]
    p = rating.add_months(d0, -3).strftime("%Y-%m-%d")
    if o != p:
        mism.append((d0, o, p))
probe("rating", "add_months(-3) == Oracle ADD_MONTHS incl. last-day-of-month rule (5 dates)", not mism, mism)

# ---------- 4. fn_usage_summary parity ----------
SQL_SUM = """select decode(u.kind_cd,1,'api',2,'storage',3,'compute','UNKNOWN') kind, count(*) event_count, nvl(sum(u.units),0) units
 from usage_events u where u.tenant_id=:t and to_char(u.occurred_at,'YYYYMMDD') between to_char(:ps,'YYYYMMDD') and to_char(:pe,'YYYYMMDD')
 group by decode(u.kind_cd,1,'api',2,'storage',3,'compute','UNKNOWN') order by 1"""
mism = []; rows = 0
for t in tenants + ["no-such-tenant"]:
    for ps, pe in WINDOWS[:4]:
        o = [[r["kind"], canon(r["event_count"]), canon(r["units"])] for r in q(SQL_SUM, t=t, ps=ps, pe=pe)]
        p = [[r["kind"], canon(r["event_count"]), canon(r["units"])] for r in rating.fn_usage_summary(store, t, ps, pe)]
        rows += len(o)
        if o != p:
            mism.append((t, str(ps), o, p))
probe("summary", f"fn_usage_summary parity: {len(tenants)+1} tenants x 4 windows, {rows} grouped rows (kind order, count, units)", not mism, mism[:3])
probe("summary", "fn_usage_summary writes no audit row (PL/SQL has no log_msg)", db[PREFIX + "billing_audit_log"].count_documents({}) == audit_before + hits + 5)

# ---------- 5. sp_finalize_rating semantics (clone only) ----------
def md5_uuid_ora(s):
    return q("select lower(regexp_replace(standard_hash(:s,'MD5'),'(.{8})(.{4})(.{4})(.{4})(.{12})','\\1-\\2-\\3-\\4-\\5')) u from dual", s=s)[0]["u"]


t, ps, pe = TENANT(1), date(2026, 2, 1), date(2026, 2, 28)
pid = md5_uuid_ora(f"{t}2026-02-01"); rid = md5_uuid_ora(pid)
before_rp = db[PREFIX + "rating_periods"].count_documents({})
doc = rating.sp_finalize_rating(store, t, ps, pe)
o, oraw = ora_rate(t, ps, pe)
r = doc["results"]
probe("finalize", "new period: _id/id == f_md5_uuid(tenant||YYYY-MM-DD) (STANDARD_HASH parity), results[0].id == f_md5_uuid(period_id)",
      doc["_id"] == pid and doc["id"] == pid and len(r) == 1 and r[0]["id"] == rid and r[0]["period_id"] == pid, (pid, rid))
probe("finalize", "period doc shape == RATING_PERIODS columns + ns; period_start/end midnight", set(doc) == {"_id", "id", "tenant_id", "period_start", "period_end", "results", "ns"}
      and doc["period_start"] == datetime(2026, 2, 1) and doc["period_end"] == datetime(2026, 2, 28) and doc["ns"] == "mongo_205236", sorted(doc))
probe("finalize", "results[0] == RATING_RESULTS columns: subscription_id from covering sub, used/quota/billable/overage from compute, rollover_units = GREATEST(quota-used,0), created_at = CAST(period_end)",
      r[0]["subscription_id"] == oraw["sub_id"] and canon(r[0]["used_units"]) == o["used_units"] and canon(r[0]["quota_units"]) == o["quota_units"]
      and canon(r[0]["billable_units"]) == o["billable_units"] and str(r[0]["overage_amount"].to_decimal()) == str(Decimal(o["overage_amount"]).quantize(Decimal("0.01")))
      and r[0]["rollover_units"] == max(int(o["quota_units"]) - int(o["used_units"]), 0) and r[0]["created_at"] == datetime(2026, 2, 28)
      and set(r[0]) == {"id", "period_id", "subscription_id", "used_units", "quota_units", "rollover_units", "billable_units", "overage_amount", "created_at"}, r[0])
probe("finalize", "results[] element types: Int64 counts, Decimal128 money (matches the U5 embedded shape)",
      all(isinstance(r[0][k], Int64) for k in ("used_units", "quota_units", "rollover_units", "billable_units")) and isinstance(r[0]["overage_amount"], Decimal128),
      {k: type(v).__name__ for k, v in r[0].items()})
probe("finalize", "two audit rows per finalize (compute + 'finalized period=<id>')",
      db[PREFIX + "billing_audit_log"].find_one(sort=[("log_id", -1)])["message"] == f"finalized period={pid}"
      and db[PREFIX + "billing_audit_log"].count_documents({}) == audit_before + hits + 5 + 2)
# re-finalize with a different period_end -> DUP_VAL_ON_INDEX path: period_end updated, result refreshed in place, no second element
doc2 = rating.sp_finalize_rating(store, t, ps, date(2026, 2, 27))
o2, _ = ora_rate(t, ps, date(2026, 2, 27))
probe("finalize", "re-finalize same (tenant, period_start) with new period_end: UPDATE path -> period_end updated, results[] still 1 element, same ids, amounts refreshed to the new window",
      doc2["period_end"] == datetime(2026, 2, 27) and len(doc2["results"]) == 1 and doc2["results"][0]["id"] == rid
      and canon(doc2["results"][0]["used_units"]) == o2["used_units"] and db[PREFIX + "rating_periods"].count_documents({}) == before_rp + 1,
      (canon(doc["results"][0]["used_units"]), canon(doc2["results"][0]["used_units"])))
probe("finalize", "UPDATE rating_results touches only the 4 amounts: quota_units, subscription_id, created_at keep INSERT-time values (PL/SQL parity: created_at stays 02-28)",
      doc2["results"][0]["created_at"] == datetime(2026, 2, 28) and doc2["results"][0]["quota_units"] == r[0]["quota_units"], doc2["results"][0]["created_at"])
# re-finalize a period that pre-exists in the fixture (Jan 2026 tenant 1, fixture id 4000...02 != md5): Oracle INSERT hits uq_rating_periods (tenant, period_start) -> UPDATE by (tenant,start); result INSERT then hits... FK ok, new md5 result id -> a 2nd rating_results row in Oracle
pre = db[PREFIX + "rating_periods"].find_one({"tenant_id": t, "period_start": datetime(2026, 1, 1)})
doc3 = rating.sp_finalize_rating(store, t, date(2026, 1, 1), date(2026, 1, 31))
probe("finalize", "fixture period with non-md5 id (4000..02): DUP_VAL_ON_INDEX(uq) -> UPDATE period_end; result appended under md5 id => 2 results[] (Oracle would also hold 2 RATING_RESULTS rows: the fixture's and the md5 one)",
      doc3["_id"] == pre["_id"] and len(doc3["results"]) == 2 and {x["id"] for x in doc3["results"]} == {pre["results"][0]["id"], md5_uuid_ora(md5_uuid_ora(f"{t}2026-01-01"))}
      and db[PREFIX + "rating_periods"].count_documents({"tenant_id": t, "period_start": datetime(2026, 1, 1)}) == 1, [x["id"] for x in doc3["results"]])
# tenant with no covering subscription -> ORA-01400 parity (subscription_id/quota NOT NULL)
try:
    rating.sp_finalize_rating(store, "no-such-tenant", ps, pe); res = "no error"
except rating.RatingIntegrityError as e:
    res = f"RatingIntegrityError: {e}"
probe("finalize", "no covering subscription -> RatingIntegrityError (ORA-01400 parity), nothing written", res.startswith("RatingIntegrityError")
      and db[PREFIX + "rating_periods"].count_documents({"tenant_id": "no-such-tenant"}) == 0, res)
probe("finalize", "failed finalize still wrote the compute audit row but no 'finalized' row (log_msg before the INSERT in PL/SQL)",
      db[PREFIX + "billing_audit_log"].find_one(sort=[("log_id", -1)])["message"].startswith("compute tenant=no-such-tenant"))
ids = [d["log_id"] for d in db[PREFIX + "billing_audit_log"].find(sort=[("log_id", 1)])]
probe("audit", "audit log_ids strictly sequential from the seeded counter, _id==log_id, counter == max", ids == list(range(1, len(ids) + 1))
      and db[PREFIX + "counters"].find_one({"_id": "SEQ_BILLING_AUDIT_LOG"})["value"] == ids[-1], (ids[0], ids[-1]))
# counter missing -> reconcile from audit log (shared-collection scenario)
db[PREFIX + "counters"].delete_one({"_id": "SEQ_BILLING_AUDIT_LOG"})
rating.log_msg(store, "PROBE", "after counter loss")
top = db[PREFIX + "billing_audit_log"].find_one(sort=[("log_id", -1)])
probe("audit", "missing counter doc -> _reconcile_log_sequence resumes at max(log_id)+1 (no duplicate/reset)", top["log_id"] == ids[-1] + 1 and top["module"] == "PROBE", top["log_id"])

# ---------- 6. transcript replay (app-level) ----------
mism = []
for i in range(1, 9):
    sc = yaml.safe_load(open(f"{HEAD}/procs/scenarios/rating/{i:03d}.yaml"))
    tr = json.load(open(f"{HEAD}/procs/oracle/transcripts/rating/RATING-{i:03d}.json"))
    inp = {x["name"]: x["value"] for x in sc["inputs"]}
    ps_, pe_ = date.fromisoformat(str(inp["period_start"])), date.fromisoformat(str(inp["period_end"]))
    if sc["entrypoint"] == "billing.sp_finalize_rating":
        continue  # replayed by the gate on a fresh clone; the clone is dirty here
    fn = rating.fn_usage_rating if sc["entrypoint"] == "billing.fn_usage_rating" else rating.fn_usage_summary
    rows = fn(store, str(inp["tenant_id"]), ps_, pe_)
    got = {}
    for f in sc["fields"]:
        vals = [None if r.get(f["from"]) is None else (str(Decimal(str(r[f["from"]])).quantize(Decimal("0.01"))) if f["type"] == "decimal" else int(r[f["from"]]) if f["type"] == "integer" else str(r[f["from"]])) for r in rows]
        got[f["name"]] = vals if f.get("collect") else (vals[0] if vals else None)
    exp = tr["business_fields"]
    if any(str(got[k]) != str(exp[k]) for k in exp):
        mism.append((sc["id"], exp, got))
probe("transcripts", "read-only rating transcripts replayed on the (dirty) clone == recorded Oracle business_fields", not mism, mism)

# ---------- 7. golden / quarantine / source untouched ----------
G = {c: fp(c) for c in SRC + ["counters"]}
G0 = json.load(open(os.path.expanduser("~/wave_recon/w2b/golden_pre_fingerprint.json")))
same = all(G0[f"{DB}.{c}"]["sha256"] == G[c][1] for c in G if f"{DB}.{c}" in G0)
probe("golden", "golden collections unchanged since wave pre-fingerprint", same, [c for c in G if f"{DB}.{c}" in G0 and G0[f"{DB}.{c}"]["sha256"] != G[c][1]])
qd = m[QDB]
qsets = {c: qd[c].count_documents({}) for c in qd.list_collection_names()}
probe("quarantine", "no U7 quarantine classes declared; quarantine db unchanged (sets)", qsets == {"bad_csv_list": 31, "dirty_signup_dt": 50, "invoice_feed_orphan_lines": 37, "orphan_document_snapshots": 6}, qsets)
probe("fixture", "source untouched by probes: BILLING_AUDIT_LOG still 1, sequences unchanged, RATING_* counts unchanged",
      q("select count(*) n from billing_audit_log")[0]["n"] == 1 and {r["sequence_name"]: r["last_number"] for r in q("select sequence_name,last_number from user_sequences")} == seqs0
      and q("select count(*) n from rating_periods")[0]["n"] == 3 and q("select count(*) n from rating_results")[0]["n"] == 3, seqs0["SEQ_BILLING_AUDIT_LOG"])

json.dump({"unit": "U7", "head": "f05741f3d9cc9acb6c24dedac6d2217351c83318", "n": len(results), "ok": sum(r["ok"] for r in results),
           "elapsed_s": round(time.time() - t0, 1), "results": results}, open(OUT, "w"), indent=1)
print(f"\n{sum(r['ok'] for r in results)}/{len(results)} ok in {time.time()-t0:.1f}s")
