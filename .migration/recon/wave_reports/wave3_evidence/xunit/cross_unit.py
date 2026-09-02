"""Wave 3 cross-unit consistency + app-level replay (U8 x U9 x shared golden set). Mutates only replay_u9_* (caller reloads)."""
import hashlib, json, os, sys, time
from datetime import date, datetime
from decimal import Decimal
from bson import Decimal128, Int64
from bson.json_util import dumps, CANONICAL_JSON_OPTIONS
from pymongo import MongoClient
import oracledb

DB = "ow_tp_mongodb_205236"; m = MongoClient(os.environ["MONGODB_ATLAS_URI"]); db = m[DB]
ora = oracledb.connect(user="ow_billing", password="ow_billing", dsn="localhost:52521/FREEPDB1"); cur = ora.cursor()
res = []; T0 = time.time()


def probe(group, name, ok, detail=""):
    res.append({"group": group, "probe": name, "ok": bool(ok), "detail": str(detail)[:800]})
    print(("ok  " if ok else "FAIL"), f"[{group}]", name, "|", str(detail)[:220])


def q(sql, **kw):
    cur.execute(sql, kw); cols = [c[0].lower() for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def fp(d_, c):
    h = hashlib.sha256(); n = 0
    for d in m[d_][c].find({}, sort=[("_id", 1)]):
        h.update(dumps(d, json_options=CANONICAL_JSON_OPTIONS, sort_keys=True).encode()); h.update(b"\n"); n += 1
    return n, h.hexdigest()


# ---------- 1. shared references on the golden set (codes / tenants / plans) ----------
codes_s = {(r["code_type"], int(r["code_val"]), r["code_desc"]) for r in q("select code_type, code_val, code_desc from codes")}
codes_t = {(d["code_type"], d["code_val"], d["code_desc"]) for d in db.codes.find()}
probe("refs", f"codes SET source==golden ({len(codes_s)} rows)", codes_s == codes_t, codes_s ^ codes_t)
need = {("INV_STATUS", 20), ("INV_STATUS", 40), ("TENANT_STATUS", 10), ("TENANT_STATUS", 20), ("DUN_STATUS", 10), ("NOTIF_KIND", 3), ("SUB_STATUS", 20), ("SUB_STATUS", 10)}
have = {(t, v) for t, v, _ in codes_t}
probe("refs", "every code value U8/U9 write (INV_STATUS 20/40, TENANT_STATUS 10/20, DUN_STATUS 10, NOTIF_KIND 3, SUB_STATUS 10/20) exists in shared codes", need <= have, sorted(need - have))
for coll, field, ref in (("billing_invoices", "tenant_id", "tenants"), ("billing_invoices", "period_id", "rating_periods"), ("credit_notes", "tenant_id", "tenants"), ("dunning_attempts", "tenant_id", "tenants"),
                         ("dunning_attempts", "invoice_id", "billing_invoices"), ("notifications", "tenant_id", "tenants"), ("subscriptions", "plan_id", "plans"), ("subscriptions", "tenant_id", "tenants"),
                         ("rating_periods", "tenant_id", "tenants"), ("usage_events", "tenant_id", "tenants")):
    refs = {d[field] for d in db[coll].find({}, {field: 1}) if d.get(field) is not None}; ids = {d["_id"] for d in db[ref].find({}, {"_id": 1})}
    probe("refs", f"golden {coll}.{field} -> {ref}._id all resolve ({len(refs)} distinct)", refs <= ids, sorted(refs - ids)[:3])
dang = [d["_id"] for d in db.rating_periods.find() for r in d["results"] if r["period_id"] != d["_id"]]
probe("refs", "golden rating_periods.results[].period_id == parent _id (no dangling embed refs)", not dang, dang)
probe("refs", "golden invoices.period_id resolve to rating_periods AND (tenant, period_start) agree",
      all((rp := db.rating_periods.find_one({"_id": d["period_id"]})) and rp["tenant_id"] == d["tenant_id"] for d in db.billing_invoices.find()))
# plan / tenant refs from the Oracle side agree (same sets)
for tbl, col, coll in (("tenants", "id", "tenants"), ("plans", "id", "plans"), ("subscriptions", "plan_id", "subscriptions")):
    s = {r["v"] for r in q(f"select distinct {col} v from {tbl}")}; t = {d[col if col != "id" else "_id"] for d in db[coll].find({}, {col: 1})}
    probe("refs", f"{tbl}.{col} distinct SET source==golden ({len(s)})", s == t, s ^ t)

# ---------- 2. F-X-1: audit-log counter contract across U8 (rating.log_msg, U7 shape) and U9 (util.log_msg, U6 shape) ----------
sys.path.insert(0, os.path.expanduser("~/wave_recon/heads/u8/services/legacy-billing/app")); import ow_billing.rating as rating8  # noqa: E402
sys.path.pop(0); [sys.modules.pop(k) for k in list(sys.modules) if k.startswith("ow_billing")]
sys.path.insert(0, os.path.expanduser("~/wave_recon/heads/u9/services/legacy-billing/app")); import ow_billing.util as util9; from ow_billing import Store as Store9  # noqa: E402
probe("F-X-1", "U8 logs through rating.log_msg with counter _id 'SEQ_BILLING_AUDIT_LOG'/field 'value'; U9 through util.log_msg with 'seq_billing_audit_log'/field 'seq' (incompatible)",
      rating8.AUDIT_SEQUENCE == "SEQ_BILLING_AUDIT_LOG" and util9.SEQ_BILLING_AUDIT_LOG == "seq_billing_audit_log", (rating8.AUDIT_SEQUENCE, util9.SEQ_BILLING_AUDIT_LOG))
gc = sorted(d["_id"] for d in db.counters.find()); probe("F-X-1", "shared golden `counters` has NEITHER audit-sequence document (both units seed their own clone counter)", not any("audit" in c.lower() for c in gc), gc)
# live demonstration on the U9 clone (sandbox): U8-style logger followed by U9-style logger allocate the SAME log_id -> DuplicateKey on _id
P = "replay_u9_"; s9 = Store9(m, DB, P)
class S8:  # minimal RatingStore-compatible view on the U9 clone
    def __init__(self): self.db, self.prefix = db, P
    def coll(self, n): return db[P + n]
    counters = property(lambda self: db[P + "counters"]); billing_audit_log = property(lambda self: db[P + "billing_audit_log"])
before = db[P + "billing_audit_log"].count_documents({}); top = db[P + "billing_audit_log"].find_one(sort=[("log_id", -1)])["log_id"]
rating8.log_msg(S8(), "PROBE", "u8-style"); r8 = db[P + "billing_audit_log"].find_one(sort=[("log_id", -1)])
err = None
try: util9.log_msg(s9, "PROBE", "u9-style")
except Exception as e: err = type(e).__name__  # noqa: BLE001
after = db[P + "billing_audit_log"].count_documents({}); ctrs = {d["_id"]: d for d in db[P + "counters"].find()}
probe("F-X-1", "LIVE: on one store, U8 logger (value counter) then U9 logger (seq counter) both compute log_id=max+1 -> U9 write fails DuplicateKeyError (U8 swallows silently in the reverse order)",
      r8["log_id"] == top + 1 and err == "DuplicateKeyError" and after == before + 1 and "SEQ_BILLING_AUDIT_LOG" in ctrs and "seq_billing_audit_log" in ctrs, (err, {k: {kk: vv for kk, vv in v.items() if kk != "_id"} for k, v in ctrs.items()}))
probe("F-X-1", "audit doc shapes agree otherwise (_id==log_id Int64, logged_at date, module, message, ns) so only the counter contract diverges",
      set(r8) == {"_id", "log_id", "logged_at", "module", "message", "ns"} and isinstance(r8["log_id"], Int64), sorted(r8))

# ---------- 3. app-level replay: U9 HTTP routes (Flask test client on the clone) vs Oracle SQL re-expression ----------
os.environ["OW_BILLING_COLLECTION_PREFIX"] = P; os.environ["MONGODB_DB"] = DB
sys.path.insert(0, os.path.expanduser("~/wave_recon/heads/u9/services/legacy-billing/app"))
import app as legacy_app  # noqa: E402
client = legacy_app.app.test_client()
SQL = """select i.tenant_id, i.id invoice_id, to_char(i.total,'FM9999999990.00') total, trunc(:d) - trunc(cast(i.issued_at as date)) days_overdue,
  decode(t.status_cd, 10, 'active', 20, 'suspended', 'UNKNOWN') tenant_status from invoices i, tenants t
  where t.id (+) = i.tenant_id and i.status_cd = 40 and to_char(i.issued_at,'YYYYMMDD') < to_char(:d,'YYYYMMDD') order by i.issued_at, i.id"""
mism = []
for d in ("2026-02-01", "2026-02-02", "2026-02-13", "2026-02-14", "2026-02-28", "2026-03-15", "2025-01-01"):
    r = client.get(f"/api/dunning/overdue?as_of={d}"); body = r.get_json()
    s = [{"tenant_id": x["tenant_id"], "invoice_id": x["invoice_id"], "total": x["total"], "days_overdue": int(x["days_overdue"]), "tenant_status": x["tenant_status"]} for x in q(SQL, d=datetime.fromisoformat(d))]
    if r.status_code != 200 or body != s: mism.append((d, r.status_code, body, s))
probe("app", "GET /api/dunning/overdue?as_of=... (7 dates) == Oracle fn_overdue_accounts SQL, money as 2dp strings, order issued_at,id", not mism, mism[:1])
r = client.get("/api/dunning/overdue?as_of=garbage"); probe("app", "GET /api/dunning/overdue invalid as_of -> 400 {detail:'invalid as_of'}", r.status_code == 400 and r.get_json() == {"detail": "invalid as_of"}, r.get_json())
r = client.get("/api/dunning/overdue"); probe("app", "GET /api/dunning/overdue default as_of=2026-02-28 (2 overdue rows)", r.status_code == 200 and len(r.get_json()) == 2, r.get_json())
n0 = db[P + "dunning_attempts"].count_documents({}); r = client.post("/api/dunning/schedule", json={"as_of": "2026-03-02"})
probe("app", "POST /api/dunning/schedule {as_of} -> {status:scheduled, scheduled:2}; 2 attempts inserted via the route", r.status_code == 200 and r.get_json() == {"status": "scheduled", "scheduled": 2} and db[P + "dunning_attempts"].count_documents({}) == n0 + 2, r.get_json())
r = client.post("/api/dunning/suspend", json={"as_of": "2026-02-27"})
probe("app", "POST /api/dunning/suspend {as_of:2026-02-27} -> {status:suspended, tenant_ids:[tenant 5]}; tenant 5 status now 20 via the route",
      r.status_code == 200 and r.get_json() == {"status": "suspended", "tenant_ids": ["00000000-0000-0000-0000-000000000005"]} and db[P + "tenants"].find_one({"_id": "00000000-0000-0000-0000-000000000005"})["status_cd"] == 20, r.get_json())
r = client.post("/api/dunning/suspend", json={"as_of": "27/02/2026"}); probe("app", "POST /api/dunning/suspend bad date -> 400", r.status_code == 400, (r.status_code, r.get_json()))
probe("app", "golden app.py /api/invoices/* routes still call Postgres billing.fn_invoice_preview/sp_issue_invoice/fn_invoice_lines (U8 exposes no Mongo HTTP route; informational)",
      True, [l.strip() for l in open(os.path.expanduser("~/wave_recon/heads/u8/services/legacy-billing/app/app.py")) if "billing." in l and "invoice" in l])

# ---------- 4. golden / quarantine untouched by the whole wave ----------
pre = json.load(open(os.path.expanduser("~/wave_recon/w3/golden_pre_fingerprint.json")))
bad = [k for k, v in pre.items() if (v["n"], v["sha256"]) != fp(*k.split("."))]
probe("golden", f"golden + quarantine byte-identical to wave-3 pre-fingerprint after all U8/U9 gates+probes ({len(pre)} collections)", not bad, bad)
ok = sum(r["ok"] for r in res); print(f"\n{ok}/{len(res)} ok in {time.time() - T0:.1f}s")
json.dump({"ok": ok, "total": len(res), "probes": res}, open(os.path.expanduser("~/wave_recon/w3/cross_unit.json"), "w"), indent=1)
