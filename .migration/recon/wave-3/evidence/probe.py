"""Independent past-the-gate probes for wave 3 (invoices with the `invoiceLines` and
`dunningAttempts` arrays, notifications) plus cross-unit references into the wave-1/2
collections and the state of the collections wave 3 writes through owner APIs
(tenants.creditNotes, tenants.status, subscriptions.status/suspendedOn).
Read-only on both sides. Prints aggregate JSON only (no row values)."""
import hashlib, json, os
from collections import Counter
from decimal import Decimal
from datetime import datetime, date, timezone
from uuid import UUID
import psycopg
from psycopg.rows import dict_row
from pymongo import MongoClient
from bson.binary import Binary
from bson.decimal128 import Decimal128

SPEC = json.load(open(".migration/mapping_spec.json"))
WAVE3 = ("invoices", "notifications")
COLS = {c["collection"]: c for c in SPEC["collections"] if c["collection"] in WAVE3}

pg_params = json.loads(os.environ["POSTGRESQL_RO_DSN"])
pg_params.pop("schema", "billing")
pg_params["dbname"] = pg_params.pop("database")
pg = psycopg.connect(**pg_params, row_factory=dict_row, autocommit=True, options="-c default_transaction_read_only=on")
db = MongoClient(os.environ["MONGODB_ATLAS_URI"], uuidRepresentation="standard", tz_aware=True)["billing_migration"]

out = {"collections_in_target_db": sorted(db.list_collection_names()),
       "pg_session_timezone": pg.execute("SHOW TimeZone").fetchone()["TimeZone"]}

def rows(sql): return pg.execute(sql).fetchall()
src = {
    "invoices": rows("SELECT * FROM billing.invoices ORDER BY id"),
    "invoice_lines": rows("SELECT * FROM billing.invoice_lines ORDER BY id"),
    "dunning_attempts": rows("SELECT * FROM billing.dunning_attempts ORDER BY id"),
    "notifications": rows("SELECT * FROM billing.notifications ORDER BY id"),
    "tenants": rows("SELECT id, status, tax_exempt FROM billing.tenants ORDER BY id"),
    "subscriptions": rows("SELECT id, tenant_id, status, suspended_on FROM billing.subscriptions ORDER BY id"),
    "credit_notes": rows("SELECT * FROM billing.credit_notes ORDER BY id"),
    "rating_periods": rows("SELECT id, tenant_id FROM billing.rating_periods ORDER BY id"),
}
tgt = {name: list(db[name].find({}, sort=[("_id", 1)])) for name in WAVE3}
tgt_tenants = list(db.tenants.find({}, sort=[("_id", 1)]))
tgt_subs = list(db.subscriptions.find({}, sort=[("_id", 1)]))
tgt_periods = {d["_id"]: d for d in db.ratingPeriods.find({}, {"_id": 1, "tenantId": 1})}

def canon(v):
    if isinstance(v, Decimal128): v = v.to_decimal()
    if isinstance(v, Decimal): return str(v.normalize()) if v != 0 else "0"
    if isinstance(v, datetime):
        if v.tzinfo is None: v = v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc).isoformat(timespec="milliseconds")
    if isinstance(v, date): return datetime(v.year, v.month, v.day, tzinfo=timezone.utc).isoformat(timespec="milliseconds")
    if isinstance(v, UUID): return str(v)
    if isinstance(v, Binary): return "binary-subtype-" + str(v.subtype)
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
    if isinstance(v, dict): return "object"
    if v is None: return "null"
    return type(v).__name__

def md5uuid(*parts): return UUID(hashlib.md5("".join(parts).encode()).hexdigest())
def dec(v): return v.to_decimal() if isinstance(v, Decimal128) else Decimal(str(v))
def scale(v): return -dec(v).as_tuple().exponent

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
    tmap = {canon(d[key_tgt]): d for d in docs}
    smap = {canon(r[key_src]): r for r in root}
    diffs = []
    for k, r in smap.items():
        d = tmap.get(k)
        if d is None:
            diffs.append((k, "missing_in_target")); continue
        for s, t in fields.items():
            sv, tv = canon(r[s]), canon(d.get(t))
            if sv is None and t not in d: continue
            if sv != tv: diffs.append((k, t))
    extra_docs = sorted(set(tmap) - set(smap))
    report[name] = {
        "source_rows": len(root), "target_docs": len(docs),
        "duplicate_target_ids": len(docs) - len(tmap),
        "target_missing_field_counts": missing, "target_null_counts": nulls_tgt, "source_null_counts": nulls_src,
        "target_bson_types": types, "undeclared_fields": dict(extra_fields),
        "value_diffs": len(diffs), "value_diff_fields": sorted({t for _, t in diffs}),
        "docs_not_in_source": len(extra_docs),
    }
    want = [(tuple((k, int(o)) for k, o in ix["keys"]), bool(ix.get("unique", False))) for ix in spec.get("indexes", [])]
    have = [(tuple((k, int(o)) for k, o in info["key"]), bool(info.get("unique", False)))
            for iname, info in db[name].index_information().items() if iname != "_id_"]
    report[name]["indexes"] = {"spec": len(want), "present": len(have),
                              "missing": [list(map(list, w[0])) for w in want if w not in have],
                              "undeclared": [list(map(list, h[0])) for h in have if h not in want]}
    opts = next(db.list_collections(filter={"name": name})).get("options", {})
    report[name]["validator_present"] = "validator" in opts
    report[name]["validation_level"] = opts.get("validationLevel", "strict(default)")

# natural keys, both sides
report["notifications"]["natural_key_tenantId_kind_sentAt"] = {
    "source_dupes": sum(c - 1 for c in Counter((canon(r["tenant_id"]), r["kind"], canon(r["sent_at"])) for r in src["notifications"]).values()),
    "target_dupes": sum(c - 1 for c in Counter((canon(d["tenantId"]), d["kind"], canon(d["sentAt"])) for d in tgt["notifications"]).values())}
report["invoices"]["periodId_shared_by_several_invoices"] = {
    "source": sum(c - 1 for c in Counter(canon(r["period_id"]) for r in src["invoices"]).values()),
    "target": sum(c - 1 for c in Counter(canon(d["periodId"]) for d in tgt["invoices"]).values())}

# embeds: invoices.invoiceLines (1:N, child key line_no) and invoices.dunningAttempts (1:few, child key id)
inv_src = {canon(r["id"]): r for r in src["invoices"]}
def embed_probe(array_path, child_rows, child_key_src, child_key_tgt, order_field=None):
    emb = next(e for e in COLS["invoices"]["embeds"] if e["array_path"] == array_path)
    child_fields = {f["source"]: f["target"] for f in emb["child_fields"]}
    pk_fields = {f["source"]: f["target"] for f in emb.get("parent_key_fields", [])}
    by_parent = {}
    for r in child_rows: by_parent.setdefault(canon(r["invoice_id"]), []).append(r)
    res = {"source_child_rows": len(child_rows), "target_elements": 0,
           "source_children_per_invoice": {}, "target_elements_per_invoice": {}, "length_mismatches": 0,
           "arrays_missing_on_target": 0, "non_array_values": 0, "elements_without_source_row": 0,
           "source_rows_without_element": 0, "duplicate_child_keys_in_array": 0, "element_value_diffs": 0,
           "element_value_diff_fields": set(), "element_bson_types": Counter(), "parent_key_field_present_in_element": Counter(),
           "undeclared_element_fields": Counter(), "orphan_source_children_without_invoice": sum(1 for r in child_rows if canon(r["invoice_id"]) not in inv_src),
           "out_of_order_arrays": 0}
    for d in tgt["invoices"]:
        iid = canon(d["_id"]); arr = d.get(array_path)
        children = by_parent.get(iid, [])
        res["source_children_per_invoice"][iid[-4:]] = len(children)
        if arr is None: res["arrays_missing_on_target"] += 1; arr = []
        elif not isinstance(arr, list): res["non_array_values"] += 1; arr = []
        res["target_elements_per_invoice"][iid[-4:]] = len(arr); res["target_elements"] += len(arr)
        if len(arr) != len(children): res["length_mismatches"] += 1
        keys = [canon(e.get(child_key_tgt)) for e in arr]
        res["duplicate_child_keys_in_array"] += len(keys) - len(set(keys))
        if order_field and [e.get(order_field) for e in arr] != sorted(e.get(order_field) for e in arr): res["out_of_order_arrays"] += 1
        smap = {canon(r[child_key_src]): r for r in children}
        for e in arr:
            r = smap.get(canon(e.get(child_key_tgt)))
            if r is None: res["elements_without_source_row"] += 1; continue
            for s, t in child_fields.items():
                res["element_bson_types"][f"{t}: {bson_kind(e.get(t))}"] += 1
                if canon(r[s]) != canon(e.get(t)): res["element_value_diffs"] += 1; res["element_value_diff_fields"].add(t)
            for s, t in pk_fields.items():
                if t in e:
                    res["parent_key_field_present_in_element"][t] += 1
                    if canon(r[s]) != canon(e[t]): res["element_value_diffs"] += 1; res["element_value_diff_fields"].add(t)
            for k in e:
                if k not in set(child_fields.values()) | set(pk_fields.values()): res["undeclared_element_fields"][k] += 1
        res["source_rows_without_element"] += sum(1 for k in smap if k not in set(keys))
    res["element_value_diff_fields"] = sorted(res["element_value_diff_fields"])
    for k in ("element_bson_types", "parent_key_field_present_in_element", "undeclared_element_fields"): res[k] = dict(res[k])
    res["source_fanout_distribution"] = dict(Counter(len(v) for v in by_parent.values()) + Counter({0: sum(1 for i in inv_src if i not in by_parent)}))
    return res
report["invoices"]["invoiceLines"] = embed_probe("invoiceLines", src["invoice_lines"], "line_no", "lineNo", order_field="lineNo")
report["invoices"]["dunningAttempts"] = embed_probe("dunningAttempts", src["dunning_attempts"], "id", "id", order_field="attemptNo")
report["invoices"]["dunningAttempts"]["duplicate_attemptNo_in_array"] = sum(
    len(d.get("dunningAttempts", [])) - len({e.get("attemptNo") for e in d.get("dunningAttempts", [])}) for d in tgt["invoices"])
report["invoices"]["dunningAttempts"]["tenantId_differs_from_invoice"] = {
    "source": sum(1 for r in src["dunning_attempts"] if canon(r["tenant_id"]) != canon(inv_src[canon(r["invoice_id"])]["tenant_id"])),
    "target": sum(1 for d in tgt["invoices"] for e in d.get("dunningAttempts", []) if canon(e.get("tenantId")) != canon(d["tenantId"]))}
report["invoices"]["invoiceLines"]["duplicate_lineNo_in_array"] = sum(
    len(d.get("invoiceLines", [])) - len({e.get("lineNo") for e in d.get("invoiceLines", [])}) for d in tgt["invoices"])

# legacy identity rule (md5 ids) — imported identities vs procedure-created ones
report["identity_rule"] = {
    "invoice_id_is_md5_period_id_invoice": {"source": sum(1 for r in src["invoices"] if r["id"] == md5uuid(str(r["period_id"]), "invoice")),
                                             "target": sum(1 for d in tgt["invoices"] if d["_id"] == md5uuid(str(d["periodId"]), "invoice"))},
    "line_id_is_md5_invoice_id_line_no": {"source": sum(1 for r in src["invoice_lines"] if r["id"] == md5uuid(str(r["invoice_id"]), str(r["line_no"]))),
                                          "target": sum(1 for d in tgt["invoices"] for e in d.get("invoiceLines", []) if e["id"] == md5uuid(str(d["_id"]), str(e["lineNo"])))},
    "attempt_id_is_md5_invoice_id_attempt_no": {"source": sum(1 for r in src["dunning_attempts"] if r["id"] == md5uuid(str(r["invoice_id"]), str(r["attempt_no"]))),
                                                "target": sum(1 for d in tgt["invoices"] for e in d.get("dunningAttempts", []) if e["id"] == md5uuid(str(d["_id"]), str(e["attemptNo"])))},
    "notification_id_is_md5_tenant_kind_date": {"source": sum(1 for r in src["notifications"] if r["id"] == md5uuid(str(r["tenant_id"]), r["kind"], r["sent_at"].astimezone(timezone.utc).date().isoformat())),
                                                "target": sum(1 for d in tgt["notifications"] if d["_id"] == md5uuid(str(d["tenantId"]), d["kind"], d["sentAt"].astimezone(timezone.utc).date().isoformat()))},
}

# cross-unit references and the collections wave 3 writes through owner APIs
tenant_src = {canon(r["id"]): r for r in src["tenants"]}
tenant_tgt = {canon(d["_id"]): d for d in tgt_tenants}
period_tenant_src = {canon(r["id"]): canon(r["tenant_id"]) for r in src["rating_periods"]}
period_tenant_tgt = {canon(k): canon(v["tenantId"]) for k, v in tgt_periods.items()}
cn_src = {canon(r["id"]): r for r in src["credit_notes"]}
cn_tgt = {canon(e["id"]): (canon(d["_id"]), e) for d in tgt_tenants for e in d.get("creditNotes", [])}
sub_src = {canon(r["id"]): r for r in src["subscriptions"]}
sub_tgt = {canon(d["_id"]): d for d in tgt_subs}
report["cross_unit"] = {
    "earlier_wave_counts_target": {c: db[c].estimated_document_count() for c in ("plans", "tenants", "subscriptions", "usageEvents", "ratingPeriods")},
    "earlier_wave_counts_source": {r["t"]: r["n"] for r in rows("SELECT 'plans' AS t, count(*) AS n FROM billing.plans UNION ALL SELECT 'tenants', count(*) FROM billing.tenants UNION ALL SELECT 'subscriptions', count(*) FROM billing.subscriptions UNION ALL SELECT 'usageEvents', count(*) FROM billing.usage_events UNION ALL SELECT 'ratingPeriods', count(*) FROM billing.rating_periods")},
    "invoices.tenantId_dangling": {"source": sum(1 for r in src["invoices"] if canon(r["tenant_id"]) not in tenant_src), "target": sum(1 for d in tgt["invoices"] if canon(d["tenantId"]) not in tenant_tgt)},
    "invoices.periodId_dangling_to_ratingPeriods": {"source": sum(1 for r in src["invoices"] if canon(r["period_id"]) not in period_tenant_src), "target": sum(1 for d in tgt["invoices"] if canon(d["periodId"]) not in period_tenant_tgt)},
    "invoices.periodId_belongs_to_other_tenant": {"source": sum(1 for r in src["invoices"] if period_tenant_src.get(canon(r["period_id"])) not in (None, canon(r["tenant_id"]))), "target": sum(1 for d in tgt["invoices"] if period_tenant_tgt.get(canon(d["periodId"])) not in (None, canon(d["tenantId"])))},
    "dunningAttempts.tenantId_dangling_target": sum(1 for d in tgt["invoices"] for e in d.get("dunningAttempts", []) if canon(e.get("tenantId")) not in tenant_tgt),
    "notifications.tenantId_dangling": {"source": sum(1 for r in src["notifications"] if canon(r["tenant_id"]) not in tenant_src), "target": sum(1 for d in tgt["notifications"] if canon(d["tenantId"]) not in tenant_tgt)},
    "notifications.kind_domain": {"source": sorted({r["kind"] for r in src["notifications"]}), "target": sorted({d["kind"] for d in tgt["notifications"]})},
    "overdue_invoices_per_tenant_status": {"source": dict(Counter(tenant_src[canon(r["tenant_id"])]["status"] for r in src["invoices"] if r["status"] == "overdue")),
                                           "target": dict(Counter(tenant_tgt[canon(d["tenantId"])]["status"] for d in tgt["invoices"] if d["status"] == "overdue"))},
    # tenants.creditNotes (written by invoicing's apply_credit) must still equal credit_notes
    "tenants.creditNotes": {"source_rows": len(cn_src), "target_elements": len(cn_tgt),
                            "missing_on_target": sum(1 for k in cn_src if k not in cn_tgt), "not_in_source": sum(1 for k in cn_tgt if k not in cn_src),
                            "on_wrong_tenant": sum(1 for k, (tid, e) in cn_tgt.items() if k in cn_src and canon(cn_src[k]["tenant_id"]) != tid),
                            "value_diffs": sum(1 for k, (tid, e) in cn_tgt.items() if k in cn_src for s, t in (("issued_on", "issuedOn"), ("amount", "amount"), ("remaining_amount", "remainingAmount")) if canon(cn_src[k][s]) != canon(e.get(t))),
                            "remainingAmount_sum": {"source": str(sum(r["remaining_amount"] for r in cn_src.values())), "target": str(sum(dec(e["remainingAmount"]) for _, e in cn_tgt.values()))},
                            "remainingAmount_gt_amount": {"source": sum(1 for r in cn_src.values() if r["remaining_amount"] > r["amount"]), "target": sum(1 for _, e in cn_tgt.values() if dec(e["remainingAmount"]) > dec(e["amount"]))}},
    # tenants.status / subscriptions.status+suspendedOn (written by plans' suspend_tenant) must still equal the source
    "tenants.status": {"source": dict(Counter(r["status"] for r in src["tenants"])), "target": dict(Counter(d["status"] for d in tgt_tenants)),
                       "value_diffs": sum(1 for k, r in tenant_src.items() if k not in tenant_tgt or r["status"] != tenant_tgt[k]["status"])},
    "subscriptions.status_suspendedOn": {"source_status": dict(Counter(r["status"] for r in src["subscriptions"])), "target_status": dict(Counter(d["status"] for d in tgt_subs)),
                                         "value_diffs": sum(1 for k, r in sub_src.items() if k not in sub_tgt or r["status"] != sub_tgt[k]["status"] or canon(r["suspended_on"]) != canon(sub_tgt[k].get("suspendedOn"))),
                                         "suspendedOn_set": {"source": sum(1 for r in src["subscriptions"] if r["suspended_on"] is not None), "target": sum(1 for d in tgt_subs if d.get("suspendedOn") is not None)}},
}

# boundaries, arithmetic invariants and DATE / TIMESTAMPTZ representation
def mm(vals):
    vals = [dec(v) if isinstance(v, (Decimal128, Decimal)) else v for v in vals if v is not None]
    return [canon(min(vals)), canon(max(vals))] if vals else None
def not_midnight(v): return isinstance(v, datetime) and (v.hour, v.minute, v.second, v.microsecond) != (0, 0, 0, 0)
lines_src_by_inv = {}
for r in src["invoice_lines"]: lines_src_by_inv.setdefault(canon(r["invoice_id"]), []).append(r)
def totals_hold_src(r):
    ls = lines_src_by_inv.get(canon(r["id"]), [])
    if not ls: return None
    sub = sum(l["amount"] for l in ls if l["line_type"] in ("plan", "usage")); tax = sum(l["amount"] for l in ls if l["line_type"] == "tax")
    credit = -sum(l["amount"] for l in ls if l["line_type"] == "credit")
    return r["subtotal"] == sub and r["tax"] == tax and r["total"] == sub + tax - credit
def totals_hold_tgt(d):
    ls = d.get("invoiceLines", [])
    if not ls: return None
    sub = sum(dec(l["amount"]) for l in ls if l["lineType"] in ("plan", "usage")); tax = sum(dec(l["amount"]) for l in ls if l["lineType"] == "tax")
    credit = -sum(dec(l["amount"]) for l in ls if l["lineType"] == "credit")
    return dec(d["subtotal"]) == sub and dec(d["tax"]) == tax and dec(d["total"]) == sub + tax - credit
ts_fields = {"invoices.issuedAt": ([r["issued_at"] for r in src["invoices"]], [d.get("issuedAt") for d in tgt["invoices"]]),
             "notifications.sentAt": ([r["sent_at"] for r in src["notifications"]], [d.get("sentAt") for d in tgt["notifications"]])}
date_fields = {"dunningAttempts.scheduledFor": [e.get("scheduledFor") for d in tgt["invoices"] for e in d.get("dunningAttempts", [])]}
report["boundaries"] = {
    "invoices.issuedAt": {"source": mm([r["issued_at"] for r in src["invoices"]]), "target": mm([d["issuedAt"] for d in tgt["invoices"]])},
    "invoices.status_domain": {"source": sorted({r["status"] for r in src["invoices"]}), "target": sorted({d["status"] for d in tgt["invoices"]})},
    "invoices.status_count": {"source": dict(Counter(r["status"] for r in src["invoices"])), "target": dict(Counter(d["status"] for d in tgt["invoices"]))},
    **{f"invoices.{f}": {"source": mm([r[f] for r in src["invoices"]]), "target": mm([d[f] for d in tgt["invoices"]]),
                         "sum_source": str(sum(r[f] for r in src["invoices"])), "sum_target": str(sum(dec(d[f]) for d in tgt["invoices"]))} for f in ("subtotal", "tax", "total")},
    "invoices.decimal_scale_gt_2_target": sum(1 for d in tgt["invoices"] for f in ("subtotal", "tax", "total") if scale(d[f]) > 2),
    "invoices.negative_amounts": {"source": sum(1 for r in src["invoices"] for f in ("subtotal", "tax", "total") if r[f] < 0), "target": sum(1 for d in tgt["invoices"] for f in ("subtotal", "tax", "total") if dec(d[f]) < 0)},
    "invoices.total_eq_subtotal_plus_tax_minus_credit_lines": {"source": dict(Counter(str(totals_hold_src(r)) for r in src["invoices"])), "target": dict(Counter(str(totals_hold_tgt(d)) for d in tgt["invoices"]))},
    "invoices.total_eq_subtotal_plus_tax": {"source": sum(1 for r in src["invoices"] if r["total"] == r["subtotal"] + r["tax"]), "target": sum(1 for d in tgt["invoices"] if dec(d["total"]) == dec(d["subtotal"]) + dec(d["tax"]))},
    "invoiceLines.lineType_domain": {"source": sorted({r["line_type"] for r in src["invoice_lines"]}), "target": sorted({e["lineType"] for d in tgt["invoices"] for e in d.get("invoiceLines", [])})},
    "invoiceLines.amount": {"source": mm([r["amount"] for r in src["invoice_lines"]]), "target": mm([e["amount"] for d in tgt["invoices"] for e in d.get("invoiceLines", [])])},
    "invoiceLines.amount_scale_gt_2_target": sum(1 for d in tgt["invoices"] for e in d.get("invoiceLines", []) if scale(e["amount"]) > 2),
    "invoiceLines.lineNo": {"source": mm([r["line_no"] for r in src["invoice_lines"]]), "target": mm([e["lineNo"] for d in tgt["invoices"] for e in d.get("invoiceLines", [])])},
    "invoiceLines.whitespace_in_text_target": sum(1 for d in tgt["invoices"] for e in d.get("invoiceLines", []) for f in ("lineType", "description") if e[f] != e[f].strip()),
    "dunningAttempts.scheduledFor": {"source": mm([r["scheduled_for"] for r in src["dunning_attempts"]]), "target": mm([e["scheduledFor"] for d in tgt["invoices"] for e in d.get("dunningAttempts", [])])},
    "dunningAttempts.scheduledFor_on_weekend": {"source": sum(1 for r in src["dunning_attempts"] if r["scheduled_for"].isoweekday() >= 6), "target": sum(1 for d in tgt["invoices"] for e in d.get("dunningAttempts", []) if e["scheduledFor"].astimezone(timezone.utc).isoweekday() >= 6)},
    "dunningAttempts.scheduledFor_before_invoice_issued": {"source": sum(1 for r in src["dunning_attempts"] if r["scheduled_for"] < inv_src[canon(r["invoice_id"])]["issued_at"].astimezone(timezone.utc).date()), "target": sum(1 for d in tgt["invoices"] for e in d.get("dunningAttempts", []) if e["scheduledFor"] < d["issuedAt"])},
    "dunningAttempts.status_domain": {"source": sorted({r["status"] for r in src["dunning_attempts"]}), "target": sorted({e["status"] for d in tgt["invoices"] for e in d.get("dunningAttempts", [])})},
    "dunningAttempts.attemptNo": {"source": mm([r["attempt_no"] for r in src["dunning_attempts"]]), "target": mm([e["attemptNo"] for d in tgt["invoices"] for e in d.get("dunningAttempts", [])])},
    "dunningAttempts.only_on_overdue_invoices": {"source": sum(1 for r in src["dunning_attempts"] if inv_src[canon(r["invoice_id"])]["status"] == "overdue"), "target": sum(1 for d in tgt["invoices"] if d["status"] == "overdue" for _ in d.get("dunningAttempts", []))},
    "notifications.sentAt": {"source": mm([r["sent_at"] for r in src["notifications"]]), "target": mm([d["sentAt"] for d in tgt["notifications"]])},
    "notifications.kind_whitespace_target": sum(1 for d in tgt["notifications"] if d["kind"] != d["kind"].strip()),
    "date_midnight_utc": {k: {"values": sum(1 for v in vs if v is not None), "non_midnight": sum(1 for v in vs if not_midnight(v)), "not_a_bson_date": sum(1 for v in vs if v is not None and not isinstance(v, datetime))} for k, vs in date_fields.items()},
    "timestamptz_fields": {k: {"source_sub_ms_precision_values": sum(1 for v in s if v is not None and v.microsecond % 1000), "target_values": sum(1 for v in t if v is not None),
                               "target_not_a_bson_date": sum(1 for v in t if v is not None and not isinstance(v, datetime)),
                               "target_multiset_equals_source_at_ms": sorted(canon(v) for v in s) == sorted(canon(v) for v in t),
                               "target_non_midnight": sum(1 for v in t if not_midnight(v))} for k, (s, t) in ts_fields.items()},
}

# overdue predicates the dunning procedures use, evaluated both sides for the recorded as_of dates
def overdue_src(as_of, grace):
    return sorted(canon(r["tenant_id"]) for r in src["invoices"] if r["status"] == "overdue" and r["issued_at"].astimezone(timezone.utc).date() <= as_of - __import__("datetime").timedelta(days=grace)) if grace else \
           sorted(canon(r["id"]) for r in src["invoices"] if r["status"] == "overdue" and r["issued_at"].astimezone(timezone.utc).date() < as_of)
def overdue_tgt(as_of, grace):
    return sorted(canon(d["tenantId"]) for d in tgt["invoices"] if d["status"] == "overdue" and d["issuedAt"].astimezone(timezone.utc).date() <= as_of - __import__("datetime").timedelta(days=grace)) if grace else \
           sorted(canon(d["_id"]) for d in tgt["invoices"] if d["status"] == "overdue" and d["issuedAt"].astimezone(timezone.utc).date() < as_of)
report["overdue_predicates"] = {}
for as_of in (date(2026, 2, 14), date(2026, 2, 17), date(2026, 2, 28)):
    a, b = overdue_src(as_of, 0), overdue_tgt(as_of, 0); c, d_ = overdue_src(as_of, 14), overdue_tgt(as_of, 14)
    report["overdue_predicates"][as_of.isoformat()] = {"fn_overdue_accounts_invoices": {"source": len(a), "target": len(b), "equal": a == b},
                                                      "sp_suspend_overdue_tenants": {"source": len(set(c)), "target": len(set(d_)), "equal": sorted(set(c)) == sorted(set(d_))}}

# write fence: the seven mapped collections only
expected = {c["collection"] for c in SPEC["collections"]}
report["write_fence"] = {"mapped_collections": sorted(expected),
                         "unexpected_collections_in_target_db": sorted(c for c in out["collections_in_target_db"] if c not in expected),
                         "mapped_collections_missing": sorted(c for c in expected if c not in out["collections_in_target_db"])}
out["probes"] = report
print(json.dumps(out, indent=1, default=str))
