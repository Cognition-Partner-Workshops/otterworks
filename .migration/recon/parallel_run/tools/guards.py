"""ns-scoped count guard + quarantine-ceiling check for one cycle (target reads only).

count guard: for every collection in the mapping spec, docs with ns == 'mongo_205236' must equal the
Tier-1 source root count recorded in that unit's gate result.json AND equal the collection's total
doc count (no foreign-ns / ns-less docs). Replay clones (U6-U9) are checked by the gates themselves.

quarantine ceiling: per unit, quarantined docs (declared classes, ns-scoped) / unit root rows <= 0.5 %.
"""
import json, os, sys
from pathlib import Path
from pymongo import MongoClient

cycle_dir = Path(sys.argv[1])
spec = json.load(open(os.path.expanduser("~/cutover_work/otterworks/.migration/03_mapping_spec.json")))
NS = spec["namespace"] if isinstance(spec.get("namespace"), str) else "mongo_205236"
cli = MongoClient(os.environ["MONGODB_ATLAS_URI"])
db = cli[spec["target_database"]]; qdb = cli[spec["quarantine_database"]]
Q_CLASSES = {"U1": ["dirty_signup_dt", "bad_csv_list"], "U2": ["invoice_feed_orphan_lines"], "U3": ["orphan_document_snapshots"]}


SRC = json.load(open(cycle_dir / "source_pre.json"))
SRC_KEY = {  # collection -> (system, key) in source_check.py output (independent of the harness)
    "codes": ("oracle", "CODES"), "tenants": ("oracle", "TENANTS"), "plans": ("oracle", "PLANS"),
    "customers": ("oracle", "CUSTOMER_MASTER@batch"), "customers_history": ("oracle", "CUSTOMER_MASTER_HIST"),
    "invoices": ("oracle", "INVOICE_HEADER@batch"), "documents": ("postgres", "documents"),
    "document_snapshots": None,  # root_where excludes orphans: use harness population (390 - 6)
    "files": ("dynamodb", "otterworks-file-metadata.ns_histogram", "demo"),
    "subscriptions": ("oracle", "SUBSCRIPTIONS"), "subscriptions_history": ("oracle", "SUBSCRIPTIONS_HIST"),
    "usage_events": ("oracle", "USAGE_EVENTS"), "rating_periods": ("oracle", "RATING_PERIODS"),
    "billing_invoices": ("oracle", "INVOICES"), "credit_notes": ("oracle", "CREDIT_NOTES"),
    "dunning_attempts": ("oracle", "DUNNING_ATTEMPTS"), "notifications": ("oracle", "NOTIFICATIONS"),
    "billing_audit_log": ("oracle", "BILLING_AUDIT_LOG"),
}


def tier1_counts(unit):
    """root population per collection: independent source read (source_pre.json) cross-checked
    against the harness Tier-3 `population` in the unit's result.json."""
    p = cycle_dir / unit / "gate" / "result.json"
    r = json.load(open(p))
    pop = {}
    for tier in r.get("tiers", []):
        if tier.get("tier") == 3:
            for k, v in tier.get("stats", {}).items():
                if isinstance(v, dict) and "population" in v:
                    pop[k] = v["population"]
    out = {}
    for coll, harness_pop in pop.items():
        key = SRC_KEY.get(coll)
        if key is None:
            out[coll] = harness_pop
        else:
            v = SRC[key[0]][key[1]]
            if len(key) == 3: v = v.get(key[2], 0)
            out[coll] = v if v == harness_pop else ("MISMATCH", v, harness_pop)
    return out, r


report = {"ns": NS, "count_guard": [], "quarantine_ceiling": [], "verdict": "PASS"}
unit_roots = {}
for c in spec["collections"]:
    unit, coll = c["unit"], c["collection"]
    total = db[coll].count_documents({})
    ns_docs = db[coll].count_documents({"ns": NS})
    t1, _ = tier1_counts(unit)
    src = t1.get(coll)
    note = ""
    if src is None:
        ok = False; note = "no Tier-3 population found in result.json"
    elif isinstance(src, tuple):
        ok = False; note = f"independent source count {src[1]} != harness population {src[2]}"; src = src[1]
    else:
        ok = (ns_docs == total) and (src == ns_docs)
    report["count_guard"].append({"unit": unit, "collection": coll, "source_root_rows": src,
                                  "target_docs_total": total, "target_docs_ns": ns_docs, "ok": ok, "note": note})
    if not ok: report["verdict"] = "FAIL"
    unit_roots[unit] = unit_roots.get(unit, 0) + (src or 0)

for unit, classes in Q_CLASSES.items():
    q = 0; per = {}
    for cls in classes:
        n = qdb[cls].count_documents({"ns": NS}); nall = qdb[cls].count_documents({})
        per[cls] = {"ns_docs": n, "total_docs": nall}; q += n
    roots = unit_roots.get(unit, 0)
    rate = (q / roots) if roots else None
    ok = rate is not None and rate <= 0.005
    report["quarantine_ceiling"].append({"unit": unit, "classes": per, "quarantined": q, "unit_root_rows": roots,
                                         "rate": rate, "ceiling": 0.005, "ok": ok})
    if not ok: report["verdict"] = "FAIL"
for unit in ("U0", "U4", "U5", "U6", "U7", "U8", "U9"):
    report["quarantine_ceiling"].append({"unit": unit, "classes": {}, "quarantined": 0,
                                         "unit_root_rows": unit_roots.get(unit, 0), "rate": 0.0, "ceiling": 0.005, "ok": True,
                                         "note": "no quarantine targets declared; expected 0"})
report["quarantine_db_collections"] = sorted(qdb.list_collection_names())
expected_q = sorted(sum(Q_CLASSES.values(), []))
report["quarantine_db_only_declared_classes"] = report["quarantine_db_collections"] == expected_q
if not report["quarantine_db_only_declared_classes"]: report["verdict"] = "FAIL"
json.dump(report, open(cycle_dir / "guards.json", "w"), indent=2, default=str)
print("guards", report["verdict"])
for r in report["count_guard"]:
    print(f"  count {r['unit']} {r['collection']}: src={r['source_root_rows']} ns={r['target_docs_ns']} total={r['target_docs_total']} ok={r['ok']} {r['note']}")
for r in report["quarantine_ceiling"]:
    if r["classes"]: print(f"  quarantine {r['unit']}: {r['quarantined']}/{r['unit_root_rows']} = {r['rate']:.5f} ok={r['ok']}")
print("  quarantine db classes:", report["quarantine_db_collections"], "only-declared:", report["quarantine_db_only_declared_classes"])
sys.exit(0 if report["verdict"] == "PASS" else 1)
