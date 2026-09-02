"""Independent fix-pass probes (F-U8-1, F-X-1). Reads Oracle with plain SQL only; writes only to
scratch `replay_fixprobe_*` collections in ow_tp_mongodb_205236, which are dropped at the end."""
import json, os, sys, hashlib
from pathlib import Path

import bson, oracledb
from bson import Int64
from pymongo import MongoClient

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "services/legacy-billing/app"))
from ow_billing import NS_VALUE, Store, util, rating, invoicing, plans, dunning  # noqa: E402

DB = "ow_tp_mongodb_205236"
client = MongoClient(os.environ["MONGODB_ATLAS_URI"])
db = client[DB]
u, p, d = os.environ["OW_BILLING_FIXTURE_DSN"].split("/", 2)
results = []


def check(group, name, ok, detail=None):
    results.append({"group": group, "probe": name, "ok": bool(ok), "detail": detail})
    print(("ok  " if ok else "FLAG"), group, name, "" if detail is None else json.dumps(detail, default=str)[:400])


with oracledb.connect(user=u, password=p, dsn=d) as ora:
    cur = ora.cursor()
    cur.execute("SELECT SEQUENCE_NAME, LAST_NUMBER FROM USER_SEQUENCES ORDER BY 1")
    last_number = {r[0]: int(r[1]) for r in cur}
    cur.execute("SELECT INVOICE_ID, LINE_NO FROM INVOICE_LINES ORDER BY 1,2")
    ora_lines = [(r[0], int(r[1])) for r in cur]
    cur.execute("SELECT LOG_ID, MODULE, MESSAGE FROM BILLING_AUDIT_LOG ORDER BY LOG_ID")
    ora_audit = [(int(r[0]), r[1], r[2]) for r in cur]

# ---- 1. lines[].invoice_id on golden + every replay clone -------------------------------------
for coll in ["billing_invoices"] + [c for c in sorted(db.list_collection_names()) if c.endswith("_billing_invoices") and c.startswith("replay_")]:
    bad, n_inv, n_lines = [], 0, 0
    for doc in db[coll].find({}, sort=[("_id", 1)]):
        n_inv += 1
        for i, line in enumerate(doc.get("lines") or []):
            n_lines += 1
            if line.get("invoice_id") is None or line["invoice_id"] != doc["_id"] or line["invoice_id"] != doc.get("id"):
                bad.append({"invoice": doc["_id"], "idx": i, "invoice_id": line.get("invoice_id")})
    check("F-U8-1", f"{coll}: every lines[] element carries invoice_id == parent _id == parent id",
          not bad and n_inv > 0, {"invoices": n_inv, "lines": n_lines, "bad": bad})

# golden lines set == Oracle INVOICE_LINES (invoice_id, line_no)
golden_lines = sorted((l["invoice_id"], int(l["line_no"])) for doc in db.billing_invoices.find() for l in doc.get("lines") or [])
check("F-U8-1", "golden billing_invoices lines (invoice_id,line_no) SET == Oracle INVOICE_LINES", golden_lines == sorted(ora_lines),
      {"golden": len(golden_lines), "oracle": len(ora_lines)})

# ---- 2. golden counters --------------------------------------------------------------------------
docs = list(db.counters.find(sort=[("_id", 1)]))
expected = {name.lower(): n for name, n in last_number.items()}
check("F-X-1", "counters: exactly one document per Oracle USER_SEQUENCES sequence (5)",
      sorted(d["_id"] for d in docs) == sorted(expected) and len(docs) == len(expected), {"ids": [d["_id"] for d in docs]})
check("F-X-1", "counters: no duplicate _id / one doc per source_sequence",
      len({d["_id"] for d in docs}) == len(docs) and len({d.get("source_sequence") for d in docs}) == len(docs))
mism = {d["_id"]: (d.get("seq"), expected.get(d["_id"])) for d in docs if d.get("seq") != expected.get(d["_id"])}
check("F-X-1", "counters.seq == Oracle USER_SEQUENCES.LAST_NUMBER for every sequence", not mism,
      {d["_id"]: int(d["seq"]) for d in docs} | {"oracle": last_number, "mismatch": mism})
check("F-X-1", "counters docs shape {_id, seq:Int64, source_sequence=_id.upper(), ns}",
      all(set(d) == {"_id", "seq", "source_sequence", "ns"} and isinstance(d["seq"], Int64) and type(d["seq"]) is Int64
          and d["source_sequence"] == d["_id"].upper() and d["ns"] == NS_VALUE for d in docs),
      [{k: (type(v).__name__ if k == "seq" else v) for k, v in d.items()} for d in docs])
check("F-X-1", "counters: no legacy-contract docs (`SEQ_BILLING_AUDIT_LOG`/`value`) anywhere in golden or clones",
      all(db[c].count_documents({"$or": [{"_id": "SEQ_BILLING_AUDIT_LOG"}, {"value": {"$exists": True}}]}) == 0
          for c in db.list_collection_names() if c.endswith("counters")),
      [c for c in db.list_collection_names() if c.endswith("counters")])

# ---- 3. static: all log_msg call sites funnel into util.log_msg with one contract ---------------
check("F-X-1", "static: rating.log_msg and invoicing.log_msg delegate to util.log_msg; plans/dunning call util.log_msg",
      "util.log_msg" in (Path(rating.__file__).read_text()) and "util.log_msg" in Path(invoicing.__file__).read_text()
      and "util.log_msg" in Path(plans.__file__).read_text() and "util.log_msg" in Path(dunning.__file__).read_text()
      and "AUDIT_SEQUENCE" not in Path(rating.__file__).read_text()
      and util.SEQ_BILLING_AUDIT_LOG == "seq_billing_audit_log")

# ---- 4. clone audit log / counters vs source (T1-T3 style, manual) -----------------------------
for prefix in ("replay_u6_", "replay_u7_", "replay_u8_", "replay_u9_"):
    audit = list(db[f"{prefix}billing_audit_log"].find(sort=[("log_id", 1)]))
    base = [(int(a["log_id"]), a["module"], a["message"]) for a in audit if int(a["log_id"]) <= max(r[0] for r in ora_audit)]
    ids = [int(a["log_id"]) for a in audit]
    ctr = {c["_id"]: c for c in db[f"{prefix}counters"].find()}
    check("audit", f"{prefix}billing_audit_log: fixture rows keyed-equal to Oracle BILLING_AUDIT_LOG; all ids unique, strictly increasing, _id==log_id, Int64",
          base == ora_audit and ids == sorted(set(ids)) and all(a["_id"] == a["log_id"] and type(a["log_id"]) is Int64 for a in audit),
          {"docs": len(audit), "oracle_rows": len(ora_audit), "ids": ids})
    check("audit", f"{prefix}counters: seq_billing_audit_log.seq == max(log_id) after Tier-4 replays (no gap/collision) and >= Oracle LAST_NUMBER-1; single contract",
          set(ctr) == {"seq_billing_audit_log", "seq_subscriptions_hist"} and int(ctr["seq_billing_audit_log"]["seq"]) == max(ids)
          and int(ctr["seq_billing_audit_log"]["seq"]) >= last_number["SEQ_BILLING_AUDIT_LOG"] - 1,
          {k: int(v["seq"]) for k, v in ctr.items()} | {"max_log_id": max(ids), "oracle_last_number": last_number["SEQ_BILLING_AUDIT_LOG"]})

# ---- 5. three log_msg paths on a scratch clone ---------------------------------------------------
SCRATCH = "replay_fixprobe_"
for c in (f"{SCRATCH}billing_audit_log", f"{SCRATCH}counters"):
    db.drop_collection(c)
db[f"{SCRATCH}billing_audit_log"].insert_many(list(db.billing_audit_log.find()))
db[f"{SCRATCH}counters"].insert_many(list(db.counters.find()))
try:
    seed = int(db[f"{SCRATCH}counters"].find_one({"_id": "seq_billing_audit_log"})["seq"])
    store6 = Store(client, DB, SCRATCH)                       # U6 plans / U9 dunning path
    store7 = rating.RatingStore(db, SCRATCH)                  # U7 path
    store8 = invoicing.InvoicingStore(db, SCRATCH)            # U8 path
    got = [
        util.log_msg(store6, "PLANS", "fixprobe util.log_msg"),
        rating.log_msg(store7, "RATING", "fixprobe rating.log_msg"),
        invoicing.log_msg(store8, "INVOICING", "fixprobe invoicing.log_msg"),
    ]
    got2 = [
        util.log_msg(store6, "PLANS", "fixprobe util.log_msg #2"),
        rating.log_msg(store7, "RATING", "fixprobe rating.log_msg #2"),
        invoicing.log_msg(store8, "INVOICING", "fixprobe invoicing.log_msg #2"),
    ]
    all_ids = got + got2
    check("F-X-1", "three log_msg paths (util/rating/invoicing) x2 on one scratch store: returned ids == seed+1..seed+6, strictly monotonic, no collision",
          all_ids == [Int64(seed + i) for i in range(1, 7)], {"seed": seed, "ids": [int(x) for x in all_ids]})
    rows = list(db[f"{SCRATCH}billing_audit_log"].find({"log_id": {"$gt": seed}}, sort=[("log_id", 1)]))
    check("F-X-1", "scratch audit rows: 6 inserted, _id==log_id, modules in call order, ns set, Int64",
          [int(r["log_id"]) for r in rows] == list(range(seed + 1, seed + 7)) and [r["module"] for r in rows] == ["PLANS", "RATING", "INVOICING"] * 2
          and all(r["_id"] == r["log_id"] and type(r["log_id"]) is Int64 and r["ns"] == NS_VALUE for r in rows),
          [(int(r["log_id"]), r["module"]) for r in rows])
    ctr_after = db[f"{SCRATCH}counters"].find_one({"_id": "seq_billing_audit_log"})
    check("F-X-1", "scratch counter advanced exactly +6 with the single contract (`seq`), no `value` field, other 4 counters untouched",
          int(ctr_after["seq"]) == seed + 6 and "value" not in ctr_after and db[f"{SCRATCH}counters"].count_documents({}) == 5
          and all(int(x["seq"]) == int(y["seq"]) for x, y in zip(db[f"{SCRATCH}counters"].find({"_id": {"$ne": "seq_billing_audit_log"}}, sort=[("_id", 1)]),
                                                            db.counters.find({"_id": {"$ne": "seq_billing_audit_log"}}, sort=[("_id", 1)]))),
          {"seq_after": int(ctr_after["seq"])})
    # unseeded counter -> LookupError surfaced by util (not PyMongoError) ; PyMongo failure swallowed like WHEN OTHERS
    db[f"{SCRATCH}counters"].delete_one({"_id": "seq_billing_audit_log"})
    try:
        util.log_msg(store6, "PLANS", "unseeded"); unseeded = "no error"
    except LookupError as e:
        unseeded = f"LookupError: {e}"
    check("F-X-1", "unseeded seq_billing_audit_log -> LookupError (loud, not silently swallowed)", unseeded.startswith("LookupError"), unseeded)
finally:
    for c in (f"{SCRATCH}billing_audit_log", f"{SCRATCH}counters"):
        db.drop_collection(c)
    check("cleanup", "scratch replay_fixprobe_* collections dropped", not [c for c in db.list_collection_names() if c.startswith(SCRATCH)])

# ---- 6. golden untouched except counters (which now equals Oracle) -----------------------------
check("golden", "golden billing_audit_log still == Oracle BILLING_AUDIT_LOG (1 row) — probes wrote only to scratch",
      [(int(a["log_id"]), a["module"], a["message"]) for a in db.billing_audit_log.find(sort=[("log_id", 1)])] == ora_audit)

summary = {"ok": sum(r["ok"] for r in results), "total": len(results), "flags": [r for r in results if not r["ok"]]}
print(json.dumps(summary, default=str))
json.dump({"summary": summary, "results": results, "oracle_last_number": last_number}, open(sys.argv[2], "w"), indent=1, default=str)
client.close()
sys.exit(0 if not summary["flags"] else 1)
