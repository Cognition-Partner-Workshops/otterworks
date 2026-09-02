"""Wave 3 independent adversarial probes for U9 (PKG_DUNNING -> ow_billing.dunning).
Oracle observed via PLAIN SQL only. Mutates ONLY replay_u9_* (the caller reloads before/after).
Expectations come from an independent Python simulation of the PL/SQL fed by Oracle SQL / clone state."""
import hashlib, json, os, sys, time
from datetime import date, datetime, timedelta
from decimal import Decimal
from bson import Decimal128, Int64
from bson.json_util import dumps, CANONICAL_JSON_OPTIONS
from pymongo import MongoClient
import oracledb

HEAD = os.path.expanduser("~/wave_recon/heads/u9/services/legacy-billing/app")
sys.path.insert(0, HEAD)
from ow_billing import dunning, Store  # noqa: E402

DB = "ow_tp_mongodb_205236"; PREFIX = "replay_u9_"
m = MongoClient(os.environ["MONGODB_ATLAS_URI"]); db = m[DB]
ora = oracledb.connect(user="ow_billing", password="ow_billing", dsn="localhost:52521/FREEPDB1"); cur = ora.cursor()
store = Store(m, DB, PREFIX)
res = []; T0 = time.time()
MON = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def probe(group, name, ok, detail=""):
    res.append({"group": group, "probe": name, "ok": bool(ok), "detail": str(detail)[:800]})
    print(("ok  " if ok else "FAIL"), f"[{group}]", name, "|", str(detail)[:220])


def q(sql, **kw):
    cur.execute(sql, kw); cols = [c[0].lower() for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def md5uuid(s):
    h = hashlib.md5(s.encode()).hexdigest(); return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


def dec(v):
    if v is None: return None
    if isinstance(v, Decimal128): v = v.to_decimal()
    return format(Decimal(str(v)).normalize(), "f")


def fp(spec):
    d_, c = spec.split(".") if "." in spec else (DB, spec); h = hashlib.sha256(); n = 0
    for d in m[d_][c].find({}, sort=[("_id", 1)]):
        h.update(dumps(d, json_options=CANONICAL_JSON_OPTIONS, sort_keys=True).encode()); h.update(b"\n"); n += 1
    return n, h.hexdigest()


def idx(coll):
    return sorted((tuple(v["key"]), v.get("unique", False)) for k, v in db[coll].index_information().items())


# ---------- 1. clone baseline vs golden ----------
CLONED = ["billing_invoices", "tenants", "subscriptions", "subscriptions_history", "dunning_attempts", "notifications", "billing_audit_log"]
bad = [c for c in CLONED if fp(c) != fp(PREFIX + c)]
probe("baseline", "7 clone collections canonical-sha-equal to golden", not bad, bad)
bad = [c for c in CLONED if idx(c) != idx(PREFIX + c)]
probe("baseline", "index specs equal golden; dunning_attempts has unique (invoice_id, attempt_no) [UQ_DUNNING_ATTEMPTS]", not bad and ((("invoice_id", 1), ("attempt_no", 1)), True) in idx(PREFIX + "dunning_attempts"), (bad, idx(PREFIX + "dunning_attempts")))
probe("baseline", "notifications unique index mirrors UQ_NOTIFICATIONS", any(u for k, u in idx(PREFIX + "notifications") if k != (("_id", 1),)), idx(PREFIX + "notifications"))
ctr = {d["_id"]: d for d in db[PREFIX + "counters"].find()}
seqs = {r["sequence_name"]: r["last_number"] for r in q("select sequence_name, last_number from user_sequences")}
probe("baseline", "counters seeded U6-shape {_id:seq_billing_audit_log|seq_subscriptions_hist, seq, ns}; seq == max(log_id)/max(hist_id) == Oracle last_number-1",
      set(ctr) == {"seq_billing_audit_log", "seq_subscriptions_hist"} and ctr["seq_billing_audit_log"]["seq"] == seqs["SEQ_BILLING_AUDIT_LOG"] - 1 == db[PREFIX + "billing_audit_log"].find_one(sort=[("log_id", -1)])["log_id"]
      and ctr["seq_subscriptions_hist"]["seq"] == seqs["SEQ_SUBSCRIPTIONS_HIST"] - 1 == 0 and all(isinstance(d["seq"], Int64) for d in ctr.values()), (ctr, seqs))
probe("baseline", "no stray replay_u9 collections", sorted(c for c in db.list_collection_names() if c.startswith(PREFIX)) == sorted(PREFIX + c for c in CLONED + ["counters"]))

# ---------- 2. nulls / dupes / boundaries / distributions ----------
for tbl, coll, cols in (("dunning_attempts", "dunning_attempts", ["scheduled_for", "status_cd", "attempt_no"]), ("notifications", "notifications", ["sent_at", "kind_cd"]),
                        ("tenants", "tenants", ["status_cd", "name"]), ("subscriptions", "subscriptions", ["ends_on", "suspended_on", "status_cd"])):
    sn = {c: q(f"select count(*) n from {tbl} where {c} is null")[0]["n"] for c in cols}
    tn = {c: db[PREFIX + coll].count_documents({"$or": [{c: None}, {c: {"$exists": False}}]}) for c in cols}
    probe("nulls", f"{coll}: NULL counts per field source==target", sn == tn, (sn, tn))
    dup = list(db[PREFIX + coll].aggregate([{"$group": {"_id": "$id", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}]))
    probe("dupes", f"{coll}: no duplicate business id, _id==id", not dup and db[PREFIX + coll].count_documents({"$expr": {"$ne": ["$_id", "$id"]}}) == 0, dup)
for tbl, coll, col in (("tenants", "tenants", "status_cd"), ("subscriptions", "subscriptions", "status_cd"), ("invoices", "billing_invoices", "status_cd"), ("dunning_attempts", "dunning_attempts", "status_cd"), ("notifications", "notifications", "kind_cd")):
    s = {int(r[col]): r["n"] for r in q(f"select {col}, count(*) n from {tbl} group by {col}")}
    t = {r["_id"]: r["n"] for r in db[PREFIX + coll].aggregate([{"$group": {"_id": f"${col}", "n": {"$sum": 1}}}])}
    probe("dist", f"{coll}.{col} distribution source==target", s == t, s)
sd = q("select to_char(min(scheduled_for),'YYYY-MM-DD') mn, to_char(max(scheduled_for),'YYYY-MM-DD') mx, min(attempt_no) a, max(attempt_no) b from dunning_attempts")[0]
td = list(db[PREFIX + "dunning_attempts"].aggregate([{"$group": {"_id": None, "mn": {"$min": "$scheduled_for"}, "mx": {"$max": "$scheduled_for"}, "a": {"$min": "$attempt_no"}, "b": {"$max": "$attempt_no"}}}]))[0]
probe("boundary", "dunning_attempts min/max scheduled_for & attempt_no source==target", (sd["mn"], sd["mx"], sd["a"], sd["b"]) == (td["mn"].strftime("%Y-%m-%d"), td["mx"].strftime("%Y-%m-%d"), td["a"], td["b"]), (sd, td))
sn_ = q("select to_char(sent_at,'YYYY-MM-DD HH24:MI:SS.FF6') s from notifications")[0]["s"]; tn_ = db[PREFIX + "notifications"].find_one()["sent_at"]
probe("boundary", "notifications.sent_at preserves the 09:00 time-of-day (TIMESTAMP(6) -> BSON date)", sn_ == tn_.strftime("%Y-%m-%d %H:%M:%S.%f"), (sn_, tn_))
probe("types", "dunning_attempts/notifications fields typed: attempt_no/status_cd/kind_cd int, dates BSON date, tenant_id refs exist in tenants",
      all(isinstance(d["attempt_no"], int) and isinstance(d["status_cd"], int) and isinstance(d["scheduled_for"], datetime) and db[PREFIX + "tenants"].count_documents({"_id": d["tenant_id"]}) == 1
          and db[PREFIX + "billing_invoices"].count_documents({"_id": d["invoice_id"]}) == 1 for d in db[PREFIX + "dunning_attempts"].find())
      and all(isinstance(d["kind_cd"], int) and isinstance(d["sent_at"], datetime) and db[PREFIX + "tenants"].count_documents({"_id": d["tenant_id"]}) == 1 for d in db[PREFIX + "notifications"].find()))

# ---------- 3. fn_overdue_accounts parity (SQL re-expression, many as_of incl. boundaries; clone == source at baseline) ----------
SQL_OVERDUE = """select i.tenant_id, i.id invoice_id, i.total, trunc(:d) - trunc(cast(i.issued_at as date)) days_overdue,
  decode(t.status_cd, 10, 'active', 20, 'suspended', 'UNKNOWN') tenant_status
  from invoices i, tenants t where t.id (+) = i.tenant_id and i.status_cd = 40 and to_char(i.issued_at,'YYYYMMDD') < to_char(:d,'YYYYMMDD') order by i.issued_at, i.id"""
AS_OF = [datetime(2026, 2, 1), datetime(2026, 2, 1, 23, 59, 59), datetime(2026, 2, 2), datetime(2026, 2, 13), datetime(2026, 2, 14), datetime(2026, 2, 14, 0, 0, 1), datetime(2026, 2, 15), datetime(2026, 2, 28),
         datetime(2026, 3, 1), datetime(2026, 3, 15, 13, 45), datetime(2026, 4, 30), datetime(2025, 1, 1), datetime(2027, 1, 1), datetime(2026, 2, 27), datetime(2026, 3, 13), datetime(2026, 3, 14)]
mism = []
for d in AS_OF:
    s = [(r["tenant_id"], r["invoice_id"], dec(r["total"]), int(r["days_overdue"]), r["tenant_status"]) for r in q(SQL_OVERDUE, d=d)]
    p = [(r["tenant_id"], r["invoice_id"], dec(r["total"]), r["days_overdue"], r["tenant_status"]) for r in dunning.fn_overdue_accounts(store, d)]
    if s != p: mism.append((str(d), s, p))
probe("parity", f"fn_overdue_accounts == PL/SQL SQL on {len(AS_OF)} as_of values (day-string boundary, time-of-day, far past/future), all cols incl. days_overdue & DECODE status", not mism, mism[:2])
# adversarial: tenant missing (outer join) and unknown status -> mutate clone
db[PREFIX + "billing_invoices"].update_one({"_id": "60000000-0000-0000-0000-000000000001"}, {"$set": {"tenant_id": "ffffffff-0000-0000-0000-00000000dead"}})
db[PREFIX + "tenants"].update_one({"_id": "00000000-0000-0000-0000-000000000005"}, {"$set": {"status_cd": 30}})
rows = dunning.fn_overdue_accounts(store, datetime(2026, 3, 1))
probe("parity", "outer-join semantics: invoice whose tenant is missing still listed with tenant_status UNKNOWN; tenant status 30 -> UNKNOWN (DECODE default)",
      [r["tenant_status"] for r in rows] == ["UNKNOWN", "UNKNOWN"] and rows[0]["tenant_id"].startswith("ffffffff"), rows)
db[PREFIX + "billing_invoices"].update_one({"_id": "60000000-0000-0000-0000-000000000001"}, {"$set": {"tenant_id": "00000000-0000-0000-0000-000000000002"}})
db[PREFIX + "tenants"].update_one({"_id": "00000000-0000-0000-0000-000000000005"}, {"$set": {"status_cd": 10}})
probe("parity", "empty result: as_of before every issued_at -> [] (no exception)", dunning.fn_overdue_accounts(store, date(2020, 1, 1)) == [])
probe("parity", "date (not datetime) input accepted and equals midnight datetime", dunning.fn_overdue_accounts(store, date(2026, 3, 1)) == dunning.fn_overdue_accounts(store, datetime(2026, 3, 1)))

# ---------- 4. sp_schedule_dunning: simulate PL/SQL from clone state, run, compare (cumulative, several as_of incl. SAT/SUN) ----------
def sim_schedule(as_of):
    day = datetime(as_of.year, as_of.month, as_of.day); dow = day.strftime("%a").upper()
    nxt = day + timedelta(days={"SAT": 2, "SUN": 1}.get(dow, 0))
    out = []
    for inv in db[PREFIX + "billing_invoices"].find({"status_cd": 40}).sort([("issued_at", 1), ("_id", 1)]):
        prior = db[PREFIX + "dunning_attempts"].find_one({"invoice_id": inv["_id"]}, sort=[("attempt_no", -1)])
        n = (prior["attempt_no"] if prior else 0) + 1
        out.append({"_id": md5uuid(inv["_id"] + str(n)), "id": md5uuid(inv["_id"] + str(n)), "tenant_id": inv["tenant_id"], "invoice_id": inv["_id"], "attempt_no": n, "scheduled_for": nxt, "status_cd": 10, "ns": "mongo_205236"})
    return out, f"scheduled {len(out)} attempts as of {day.day:02d}-{MON[day.month - 1]}-{day.year % 100:02d}"


def run_schedule(label, as_of):
    exp, msg = sim_schedule(as_of); before = {d["_id"] for d in db[PREFIX + "dunning_attempts"].find({}, {"_id": 1})}; la = db[PREFIX + "billing_audit_log"].count_documents({})
    n = dunning.sp_schedule_dunning(store, as_of)
    new = list(db[PREFIX + "dunning_attempts"].find({"_id": {"$nin": list(before)}}).sort("attempt_no", 1))
    got = sorted(({k: v for k, v in d.items()} for d in new), key=lambda d: d["_id"]); exp_s = sorted(exp, key=lambda d: d["_id"])
    log = db[PREFIX + "billing_audit_log"].find_one(sort=[("log_id", -1)])
    probe("schedule", f"{label}: inserted attempts (id=md5(invoice||attempt_no), attempt_no=max+1, scheduled_for weekend-shifted, status 10, ns) == simulation; return {n}=={len(exp)}",
          got == exp_s and n == len(exp), (got, exp_s))
    probe("schedule", f"{label}: exactly one DUNNING audit row '{msg}' (TO_CHAR DD-MON-YY), log_id == counter.seq",
          db[PREFIX + "billing_audit_log"].count_documents({}) == la + 1 and log["module"] == "DUNNING" and log["message"] == msg and log["log_id"] == db[PREFIX + "counters"].find_one({"_id": "seq_billing_audit_log"})["seq"], (log["message"], msg))


run_schedule("DUNNING-002-like weekday 2026-03-02 (Mon): 60..02 gets attempt 2 (fixture attempt 1 exists), 60..01 gets attempt 1", datetime(2026, 3, 2))
run_schedule("same day again -> attempt_no increments (no dedupe by day), 2 more rows", datetime(2026, 3, 2, 15, 30))
run_schedule("Saturday 2026-03-07 -> scheduled_for Monday 03-09", date(2026, 3, 7))
run_schedule("Sunday 2026-03-08 -> scheduled_for Monday 03-09", date(2026, 3, 8))
run_schedule("Friday 2026-03-06 -> no shift", date(2026, 3, 6))
run_schedule("as_of before any invoice (2020-01-01): status filter only, still schedules both overdue invoices", date(2020, 1, 1))
# duplicate-key swallow path (WHEN OTHERS THEN NULL): plant an attempt at max+1 with a foreign _id so the port's insert hits UQ (invoice_id,attempt_no)
mx = db[PREFIX + "dunning_attempts"].find_one({"invoice_id": "60000000-0000-0000-0000-000000000001"}, sort=[("attempt_no", -1)])["attempt_no"]
db[PREFIX + "dunning_attempts"].insert_one({"_id": "planted-dup", "id": "planted-dup", "tenant_id": "x", "invoice_id": "60000000-0000-0000-0000-000000000001", "attempt_no": mx + 1, "scheduled_for": datetime(2026, 1, 1), "status_cd": 10, "ns": "mongo_205236"})
# make the port compute attempt mx+1 anyway: temporarily hide the planted row from its max() by giving it attempt_no lookup collision -> instead plant an _id collision:
db[PREFIX + "dunning_attempts"].delete_one({"_id": "planted-dup"})
db[PREFIX + "dunning_attempts"].insert_one({"_id": md5uuid("60000000-0000-0000-0000-000000000001" + str(mx + 1)), "id": "planted-dup", "tenant_id": "x", "invoice_id": "other", "attempt_no": 99, "scheduled_for": datetime(2026, 1, 1), "status_cd": 10, "ns": "mongo_205236"})
la = db[PREFIX + "billing_audit_log"].count_documents({}); n = dunning.sp_schedule_dunning(store, date(2026, 3, 10))
probe("schedule", "WHEN OTHERS THEN NULL path: PK collision on one invoice's attempt is swallowed, the other invoice is still scheduled, count excludes the swallowed one (1), log still written",
      n == 1 and db[PREFIX + "billing_audit_log"].count_documents({}) == la + 1 and db[PREFIX + "billing_audit_log"].find_one(sort=[("log_id", -1)])["message"].startswith("scheduled 1 attempts"), n)
db[PREFIX + "dunning_attempts"].delete_one({"id": "planted-dup"})
db[PREFIX + "billing_invoices"].update_many({}, {"$set": {"status_cd": 20}})
la = db[PREFIX + "billing_audit_log"].count_documents({}); n = dunning.sp_schedule_dunning(store, date(2026, 3, 10))
probe("schedule", "empty-set behaviour: no status-40 invoices -> 0 scheduled, 'scheduled 0 attempts as of 10-MAR-26' still logged", n == 0 and db[PREFIX + "billing_audit_log"].find_one(sort=[("log_id", -1)])["message"] == "scheduled 0 attempts as of 10-MAR-26")
db[PREFIX + "billing_invoices"].update_one({"_id": "60000000-0000-0000-0000-000000000001"}, {"$set": {"status_cd": 40}})
db[PREFIX + "billing_invoices"].update_one({"_id": "60000000-0000-0000-0000-000000000002"}, {"$set": {"status_cd": 40}})
dl = list(db[PREFIX + "dunning_attempts"].aggregate([{"$group": {"_id": {"i": "$invoice_id", "n": "$attempt_no"}, "c": {"$sum": 1}}}, {"$match": {"c": {"$gt": 1}}}]))
probe("post", "after all scheduling: (invoice_id, attempt_no) unique, attempt_no contiguous 1..k per invoice, _id==id",
      not dl and all([d["attempt_no"] for d in db[PREFIX + "dunning_attempts"].find({"invoice_id": i}).sort("attempt_no", 1)] == list(range(1, db[PREFIX + "dunning_attempts"].count_documents({"invoice_id": i}) + 1))
                     for i in ("60000000-0000-0000-0000-000000000001", "60000000-0000-0000-0000-000000000002")) and db[PREFIX + "dunning_attempts"].count_documents({"$expr": {"$ne": ["$_id", "$id"]}}) == 0, dl)

# ---------- 5. sp_suspend_overdue: simulate PL/SQL, run, compare ----------
def sim_suspend(as_of):
    day = datetime(as_of.year, as_of.month, as_of.day); cutoff = (day - timedelta(days=14)).strftime("%Y%m%d")
    tids = sorted({d["tenant_id"] for d in db[PREFIX + "billing_invoices"].find({"status_cd": 40}) if d["issued_at"].strftime("%Y%m%d") <= cutoff})
    plan = {}
    for t in tids:
        if db[PREFIX + "tenants"].count_documents({"_id": t, "status_cd": 10}) == 0: continue
        subs = list(db[PREFIX + "subscriptions"].find({"tenant_id": t, "status_cd": 10}).sort("_id", 1))
        notif_exists = db[PREFIX + "notifications"].count_documents({"tenant_id": t, "kind_cd": 3, "sent_at": day}) > 0
        plan[t] = {"subs": subs, "notif": None if notif_exists else md5uuid(f"{t}suspension{day:%Y-%m-%d}"), "day": day}
    return tids, plan


def run_suspend(label, as_of):
    tids, plan = sim_suspend(as_of); la = db[PREFIX + "billing_audit_log"].count_documents({}); hb = db[PREFIX + "subscriptions_history"].count_documents({})
    untouched_subs = {d["_id"]: d for d in db[PREFIX + "subscriptions"].find({"status_cd": {"$ne": 10}})}
    hist_seq_before = db[PREFIX + "counters"].find_one({"_id": "seq_subscriptions_hist"})["seq"]
    out = dunning.sp_suspend_overdue(store, as_of)
    probe("suspend", f"{label}: returned suspended tenants == PL/SQL candidates with status 10 {sorted(plan)} (candidates {tids})", sorted(out) == sorted(plan), out)
    ok = True; det = []
    for t, p in plan.items():
        ten = db[PREFIX + "tenants"].find_one({"_id": t}); ok &= ten["status_cd"] == 20
        for s in p["subs"]:
            now = db[PREFIX + "subscriptions"].find_one({"_id": s["_id"]}); ok &= now["status_cd"] == 20 and now["suspended_on"] == p["day"]
            h = db[PREFIX + "subscriptions_history"].find_one({"id": s["_id"], "hist_op": "UPD"}, sort=[("hist_id", -1)])
            good_h = h is not None and h["status_cd"] == 10 and h.get("suspended_on") == s.get("suspended_on") and h["plan_id"] == s["plan_id"] and h["tenant_id"] == t and h["starts_on"] == s["starts_on"] \
                and h.get("ends_on") == s.get("ends_on") and h["_id"] == h["hist_id"] and isinstance(h["hist_id"], Int64) and len(h["hist_dt"]) == 18 and h["hist_dt"][3:6] in MON and h["ns"] == "mongo_205236"
            ok &= good_h; det.append((t, s["_id"], h))
        if p["notif"]:
            n = db[PREFIX + "notifications"].find_one({"_id": p["notif"]}); ok &= n is not None and n["kind_cd"] == 3 and n["sent_at"] == p["day"] and n["tenant_id"] == t and n["id"] == p["notif"] and n["ns"] == "mongo_205236"
    probe("suspend", f"{label}: tenants->20, ACTIVE subs->20 with suspended_on=TRUNC(as_of), trg_subscriptions_hist rows (OLD image, UPD, hist_dt 'DD-MON-YY HH24:MI:SS', seq id), notification id=md5(tenant||'suspension'||YYYY-MM-DD) sent_at=TRUNC(as_of) kind 3", ok, det[:2])
    probe("suspend", f"{label}: non-active subscriptions (20/30) untouched; history rows added == suspended active subs ({sum(len(p['subs']) for p in plan.values())}); hist counter advanced by same",
          all(db[PREFIX + "subscriptions"].find_one({"_id": k}) == v for k, v in untouched_subs.items()) and db[PREFIX + "subscriptions_history"].count_documents({}) - hb == sum(len(p["subs"]) for p in plan.values())
          == db[PREFIX + "counters"].find_one({"_id": "seq_subscriptions_hist"})["seq"] - hist_seq_before)
    logs = [d["message"] for d in db[PREFIX + "billing_audit_log"].find({"log_id": {"$gt": la}}).sort("log_id", 1)]
    probe("suspend", f"{label}: one 'suspended tenant=<id>' DUNNING audit row per suspended tenant, nothing else", logs == [f"suspended tenant={t}" for t in out], logs)


# fixture baseline: only tenant 5 (invoice 60..02 issued 02-13) and tenant 2 (60..01 issued 02-01, tenant already suspended)
run_suspend("as_of 2026-02-26 (cutoff 02-12): 60..01 qualifies but tenant 2 already suspended -> nothing", date(2026, 2, 26))
run_suspend("as_of 2026-02-27 (cutoff 02-13 == issued_at, <= boundary): tenant 5 suspended, tenant 2 skipped", datetime(2026, 2, 27, 18, 0))
run_suspend("rerun same as_of: idempotent (tenant 5 now 20), no dupe notification/history", datetime(2026, 2, 27))
# re-activate tenant 5 in clone & add a second active sub + a cancelled sub to test multi-sub + status-30 immunity
db[PREFIX + "tenants"].update_one({"_id": "00000000-0000-0000-0000-000000000005"}, {"$set": {"status_cd": 10}})
base = db[PREFIX + "subscriptions"].find_one({"_id": "20000000-0000-0000-0000-000000000005"})
for sid, st in (("probe-sub-active", 10), ("probe-sub-cancelled", 30)):
    d = dict(base); d["_id"] = d["id"] = sid; d["status_cd"] = st; d.pop("suspended_on", None); db[PREFIX + "subscriptions"].insert_one(d)
db[PREFIX + "subscriptions"].update_one({"_id": "20000000-0000-0000-0000-000000000005"}, {"$set": {"status_cd": 10}, "$unset": {"suspended_on": ""}})
run_suspend("tenant 5 re-activated with 2 active + 1 cancelled sub, as_of 2026-03-01: both active suspended, cancelled untouched, notification for 03-01 new; 02-27 notification kept", date(2026, 3, 1))
run_suspend("as_of 2026-02-14 (cutoff 01-31 < all issued_at): no candidates -> [] and no writes", date(2026, 2, 14))
probe("suspend", "notifications now: fixture 90..01 + 2 suspension rows (02-27, 03-01) for tenant 5; each (tenant, kind, sent_at) unique",
      db[PREFIX + "notifications"].count_documents({}) == 3 and db[PREFIX + "notifications"].count_documents({"tenant_id": "00000000-0000-0000-0000-000000000005", "kind_cd": 3}) == 2)
ids = [d["log_id"] for d in db[PREFIX + "billing_audit_log"].find(sort=[("log_id", 1)])]
probe("post", "billing_audit_log log_ids contiguous from 1, _id==log_id, module DUNNING for all new rows", ids == list(range(1, len(ids) + 1)) and db[PREFIX + "billing_audit_log"].count_documents({"$expr": {"$ne": ["$_id", "$log_id"]}}) == 0
      and db[PREFIX + "billing_audit_log"].count_documents({"log_id": {"$gt": 1}, "module": {"$ne": "DUNNING"}}) == 0, (ids[0], ids[-1]))

# ---------- 6. golden / quarantine / source untouched ----------
pre = json.load(open(os.path.expanduser("~/wave_recon/w3/golden_pre_fingerprint.json")))
bad = [k for k, v in pre.items() if (v["n"], v["sha256"]) != fp(k)]
probe("golden", f"golden + quarantine collections byte-identical to the wave-3 pre-fingerprint ({len(pre)} collections)", not bad, bad)
qs = {c: m[DB + "_quarantine"][c].count_documents({}) for c in m[DB + "_quarantine"].list_collection_names()}
probe("golden", "quarantine SETS == {bad_csv_list:31, dirty_signup_dt:50, invoice_feed_orphan_lines:37, orphan_document_snapshots:6}; U9 declares none", qs == {"bad_csv_list": 31, "dirty_signup_dt": 50, "invoice_feed_orphan_lines": 37, "orphan_document_snapshots": 6}, qs)
src = q("select (select count(*) from dunning_attempts) d, (select count(*) from notifications) n, (select count(*) from subscriptions_hist) h, (select count(*) from billing_audit_log) a, (select count(*) from tenants where status_cd=20) ts, (select to_char(initialized_at,'YYYY-MM-DD HH24:MI:SS.FF6') from fixture_meta) fm from dual")[0]
probe("golden", "Oracle source untouched: DUNNING_ATTEMPTS 1, NOTIFICATIONS 1, SUBSCRIPTIONS_HIST 0, BILLING_AUDIT_LOG 1, suspended tenants 1, FIXTURE_META unchanged", (src["d"], src["n"], src["h"], src["a"], src["ts"]) == (1, 1, 0, 1, 1) and src["fm"] == "2026-09-01 20:53:10.961888", src)

ok = sum(r["ok"] for r in res)
print(f"\n{ok}/{len(res)} ok in {time.time() - T0:.1f}s")
json.dump({"ok": ok, "total": len(res), "seconds": round(time.time() - T0, 1), "probes": res}, open(os.path.expanduser("~/wave_recon/w3/U9/probes.json"), "w"), indent=1)
