"""Independent past-the-gate probes for wave 1 (plans, tenants, subscriptions).
Read-only on both sides. Prints aggregate JSON only (no row values)."""
import json, os, sys
from collections import Counter
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID
import psycopg
from psycopg.rows import dict_row
from pymongo import MongoClient
from bson.binary import Binary
from bson.decimal128 import Decimal128

SPEC = json.load(open(".migration/mapping_spec.json"))
COLS = {c["collection"]: c for c in SPEC["collections"] if c["collection"] in ("plans", "tenants", "subscriptions")}

pg_params = json.loads(os.environ["POSTGRESQL_RO_DSN"])
schema = pg_params.pop("schema", "billing")
pg_params["dbname"] = pg_params.pop("database")
pg = psycopg.connect(**pg_params, row_factory=dict_row, autocommit=True, options="-c default_transaction_read_only=on")
db = MongoClient(os.environ["MONGODB_ATLAS_URI"], uuidRepresentation="standard")["billing_migration"]

out = {"collections_in_target_db": sorted(db.list_collection_names())}

src = {
    "plans": pg.execute("SELECT * FROM billing.plans ORDER BY id").fetchall(),
    "tenants": pg.execute("SELECT * FROM billing.tenants ORDER BY id").fetchall(),
    "credit_notes": pg.execute("SELECT * FROM billing.credit_notes ORDER BY tenant_id, issued_on, id").fetchall(),
    "subscriptions": pg.execute("SELECT * FROM billing.subscriptions ORDER BY id").fetchall(),
}
tgt = {name: list(db[name].find({}, sort=[("_id", 1)])) for name in COLS}

def canon(v):
    if isinstance(v, Decimal128):
        v = v.to_decimal()
    if isinstance(v, Decimal):
        return str(v.normalize()) if v != 0 else "0"
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, Binary):
        return "binary-subtype-" + str(v.subtype)
    return v

def bson_kind(v):
    if isinstance(v, bool): return "bool"
    if isinstance(v, int): return "int"
    if isinstance(v, Decimal128): return "decimal"
    if isinstance(v, datetime): return "date"
    if isinstance(v, UUID): return "binData(uuid, subtype 4)"
    if isinstance(v, Binary): return "binData(subtype " + str(v.subtype) + ")"
    if isinstance(v, str): return "string"
    if isinstance(v, list): return "array"
    if v is None: return "null"
    return type(v).__name__

report = {}
for name, spec in COLS.items():
    docs, root = tgt[name], src[spec["root_table"]]
    fields = {f["source"]: f["target"] for f in spec["fields"]}
    key_src, key_tgt = spec["key"]["source"][0], spec["key"]["target"]
    allowed = set(fields.values()) | {key_tgt} | {e["array_path"] for e in spec.get("embeds", [])}
    extra_fields = Counter(k for d in docs for k in d if k not in allowed)
    missing = {t: sum(1 for d in docs if t not in d) for t in fields.values()}
    nulls_tgt = {t: sum(1 for d in docs if t in d and d[t] is None) for t in fields.values()}
    nulls_src = {s: sum(1 for r in root if r[s] is None) for s in fields}
    types = {t: dict(Counter(bson_kind(d[t]) for d in docs if t in d)) for t in list(fields.values()) + [key_tgt]}
    # exact value diff after canonicalization, keyed by _id
    tmap = {canon(d[key_tgt]): d for d in docs}
    smap = {canon(r[key_src]): r for r in root}
    diffs = []
    for k, r in smap.items():
        d = tmap.get(k)
        if d is None:
            diffs.append((k, "missing_in_target")); continue
        for s, t in fields.items():
            sv, tv = canon(r[s]), canon(d.get(t))
            if sv is None and t not in d:
                continue
            if sv != tv:
                diffs.append((k, t))
    extra_docs = sorted(set(tmap) - set(smap))
    report[name] = {
        "source_rows": len(root), "target_docs": len(docs),
        "duplicate_target_ids": len(docs) - len(tmap),
        "target_missing_field_counts": missing, "target_null_counts": nulls_tgt, "source_null_counts": nulls_src,
        "target_bson_types": types, "undeclared_fields": dict(extra_fields),
        "value_diffs": len(diffs), "value_diff_fields": sorted({t for _, t in diffs}),
        "docs_not_in_source": len(extra_docs),
    }
    # indexes vs spec
    want = []
    for ix in spec.get("indexes", []):
        want.append((tuple((k, int(o)) for k, o in ix["keys"]), bool(ix.get("unique", False))))
    have = []
    for iname, info in db[name].index_information().items():
        if iname == "_id_": continue
        have.append((tuple((k, int(o)) for k, o in info["key"]), bool(info.get("unique", False))))
    report[name]["indexes"] = {"spec": len(want), "present": len(have),
                              "missing": [list(map(list, w[0])) for w in want if w not in have],
                              "undeclared": [list(map(list, h[0])) for h in have if h not in want]}
    opts = next(db.list_collections(filter={"name": name})).get("options", {})
    report[name]["validator_present"] = "validator" in opts
    report[name]["validation_level"] = opts.get("validationLevel", "strict(default)")

# natural key uniqueness, both sides
report["plans"]["natural_key_code"] = {
    "source_dupes": sum(c - 1 for c in Counter(r["code"] for r in src["plans"]).values()),
    "target_dupes": sum(c - 1 for c in Counter(d["code"] for d in tgt["plans"]).values())}
report["tenants"]["natural_key_name"] = {
    "source_dupes": sum(c - 1 for c in Counter(r["name"] for r in src["tenants"]).values()),
    "target_dupes": sum(c - 1 for c in Counter(d["name"] for d in tgt["tenants"]).values())}

# embed: creditNotes lengths vs source child counts per tenant, element values
cn_src = Counter(canon(r["tenant_id"]) for r in src["credit_notes"])
cn_tgt = {canon(d["_id"]): len(d.get("creditNotes", [])) for d in tgt["tenants"]}
len_mismatch = [k for k in cn_tgt if cn_tgt[k] != cn_src.get(k, 0)]
orphans = [k for k in cn_src if k not in cn_tgt]
elem_src = {(canon(r["tenant_id"]), canon(r["id"])): (canon(r["issued_on"]), canon(r["amount"]), canon(r["remaining_amount"])) for r in src["credit_notes"]}
elem_tgt = {}
elem_types = Counter()
order_ok = True
for d in tgt["tenants"]:
    prev = None
    for e in d.get("creditNotes", []):
        elem_tgt[(canon(d["_id"]), canon(e["id"]))] = (canon(e.get("issuedOn")), canon(e.get("amount")), canon(e.get("remainingAmount")))
        elem_types[tuple(bson_kind(e.get(k)) for k in ("id", "issuedOn", "amount", "remainingAmount"))] += 1
        cur = (e.get("issuedOn"), canon(e["id"]))
        if prev is not None and cur < prev: order_ok = False
        prev = cur
report["tenants"]["creditNotes"] = {
    "source_child_rows": len(src["credit_notes"]), "target_elements": sum(cn_tgt.values()),
    "length_distribution": dict(Counter(cn_tgt.values())),
    "tenants_with_zero_notes": sum(1 for v in cn_tgt.values() if v == 0),
    "length_mismatches": len(len_mismatch), "orphan_child_rows_without_parent_doc": len(orphans),
    "element_value_diffs": sum(1 for k, v in elem_src.items() if elem_tgt.get(k) != v),
    "elements_not_in_source": len(set(elem_tgt) - set(elem_src)),
    "element_bson_types": {" / ".join(k): v for k, v in elem_types.items()},
    "sorted_by_issuedOn_id": order_ok,
}

# referential integrity (subscriptions -> tenants, plans) both sides
tids = {canon(d["_id"]) for d in tgt["tenants"]}; pids = {canon(d["_id"]) for d in tgt["plans"]}
report["subscriptions"]["refs"] = {
    "target_dangling_tenantId": sum(1 for d in tgt["subscriptions"] if canon(d["tenantId"]) not in tids),
    "target_dangling_planId": sum(1 for d in tgt["subscriptions"] if canon(d["planId"]) not in pids),
    "source_dangling_tenant_id": pg.execute("SELECT count(*) AS n FROM billing.subscriptions s LEFT JOIN billing.tenants t ON t.id = s.tenant_id WHERE t.id IS NULL").fetchone()["n"],
    "source_dangling_plan_id": pg.execute("SELECT count(*) AS n FROM billing.subscriptions s LEFT JOIN billing.plans p ON p.id = s.plan_id WHERE p.id IS NULL").fetchone()["n"],
    "open_subscriptions_per_tenant_target": dict(Counter(Counter(canon(d["tenantId"]) for d in tgt["subscriptions"] if "endsOn" not in d).values())),
    "open_subscriptions_per_tenant_source": dict(Counter(Counter(canon(r["tenant_id"]) for r in src["subscriptions"] if r["ends_on"] is None).values())),
}
# boundaries
def mm(vals):
    vals = [v.to_decimal() if isinstance(v, Decimal128) else v for v in vals if v is not None]
    return [canon(min(vals)), canon(max(vals))] if vals else None
report["boundaries"] = {
    "subscriptions.startsOn": {"source": mm([r["starts_on"] for r in src["subscriptions"]]), "target": mm([d["startsOn"] for d in tgt["subscriptions"]])},
    "subscriptions.endsOn": {"source": mm([r["ends_on"] for r in src["subscriptions"]]), "target": mm([d.get("endsOn") for d in tgt["subscriptions"]])},
    "subscriptions.suspendedOn": {"source": mm([r["suspended_on"] for r in src["subscriptions"]]), "target": mm([d.get("suspendedOn") for d in tgt["subscriptions"]])},
    "plans.monthlyFee": {"source": mm([r["monthly_fee"] for r in src["plans"]]), "target": mm([d["monthlyFee"] for d in tgt["plans"]])},
    "plans.overageRate": {"source": mm([r["overage_rate"] for r in src["plans"]]), "target": mm([d["overageRate"] for d in tgt["plans"]])},
    "creditNotes.issuedOn": {"source": mm([r["issued_on"] for r in src["credit_notes"]]), "target": mm([e["issuedOn"] for d in tgt["tenants"] for e in d["creditNotes"]])},
    "creditNotes.remainingAmount": {"source": mm([r["remaining_amount"] for r in src["credit_notes"]]), "target": mm([e["remainingAmount"] for d in tgt["tenants"] for e in d["creditNotes"]])},
    "date_midnight_utc_all": all(d["startsOn"].hour == 0 and d["startsOn"].minute == 0 and d["startsOn"].second == 0 and d["startsOn"].microsecond == 0 for d in tgt["subscriptions"]),
    "status_domains": {"subscriptions": sorted({d["status"] for d in tgt["subscriptions"]}), "tenants": sorted({d["status"] for d in tgt["tenants"]}), "plans.tier": sorted({d["tier"] for d in tgt["plans"]})},
    "plans.inactive_count": {"source": sum(1 for r in src["plans"] if not r["active"]), "target": sum(1 for d in tgt["plans"] if not d["active"])},
    "tenants.taxExempt_true": {"source": sum(1 for r in src["tenants"] if r["tax_exempt"]), "target": sum(1 for d in tgt["tenants"] if d["taxExempt"])},
}
# later-wave tables untouched in target (write fence)
report["write_fence"] = {"later_wave_collections_present": sorted(c for c in out["collections_in_target_db"] if c not in COLS),
                         "source_later_wave_row_counts": {r["t"]: r["n"] for r in pg.execute("SELECT 'usage_events' AS t, count(*) AS n FROM billing.usage_events UNION ALL SELECT 'rating_periods', count(*) FROM billing.rating_periods UNION ALL SELECT 'rating_results', count(*) FROM billing.rating_results UNION ALL SELECT 'invoices', count(*) FROM billing.invoices UNION ALL SELECT 'invoice_lines', count(*) FROM billing.invoice_lines UNION ALL SELECT 'dunning_attempts', count(*) FROM billing.dunning_attempts UNION ALL SELECT 'notifications', count(*) FROM billing.notifications").fetchall()}}
out["probes"] = report
print(json.dumps(out, indent=1, default=str))
