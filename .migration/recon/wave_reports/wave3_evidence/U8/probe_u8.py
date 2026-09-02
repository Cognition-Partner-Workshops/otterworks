"""Wave 3 independent adversarial probes for U8 (PKG_INVOICING -> ow_billing.invoicing).
Oracle is observed with PLAIN SQL only (the packages write BILLING_AUDIT_LOG). The clone
replay_u8_* is reloaded by the caller before this script runs; this script mutates ONLY the clone.
Expected values for sp_issue_invoice are produced by an independent re-implementation of the
PL/SQL (SQL re-expression of compute_preview + Python simulation of the burn-down loop)."""
import hashlib, json, os, sys, time
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from bson import Decimal128, Int64
from bson.json_util import dumps, CANONICAL_JSON_OPTIONS
from pymongo import MongoClient
import oracledb

HEAD = os.path.expanduser("~/wave_recon/heads/u8/services/legacy-billing/app")
sys.path.insert(0, HEAD)
from ow_billing import invoicing, rating  # noqa: E402

DB = "ow_tp_mongodb_205236"; PREFIX = "replay_u8_"
m = MongoClient(os.environ["MONGODB_ATLAS_URI"]); db = m[DB]
ora = oracledb.connect(user="ow_billing", password="ow_billing", dsn="localhost:52521/FREEPDB1"); cur = ora.cursor()
store = invoicing.InvoicingStore(db, PREFIX)
res = []; T0 = time.time()


def probe(group, name, ok, detail=""):
    res.append({"group": group, "probe": name, "ok": bool(ok), "detail": str(detail)[:800]})
    print(("ok  " if ok else "FAIL"), f"[{group}]", name, "|", str(detail)[:220])


def q(sql, **kw):
    cur.execute(sql, kw); cols = [c[0].lower() for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def canon(v):
    if v is None: return None
    if isinstance(v, Decimal128): v = v.to_decimal()
    if isinstance(v, (int, float, Decimal)):
        d = Decimal(str(v));
        return str(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) if d == d.to_integral() or True else str(d)
    if isinstance(v, datetime): return v.strftime("%Y-%m-%d %H:%M:%S")
    return str(v)


def exact(v):
    """Exact decimal string (no quantize) for unrounded comparisons."""
    if v is None: return None
    if isinstance(v, Decimal128): v = v.to_decimal()
    return format(Decimal(str(v)).normalize(), "f")


def md5uuid(s):
    h = hashlib.md5(s.encode()).hexdigest(); return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


def fp(coll, ignore_id=False):
    h = hashlib.sha256(); n = 0
    for d in db[coll].find({}, sort=[("_id", 1)]):
        if ignore_id: d.pop("_id", None)
        h.update(dumps(d, json_options=CANONICAL_JSON_OPTIONS, sort_keys=True).encode()); h.update(b"\n"); n += 1
    return n, h.hexdigest()


def idx(coll):
    return sorted((tuple(v["key"]), v.get("unique", False), v.get("expireAfterSeconds")) for k, v in db[coll].index_information().items())


# ---------- 1. clone baseline vs golden ----------
CLONED = ["subscriptions", "subscriptions_history", "usage_events", "rating_periods", "billing_invoices", "credit_notes",
          "dunning_attempts", "notifications", "billing_audit_log", "plans", "tenants"]
bad = [c for c in CLONED if fp(c) != fp(PREFIX + c)]
probe("baseline", "11 clone collections canonical-sha-equal to golden (docs incl. _id)", not bad, bad)
bad = [c for c in CLONED if idx(c) != idx(PREFIX + c)]
probe("baseline", "index specs (keys/unique/TTL) equal golden", not bad, bad)
vs = next(c.get("options", {}).get("validator") for c in db.list_collections(filter={"name": "usage_events"}))
vt = next(c.get("options", {}).get("validator") for c in db.list_collections(filter={"name": PREFIX + "usage_events"}))
probe("baseline", "usage_events $jsonSchema validator cloned", vs == vt and vs is not None, vt)
probe("baseline", "no *__staging / stray replay_u8 collections", sorted(c for c in db.list_collection_names() if c.startswith(PREFIX)) ==
      sorted(PREFIX + c for c in CLONED + ["counters"]), sorted(c for c in db.list_collection_names() if c.startswith(PREFIX)))
ctr = list(db[PREFIX + "counters"].find())
seq = q("select last_number from user_sequences where sequence_name='SEQ_BILLING_AUDIT_LOG'")[0]["last_number"]
mx = db[PREFIX + "billing_audit_log"].find_one(sort=[("log_id", -1)])["log_id"]
probe("baseline", "counter {_id:SEQ_BILLING_AUDIT_LOG,value} == max(log_id) == USER_SEQUENCES.last_number-1 (U7 contract, Int64)",
      len(ctr) == 1 and ctr[0]["_id"] == "SEQ_BILLING_AUDIT_LOG" and ctr[0]["value"] == mx == seq - 1 and isinstance(ctr[0]["value"], Int64), (ctr, mx, seq))

# ---------- 2. null / dup / boundary / embed distribution (clone vs Oracle) ----------
for tbl, coll, cols in (("credit_notes", "credit_notes", ["issued_on", "amount", "remaining_amount"]),
                        ("invoices", "billing_invoices", ["issued_at", "subtotal", "tax", "total", "status_cd", "period_id"]),
                        ("tenants", "tenants", ["tax_exempt_yn", "status_cd", "name"])):
    sn = {c: q(f"select count(*) n from {tbl} where {c} is null")[0]["n"] for c in cols}
    tn = {c: db[PREFIX + coll].count_documents({"$or": [{c: None}, {c: {"$exists": False}}]}) for c in cols}
    probe("nulls", f"{coll}: NULL counts per field source==target", sn == tn, (sn, tn))
    dup = list(db[PREFIX + coll].aggregate([{"$group": {"_id": "$id", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}]))
    probe("dupes", f"{coll}: no duplicate business id, _id==id everywhere", not dup and db[PREFIX + coll].count_documents({"$expr": {"$ne": ["$_id", "$id"]}}) == 0, dup)
ld = {int(r["_id"]): r["n"] for r in db[PREFIX + "billing_invoices"].aggregate([{"$project": {"n": {"$size": "$lines"}}}, {"$group": {"_id": "$n", "n": {"$sum": 1}}}])}
ls = {int(r["k"]): r["n"] for r in q("select k, count(*) n from (select i.id, (select count(*) from invoice_lines l where l.invoice_id = i.id) k from invoices i) group by k")}
probe("embed", "billing_invoices.lines[] length distribution == INVOICE_LINES child rows per header", ld == ls, (ld, ls))
dl = list(db[PREFIX + "billing_invoices"].aggregate([{"$unwind": "$lines"}, {"$group": {"_id": {"i": "$_id", "n": "$lines.line_no"}, "c": {"$sum": 1}}}, {"$match": {"c": {"$gt": 1}}}]))
probe("embed", "lines[] (invoice, line_no) unique (UQ_INVOICE_LINES) and lines[].invoice_id == parent _id", not dl and
      db[PREFIX + "billing_invoices"].count_documents({"$expr": {"$gt": [{"$size": {"$filter": {"input": "$lines", "cond": {"$ne": ["$$this.invoice_id", "$_id"]}}}}, 0]}}) == 0, dl)
sm = q("select to_char(min(issued_at),'YYYY-MM-DD HH24:MI:SS') mn, to_char(max(issued_at),'YYYY-MM-DD HH24:MI:SS') mx, sum(total) st, sum(tax) sx, sum(subtotal) ss from invoices")[0]
tm = list(db[PREFIX + "billing_invoices"].aggregate([{"$group": {"_id": None, "mn": {"$min": "$issued_at"}, "mx": {"$max": "$issued_at"}, "st": {"$sum": "$total"}, "sx": {"$sum": "$tax"}, "ss": {"$sum": "$subtotal"}}}]))[0]
probe("boundary", "billing_invoices min/max issued_at, sum(total/tax/subtotal) source==target",
      (sm["mn"], sm["mx"], canon(sm["st"]), canon(sm["sx"]), canon(sm["ss"])) == (canon(tm["mn"]), canon(tm["mx"]), canon(tm["st"]), canon(tm["sx"]), canon(tm["ss"])), (sm, tm))
sc = q("select sum(remaining_amount) s, min(issued_on) mn, max(issued_on) mx, count(distinct tenant_id) nt, sum(case when remaining_amount>0 then 1 else 0 end) pos from credit_notes")[0]
tc = list(db[PREFIX + "credit_notes"].aggregate([{"$group": {"_id": None, "s": {"$sum": "$remaining_amount"}, "mn": {"$min": "$issued_on"}, "mx": {"$max": "$issued_on"}, "nt": {"$addToSet": "$tenant_id"}, "pos": {"$sum": {"$cond": [{"$gt": ["$remaining_amount", 0]}, 1, 0]}}}}]))[0]
probe("boundary", "credit_notes sum(remaining), min/max issued_on, distinct tenants, positive count source==target",
      (canon(sc["s"]), canon(sc["mn"]), canon(sc["mx"]), sc["nt"], sc["pos"]) == (canon(tc["s"]), canon(tc["mn"]), canon(tc["mx"]), len(tc["nt"]), tc["pos"]), (sc, tc))
sd = {int(r["status_cd"]): r["n"] for r in q("select status_cd, count(*) n from invoices group by status_cd")}
td = {r["_id"]: r["n"] for r in db[PREFIX + "billing_invoices"].aggregate([{"$group": {"_id": "$status_cd", "n": {"$sum": 1}}}])}
probe("dist", "invoices.status_cd distribution source==target (20 issued / 40 overdue; no 10 draft / 30 paid in data -- recorded)", sd == td, sd)
tx = {r["tax_exempt_yn"]: r["n"] for r in q("select tax_exempt_yn, count(*) n from tenants group by tax_exempt_yn")}
tt = {r["_id"]: r["n"] for r in db[PREFIX + "tenants"].aggregate([{"$group": {"_id": "$tax_exempt_yn", "n": {"$sum": 1}}}])}
probe("dist", "tenants.tax_exempt_yn distribution source==target (exempt branch is live in data)", tx == tt and tx.get("Y", 0) > 0, tx)
types_ok = all(isinstance(d["subtotal"], Decimal128) and isinstance(d["tax"], Decimal128) and isinstance(d["total"], Decimal128) and isinstance(d["issued_at"], datetime)
               and all(isinstance(l["amount"], Decimal128) and isinstance(l["line_no"], int) for l in d["lines"]) for d in db[PREFIX + "billing_invoices"].find())
probe("types", "billing_invoices money fields Decimal128, issued_at BSON date, lines.amount Decimal128 / line_no int", types_ok)

# ---------- 3. fn_invoice_preview parity: SQL re-expression of compute_preview vs Python (69 tenants x windows) ----------
SQL_RATE = """
with sub as (
  select * from (select s.id, s.status_cd, s.suspended_on, s.plan_id from subscriptions s
                 where s.tenant_id = :t and s.starts_on <= :pe and (s.ends_on is null or s.ends_on >= :ps)
                 order by s.starts_on desc) where rownum <= 1),
pl as (select p.included_units inc, p.overage_rate rate, p.code, p.monthly_fee fee from plans p, sub where p.id = sub.plan_id),
used as (select nvl(sum(nvl(u.units,0)),0) used from usage_events u where u.tenant_id = :t
          and to_char(u.occurred_at,'YYYYMMDD') >= to_char(:ps,'YYYYMMDD') and to_char(u.occurred_at,'YYYYMMDD') <= to_char(:pe,'YYYYMMDD')),
pri as (select nvl(sum(nvl(rr.rollover_units,0)),0) prior0 from rating_results rr, rating_periods rp
         where rp.id = rr.period_id and rp.tenant_id = :t and rp.period_start < :ps and rp.period_start >= add_months(:ps, -3)),
cr as (select nvl(sum(nvl(remaining_amount,0)),0) credit from credit_notes where tenant_id = :t and remaining_amount > 0),
tn as (select nvl(max(nvl(tax_exempt_yn,'N')),'N') exempt from tenants where id = :t),
a as (select (select inc from pl) inc, (select rate from pl) rate, (select code from pl) code, (select fee from pl) fee, used.used,
             least(nvl(2*(select inc from pl), pri.prior0), pri.prior0) prior1,
             (select status_cd from sub) st, (select suspended_on from sub) susp, cr.credit, tn.exempt from used, pri, cr, tn),
b as (select a.*, greatest(nvl(used - least(prior1, nvl(inc*2, prior1)) - inc, 0), 0) billable from a),
c as (select b.*, round(least(billable,101)*rate + greatest(billable-101,0)*rate*1.5, 2) ov,
             case when st = 20 and susp is not null and susp between :ps and :pe then (:pe - susp + 1)/(:pe - :ps + 1) end factor from b),
d as (select code, fee, credit, exempt, case when factor is not null then round(ov*factor, 2) else ov end overage from c)
select code, fee, overage, credit, exempt, decode(exempt, 'Y', 0, (fee + overage) * 0.0825) tax,
       round(fee + overage + decode(exempt, 'Y', 0, (fee + overage) * 0.0825), 2) cap
from d"""


def ora_preview(t, ps, pe):
    r = q(SQL_RATE, t=t, ps=ps, pe=pe)[0]
    fee, ov, tax, credit, cap = (None if r["fee"] is None else Decimal(str(r["fee"]))), (None if r["overage"] is None else Decimal(str(r["overage"]))), \
        (None if r["tax"] is None else Decimal(str(r["tax"]))), Decimal(str(r["credit"])), (None if r["cap"] is None else Decimal(str(r["cap"])))
    credit_app = min(credit, cap if cap is not None else credit)
    def rnd(x): return None if x is None else x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    half = None if tax is None else tax / 2
    rows = [(1, "plan", r["code"], rnd(fee), Decimal(0), Decimal(0), rnd(fee)),
            (2, "usage", "usage overage", rnd(ov), Decimal(0), Decimal(0), rnd(ov)),
            (3, "tax", "regional tax", half, Decimal(0), Decimal(0), half),
            (4, "tax", "local tax", half, Decimal(0), Decimal(0), half),
            (5, "credit", "credit notes", Decimal(0), Decimal(0), credit_app, -credit_app)]
    return [tuple(exact(x) if isinstance(x, Decimal) else x for x in row) for row in rows], r


def py_preview(t, ps, pe):
    rows = invoicing.fn_invoice_preview(store, t, ps, pe)
    return [tuple(exact(x) if isinstance(x, Decimal) else x for x in (r["line_no"], r["line_type"], r["description"], r["amount"], r["tax_amount"], r["credit_applied"], r["total"])) for r in rows]


tenants = [r["id"] for r in q("select id from tenants order by id")]
WINDOWS = [(date(2026, 2, 1), date(2026, 2, 28)), (date(2026, 1, 1), date(2026, 1, 31)), (date(2026, 3, 1), date(2026, 3, 31)), (date(2026, 2, 15), date(2026, 3, 15))]
mism = []; n_ops = 0; stats = {"no_plan": 0, "exempt": 0, "credit_capped": 0, "credit_full": 0, "nonzero_overage": 0, "odd_half_tax": 0}
for t in tenants + ["ffffffff-0000-0000-0000-000000000000"]:
    for ps, pe in WINDOWS:
        n_ops += 1
        o, raw = ora_preview(t, ps, pe); p = py_preview(t, ps, pe)
        if o != p: mism.append((t, str(ps), o, p))
        if raw["fee"] is None: stats["no_plan"] += 1
        if raw["exempt"] == "Y": stats["exempt"] += 1
        if raw["overage"] not in (None, 0): stats["nonzero_overage"] += 1
        if raw["credit"] > 0 and raw["cap"] is not None and raw["credit"] > raw["cap"]: stats["credit_capped"] += 1
        elif raw["credit"] > 0: stats["credit_full"] += 1
        if raw["tax"] is not None and (Decimal(str(raw["tax"])) / 2).as_tuple().exponent < -2: stats["odd_half_tax"] += 1
probe("parity", f"fn_invoice_preview == PL/SQL re-expression on {n_ops} ops (70 tenants x 4 windows), all 5 rows x 7 cols exact (unrounded tax/2)", not mism, (stats, mism[:3]))

# fn_invoice_lines for every invoice vs INVOICE_LINES
mism = []
for inv in q("select id from invoices order by id") + [{"id": "60000000-0000-0000-0000-00000000dead"}]:
    s = [(int(r["line_no"]), r["line_type"], r["description"], canon(r["amount"])) for r in q("select line_no, line_type, description, amount from invoice_lines where invoice_id=:i order by line_no", i=inv["id"])]
    p = [(r["line_no"], r["line_type"], r["description"], canon(r["amount"])) for r in invoicing.fn_invoice_lines(store, inv["id"])]
    if s != p: mism.append((inv["id"], s, p))
probe("parity", "fn_invoice_lines == INVOICE_LINES for all 3 invoices (incl. 2 with zero lines) + unknown id -> []", not mism, mism)

# ---------- 4. sp_issue_invoice deep checks (clone only; expectation = independent PL/SQL simulation) ----------
def simulate_issue(t, ps, pe, notes_before, existing):
    """Replicates sp_issue_invoice after finalize: totals + burn-down over the given notes (oldest first)."""
    o, raw = ora_preview(t, ps, pe)
    fee = None if raw["fee"] is None else Decimal(str(raw["fee"])); ov = None if raw["overage"] is None else Decimal(str(raw["overage"]))
    tax = None if raw["tax"] is None else Decimal(str(raw["tax"])); cap = None if raw["cap"] is None else Decimal(str(raw["cap"]))
    credit = sum((n["remaining"] for n in notes_before if n["remaining"] > 0), Decimal(0))
    credit_app = min(credit, cap if cap is not None else credit)
    def rnd(x): return None if x is None else x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if fee is None or ov is None or tax is None: return {"error": "ORA-01400 (NULL line description/amount)"}
    subtotal = rnd(fee) + rnd(ov); vtax = rnd(tax / 2) + rnd(tax / 2); total = rnd(subtotal + vtax - credit_app)
    period_id = md5uuid(f"{t}{ps:%Y-%m-%d}"); inv_id = md5uuid(period_id + "invoice")
    lines = [(1, "plan", raw["code"], rnd(fee)), (2, "usage", "usage overage", rnd(ov)), (3, "tax", "regional tax", rnd(tax / 2)),
             (4, "tax", "local tax", rnd(tax / 2)), (5, "credit", "credit notes", rnd(-credit_app))]
    lines = [{"id": md5uuid(inv_id + str(n)), "line_no": n, "line_type": ty, "description": d, "amount": exact(a)} for n, ty, d, a in lines]
    v = credit_app; after = []
    for n in sorted([x for x in notes_before if x["remaining"] > 0], key=lambda x: (x["issued_on"], x["id"])):
        if v <= 0: after.append((n["id"], n["remaining"])); continue
        after.append((n["id"], max(n["remaining"] - v, Decimal(0)))); v = max(v - n["remaining"], Decimal(0))
    after_map = dict(after)
    notes_after = {n["id"]: exact(after_map.get(n["id"], n["remaining"])) for n in notes_before}
    return {"invoice": {"_id": inv_id, "id": inv_id, "tenant_id": existing["tenant_id"] if existing else t, "period_id": existing["period_id"] if existing else period_id,
                        "issued_at": existing["issued_at"] if existing else datetime(pe.year, pe.month, pe.day), "subtotal": exact(subtotal), "tax": exact(vtax), "total": exact(total), "status_cd": 20},
            "lines": lines, "notes_after": notes_after, "credit_app": exact(credit_app), "total_text": None, "total": total}


def notes_now(t):
    return [{"id": d["_id"], "issued_on": d["issued_on"], "remaining": d["remaining_amount"].to_decimal()} for d in db[PREFIX + "credit_notes"].find({"tenant_id": t})]


def ora_to_char(d):
    s = format(d.normalize(), "f")
    if s.startswith("0."): s = s[1:]
    if s.startswith("-0."): s = "-" + s[2:]
    return "0" if s in ("0", "-0") else s


def issue_and_check(label, t, ps, pe):
    notes_before = notes_now(t); existing = db[PREFIX + "billing_invoices"].find_one({"_id": md5uuid(md5uuid(f"{t}{ps:%Y-%m-%d}") + "invoice")})
    exp = simulate_issue(t, ps, pe, notes_before, existing)
    audit_before = db[PREFIX + "billing_audit_log"].count_documents({}); rp_before = db[PREFIX + "rating_periods"].count_documents({})
    err = None
    try:
        invoicing.sp_issue_invoice(store, t, ps, pe)
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {e}"
    if "error" in exp:
        inv = db[PREFIX + "billing_invoices"].find_one({"tenant_id": t, "period_id": md5uuid(f"{t}{ps:%Y-%m-%d}")})
        # Oracle: RATING_RESULTS.SUBSCRIPTION_ID is NOT NULL -> sp_finalize_rating raises ORA-01400 first; port raises RatingIntegrityError (U7) first.
        probe("issue", f"{label}: PL/SQL raises ORA-01400 in sp_finalize_rating (RATING_RESULTS.SUBSCRIPTION_ID NOT NULL) -> port raises RatingIntegrityError, no invoice written, credit notes untouched, no rating-period residue, exactly the one autonomous RATING 'compute' audit row persists (as Oracle's autonomous log_msg would)",
              err is not None and "RatingIntegrityError" in err and inv is None and notes_now(t) == notes_before
              and db[PREFIX + 'rating_periods'].count_documents({}) == rp_before and db[PREFIX + 'billing_audit_log'].count_documents({}) == audit_before + 1
              and db[PREFIX + 'billing_audit_log'].find_one(sort=[("log_id", -1)])["message"].startswith(f"compute tenant={t} "),
              (err, f"rating_periods {rp_before} -> {db[PREFIX + 'rating_periods'].count_documents({})} ; audit +{db[PREFIX + 'billing_audit_log'].count_documents({}) - audit_before}"))
        return
    inv = db[PREFIX + "billing_invoices"].find_one({"_id": exp["invoice"]["_id"]})
    got = {k: (exact(inv[k]) if isinstance(inv.get(k), Decimal128) else inv.get(k)) for k in exp["invoice"]}
    probe("issue", f"{label}: invoice header (id/tenant/period/issued_at/subtotal/tax/total/status) == PL/SQL simulation", err is None and got == exp["invoice"], (err, got, exp["invoice"]))
    gl = [{"id": l["id"], "line_no": l["line_no"], "line_type": l["line_type"], "description": l["description"], "amount": exact(l["amount"])} for l in sorted(inv["lines"], key=lambda l: l["line_no"])]
    probe("issue", f"{label}: 5 lines (ids md5(invoice||line_no), types, descriptions, amounts incl. credit line = -credit_applied, tax halves rounded to NUMBER(12,2)) == simulation", gl == exp["lines"], (gl, exp["lines"]))
    na = {d["_id"]: exact(d["remaining_amount"]) for d in db[PREFIX + "credit_notes"].find({"tenant_id": t})}
    probe("issue", f"{label}: credit-note burn-down (oldest first, GREATEST(remaining - v_credit, 0), running counter quirk) == simulation; credit_app={exp['credit_app']}", na == exp["notes_after"], (na, exp["notes_after"]))
    probe("issue", f"{label}: invoice doc shape: ns, top-level keys exactly as mapped, status int",
          inv.get("ns") == "mongo_205236" and set(inv) == {"_id", "id", "tenant_id", "period_id", "issued_at", "subtotal", "tax", "total", "status_cd", "lines", "ns"}, sorted(inv))
    probe("shape-F-U8-1", f"{label}: rebuilt lines[] elements carry invoice_id (loader-embedded INVOICE_LINES rows do: keys id,invoice_id,line_no,line_type,description,amount)",
          all(set(l) == {"id", "invoice_id", "line_no", "line_type", "description", "amount"} and l["invoice_id"] == inv["_id"] for l in inv["lines"]),
          {"line_keys": sorted(inv["lines"][0]) if inv["lines"] else None})
    log = db[PREFIX + "billing_audit_log"].find_one(sort=[("log_id", -1)])
    probe("issue", f"{label}: exactly one INVOICING audit row 'issued invoice=<id> total=<TO_CHAR(NVL(total,0))>' appended after the RATING rows, log_id sequential",
          log["module"] == "INVOICING" and log["message"] == f"issued invoice={exp['invoice']['_id']} total={ora_to_char(exp['total'])}" and
          db[PREFIX + "billing_audit_log"].count_documents({"module": "INVOICING", "log_id": {"$gt": audit_before}}) == 1 and log["log_id"] == db[PREFIX + "counters"].find_one()["value"],
          (log["message"], f"issued invoice={exp['invoice']['_id']} total={ora_to_char(exp['total'])}"))
    pid = md5uuid(f"{t}{ps:%Y-%m-%d}"); rp = db[PREFIX + "rating_periods"].find_one({"tenant_id": t, "period_start": datetime(ps.year, ps.month, ps.day)})
    if rp is not None and rp["_id"] != pid:
        # fixture-seeded period id != md5(tenant||start): Oracle's sp_finalize_rating would hit ORA-02291 (RATING_RESULTS.PERIOD_ID FK) and
        # sp_issue_invoice would abort with NO invoice; the port appends a dangling results[] element and issues the invoice. Inherited from U7 (F-U7-1).
        probe("F-U8-2", f"{label}: DIVERGENCE (inherited U7 F-U7-1): fixture period {rp['_id']} != md5 {pid}; Oracle -> ORA-02291, no invoice. Port issued invoice with period_id={inv['period_id']} (dangling) and appended results[] element period_id={rp['results'][-1]['period_id']} (len={len(rp['results'])})",
              False, f"invoice exists={db[PREFIX + 'billing_invoices'].count_documents({'_id': inv['_id']})}, rating_periods with _id={pid}: {db[PREFIX + 'rating_periods'].count_documents({'_id': pid})}")
    else:
        probe("issue", f"{label}: rating period finalized: rating_periods.{{_id=md5(tenant||start)}} exists with one results[] element, invoice.period_id references it",
              rp is not None and rp["_id"] == pid == inv["period_id"] and len(rp["results"]) == 1)
    return inv


FEB = (date(2026, 2, 1), date(2026, 2, 28))
T = lambda n: f"00000000-0000-0000-0000-{n:012d}"
issue_and_check("INVOICE-003 tenant 9 (two credit dates, credit > cap)", T(9), *FEB)
issue_and_check("INVOICE-004 tenant 4 (equal issued_on ties -> id order)", T(4), *FEB)
issue_and_check("INVOICE-005 tenant 6 (no credit; re-issue of EXISTING invoice 60..03 -> DUP_VAL_ON_INDEX path keeps issued_at/tenant/period)", T(6), *FEB)
issue_and_check("tenant 3 (TAX EXEMPT, credit 25 < cap -> full credit applied, tax lines 0)", T(3), *FEB)
issue_and_check("tenant 2 (SUSPENDED sub, existing OVERDUE invoice 60..01 for period 40..01 -> re-issue flips 40->20; suspension factor)", T(2), *FEB)
issue_and_check("tenant 9 AGAIN (idempotency quirk: less credit left -> higher total, same ids, lines rebuilt)", T(9), *FEB)
issue_and_check("tenant 1 January window (rollover from Dec/Jan, no credit)", T(1), date(2026, 1, 1), date(2026, 1, 31))
issue_and_check("tenant 1 Feb-15..Mar-15 straddling window", T(1), date(2026, 2, 15), date(2026, 3, 15))
issue_and_check("unknown tenant (no plan -> NULL plan line)", "ffffffff-0000-0000-0000-000000000000", *FEB)
# tenant with no covering subscription in Dec 2025?
nosub = [t for t in tenants if not q("select 1 from subscriptions where tenant_id=:t and starts_on <= :pe and (ends_on is null or ends_on >= :ps)", t=t, ps=date(2025, 12, 1), pe=date(2025, 12, 31))]
if nosub:
    issue_and_check(f"tenant {nosub[0][-2:]} Dec-2025 (real tenant, no covering subscription -> NULL plan)", nosub[0], date(2025, 12, 1), date(2025, 12, 31))
probe("issue", "tenants with no covering subscription for Dec-2025 exist in data (NULL-plan branch exercised on real tenants)", bool(nosub), len(nosub))

# clone-wide invariants after all issues
inv_all = list(db[PREFIX + "billing_invoices"].find())
probe("post", "after issues: every invoice _id==id, lines (invoice,line_no) unique, status in {20,40}, no invoice for unknown tenant",
      all(d["_id"] == d["id"] for d in inv_all) and all(len({l["line_no"] for l in d["lines"]}) == len(d["lines"]) for d in inv_all)
      and {d["status_cd"] for d in inv_all} <= {20, 40} and not [d for d in inv_all if d["tenant_id"].startswith("ffffffff")], len(inv_all))
probe("post", "credit_notes: remaining_amount never negative, never exceeds amount, Decimal128 2dp",
      all(Decimal(0) <= d["remaining_amount"].to_decimal() <= d["amount"].to_decimal() and isinstance(d["remaining_amount"], Decimal128) for d in db[PREFIX + "credit_notes"].find()))
ids = [d["log_id"] for d in db[PREFIX + "billing_audit_log"].find(sort=[("log_id", 1)])]
probe("post", "billing_audit_log log_ids strictly sequential from the seeded counter, all Int64, ns set", ids == list(range(ids[0], ids[0] + len(ids))) and ids[0] == 1
      and all(isinstance(d["log_id"], Int64) and d.get("ns") == "mongo_205236" for d in db[PREFIX + "billing_audit_log"].find()), (ids[0], ids[-1], len(ids)))

# ---------- 5. golden / quarantine / source untouched ----------
pre = json.load(open(os.path.expanduser("~/wave_recon/w3/golden_pre_fingerprint.json")))
def fp2(spec):
    d_, c = spec.split("."); h = hashlib.sha256(); n = 0
    for d in m[d_][c].find({}, sort=[("_id", 1)]):
        h.update(dumps(d, json_options=CANONICAL_JSON_OPTIONS, sort_keys=True).encode()); h.update(b"\n"); n += 1
    return n, h.hexdigest()
bad = [k for k, v in pre.items() if (v["n"], v["sha256"]) != fp2(k)]
probe("golden", f"golden + quarantine collections byte-identical to the wave-3 pre-fingerprint ({len(pre)} collections)", not bad, bad)
qs = {c: m[DB + "_quarantine"][c].count_documents({}) for c in m[DB + "_quarantine"].list_collection_names()}
probe("golden", "quarantine SETS == {bad_csv_list:31, dirty_signup_dt:50, invoice_feed_orphan_lines:37, orphan_document_snapshots:6}; U8 declares none (0 new)",
      qs == {"bad_csv_list": 31, "dirty_signup_dt": 50, "invoice_feed_orphan_lines": 37, "orphan_document_snapshots": 6}, qs)
src = q("select (select count(*) from invoices) i, (select count(*) from invoice_lines) l, (select count(*) from credit_notes) c, (select count(*) from billing_audit_log) a, (select count(*) from rating_periods) rp, (select to_char(initialized_at,'YYYY-MM-DD HH24:MI:SS.FF6') from fixture_meta) fm from dual")[0]
probe("golden", "Oracle source untouched (plain SQL only): INVOICES 3, INVOICE_LINES 2, CREDIT_NOTES 5, BILLING_AUDIT_LOG 1, RATING_PERIODS 3, FIXTURE_META unchanged", (src["i"], src["l"], src["c"], src["a"], src["rp"]) == (3, 2, 5, 1, 3) and src["fm"] == "2026-09-01 20:53:10.961888", src)

ok = sum(r["ok"] for r in res)
print(f"\n{ok}/{len(res)} ok in {time.time() - T0:.1f}s")
json.dump({"ok": ok, "total": len(res), "seconds": round(time.time() - T0, 1), "probes": res}, open(os.path.expanduser("~/wave_recon/w3/U8/probes.json"), "w"), indent=1)
