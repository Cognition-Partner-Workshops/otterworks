"""Independent past-the-gate probes for wave 2 (usageEvents, ratingPeriods with the `rating`
subdocument) plus cross-unit references into the wave-1 collections.
Read-only on both sides. Prints aggregate JSON only (no row values)."""
import json, os
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
WAVE2 = ("usageEvents", "ratingPeriods")
COLS = {c["collection"]: c for c in SPEC["collections"] if c["collection"] in WAVE2}

pg_params = json.loads(os.environ["POSTGRESQL_RO_DSN"])
pg_params.pop("schema", "billing")
pg_params["dbname"] = pg_params.pop("database")
pg = psycopg.connect(**pg_params, row_factory=dict_row, autocommit=True, options="-c default_transaction_read_only=on")
db = MongoClient(os.environ["MONGODB_ATLAS_URI"], uuidRepresentation="standard", tz_aware=True)["billing_migration"]

out = {"collections_in_target_db": sorted(db.list_collection_names())}

src = {
    "usage_events": pg.execute("SELECT * FROM billing.usage_events ORDER BY id").fetchall(),
    "rating_periods": pg.execute("SELECT * FROM billing.rating_periods ORDER BY id").fetchall(),
    "rating_results": pg.execute("SELECT * FROM billing.rating_results ORDER BY id").fetchall(),
    "tenants": pg.execute("SELECT id FROM billing.tenants").fetchall(),
    "subscriptions": pg.execute("SELECT id, tenant_id FROM billing.subscriptions").fetchall(),
}
tgt = {name: list(db[name].find({}, sort=[("_id", 1)])) for name in WAVE2}

def canon(v):
    if isinstance(v, Decimal128):
        v = v.to_decimal()
    if isinstance(v, Decimal):
        return str(v.normalize()) if v != 0 else "0"
    if isinstance(v, datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc).isoformat(timespec="milliseconds")
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day, tzinfo=timezone.utc).isoformat(timespec="milliseconds")
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
    if isinstance(v, dict): return "object"
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
    want = [(tuple((k, int(o)) for k, o in ix["keys"]), bool(ix.get("unique", False))) for ix in spec.get("indexes", [])]
    have = [(tuple((k, int(o)) for k, o in info["key"]), bool(info.get("unique", False)))
            for iname, info in db[name].index_information().items() if iname != "_id_"]
    report[name]["indexes"] = {"spec": len(want), "present": len(have),
                              "missing": [list(map(list, w[0])) for w in want if w not in have],
                              "undeclared": [list(map(list, h[0])) for h in have if h not in want]}
    opts = next(db.list_collections(filter={"name": name})).get("options", {})
    report[name]["validator_present"] = "validator" in opts
    report[name]["validation_level"] = opts.get("validationLevel", "strict(default)")

# natural key (tenantId, periodStart) uniqueness, both sides
report["ratingPeriods"]["natural_key_tenantId_periodStart"] = {
    "source_dupes": sum(c - 1 for c in Counter((canon(r["tenant_id"]), canon(r["period_start"])) for r in src["rating_periods"]).values()),
    "target_dupes": sum(c - 1 for c in Counter((canon(d["tenantId"]), canon(d["periodStart"])) for d in tgt["ratingPeriods"]).values())}

# embed: ratingPeriods.rating is a 1:1 subdocument of rating_results keyed by period_id
emb = next(e for e in COLS["ratingPeriods"]["embeds"] if e["array_path"] == "rating")
child_fields = {f["source"]: f["target"] for f in emb["child_fields"]}
parent_key_fields = {f["source"]: f["target"] for f in emb.get("parent_key_fields", [])}
rr_by_period = Counter(canon(r["period_id"]) for r in src["rating_results"])
rr_src = {canon(r["period_id"]): r for r in src["rating_results"]}
sub_types, sub_diffs, sub_undeclared, pk_present = Counter(), [], Counter(), Counter()
presence = {"periods_with_rating": 0, "periods_without_rating": 0, "rating_is_array_not_subdocument": 0,
            "rating_present_but_no_source_result": 0, "rating_missing_but_source_result_exists": 0}
for d in tgt["ratingPeriods"]:
    pid = canon(d["_id"]); has_src = pid in rr_src
    sub = d.get("rating")
    if isinstance(sub, list):
        presence["rating_is_array_not_subdocument"] += 1
    if sub is None:
        presence["periods_without_rating"] += 1
        if has_src: presence["rating_missing_but_source_result_exists"] += 1
        continue
    presence["periods_with_rating"] += 1
    if not has_src:
        presence["rating_present_but_no_source_result"] += 1; continue
    r = rr_src[pid]
    for s, t in child_fields.items():
        sv, tv = canon(r[s]), canon(sub.get(t))
        sub_types[(t, bson_kind(sub.get(t)))] += 1
        if sv is None and t not in sub: continue
        if sv != tv: sub_diffs.append((pid, t))
    for s, t in parent_key_fields.items():
        if t in sub:
            pk_present[t] += 1
            if canon(r[s]) != canon(sub[t]): sub_diffs.append((pid, t))
    for k in sub:
        if k not in set(child_fields.values()) | set(parent_key_fields.values()):
            sub_undeclared[k] += 1
report["ratingPeriods"]["rating_subdocument"] = {
    "source_child_rows": len(src["rating_results"]),
    "source_results_per_period_distribution": dict(Counter(rr_by_period.values())),
    "source_periods_without_result": sum(1 for r in src["rating_periods"] if canon(r["id"]) not in rr_src),
    "orphan_source_results_without_period": sum(1 for r in src["rating_results"] if canon(r["period_id"]) not in {canon(p["id"]) for p in src["rating_periods"]}),
    **presence,
    "element_value_diffs": len(sub_diffs), "element_value_diff_fields": sorted({t for _, t in sub_diffs}),
    "element_bson_types": {f"{t}: {k}": v for (t, k), v in sub_types.items()},
    "parent_key_field_present_in_subdocument": dict(pk_present),
    "undeclared_subdocument_fields": dict(sub_undeclared),
    "period_id_is_md5_of_tenant_id_period_start_source": sum(1 for r in src["rating_periods"] if canon(r["id"]) == canon(UUID(__import__("hashlib").md5((str(r["tenant_id"]) + r["period_start"].isoformat()).encode()).hexdigest()))),
    "period_id_is_md5_of_tenant_id_period_start_target": sum(1 for d in tgt["ratingPeriods"] if canon(d["_id"]) == canon(UUID(__import__("hashlib").md5((str(d["tenantId"]) + d["periodStart"].date().isoformat()).encode()).hexdigest()))),
    "result_id_is_md5_of_period_id_source": sum(1 for r in src["rating_results"] if canon(r["id"]) == canon(UUID(__import__("hashlib").md5(str(r["period_id"]).encode()).hexdigest()))),
    "result_id_is_md5_of_period_id_target": sum(1 for d in tgt["ratingPeriods"] if isinstance(d.get("rating"), dict) and canon(d["rating"].get("id")) == canon(UUID(__import__("hashlib").md5(str(d["_id"]).encode()).hexdigest()))),
}

# cross-unit references into wave-1 collections (target) and the source tables
period_tenant_src = {canon(p["id"]): canon(p["tenant_id"]) for p in src["rating_periods"]}
tenant_ids_tgt = {canon(d["_id"]) for d in db.tenants.find({}, {"_id": 1})}
sub_tgt = {canon(d["_id"]): canon(d["tenantId"]) for d in db.subscriptions.find({}, {"_id": 1, "tenantId": 1})}
tenant_ids_src = {canon(r["id"]) for r in src["tenants"]}
sub_src = {canon(r["id"]): canon(r["tenant_id"]) for r in src["subscriptions"]}
report["cross_unit"] = {
    "wave1_counts_target": {c: db[c].estimated_document_count() for c in ("plans", "tenants", "subscriptions")},
    "wave1_counts_source": {r["t"]: r["n"] for r in pg.execute("SELECT 'plans' AS t, count(*) AS n FROM billing.plans UNION ALL SELECT 'tenants', count(*) FROM billing.tenants UNION ALL SELECT 'subscriptions', count(*) FROM billing.subscriptions").fetchall()},
    "usageEvents.tenantId_dangling_target": sum(1 for d in tgt["usageEvents"] if canon(d["tenantId"]) not in tenant_ids_tgt),
    "usage_events.tenant_id_dangling_source": sum(1 for r in src["usage_events"] if canon(r["tenant_id"]) not in tenant_ids_src),
    "ratingPeriods.tenantId_dangling_target": sum(1 for d in tgt["ratingPeriods"] if canon(d["tenantId"]) not in tenant_ids_tgt),
    "rating_periods.tenant_id_dangling_source": sum(1 for r in src["rating_periods"] if canon(r["tenant_id"]) not in tenant_ids_src),
    "rating.subscriptionId_dangling_target": sum(1 for d in tgt["ratingPeriods"] if isinstance(d.get("rating"), dict) and canon(d["rating"].get("subscriptionId")) not in sub_tgt),
    "rating_results.subscription_id_dangling_source": sum(1 for r in src["rating_results"] if canon(r["subscription_id"]) not in sub_src),
    "rating.subscriptionId_belongs_to_other_tenant_target": sum(1 for d in tgt["ratingPeriods"] if isinstance(d.get("rating"), dict) and sub_tgt.get(canon(d["rating"].get("subscriptionId"))) not in (None, canon(d["tenantId"]))),
    "rating_results.subscription_id_belongs_to_other_tenant_source": sum(1 for r in src["rating_results"] if sub_src.get(canon(r["subscription_id"])) != period_tenant_src.get(canon(r["period_id"]))),
    "tenants_with_usage_target": len({canon(d["tenantId"]) for d in tgt["usageEvents"]}),
    "tenants_with_usage_source": len({canon(r["tenant_id"]) for r in src["usage_events"]}),
    "tenants_with_periods_target": len({canon(d["tenantId"]) for d in tgt["ratingPeriods"]}),
    "tenants_with_periods_source": len({canon(r["tenant_id"]) for r in src["rating_periods"]}),
}

# period containment: usage events per rating period (tenant + occurred_at::date within period), both sides
def contained_src():
    rows = pg.execute("SELECT rp.id, count(u.id) AS n FROM billing.rating_periods rp LEFT JOIN billing.usage_events u ON u.tenant_id = rp.tenant_id AND u.occurred_at::date BETWEEN rp.period_start AND rp.period_end GROUP BY rp.id").fetchall()
    return {canon(r["id"]): r["n"] for r in rows}
def contained_tgt():
    res = {}
    for d in tgt["ratingPeriods"]:
        ps, pe = d["periodStart"].date(), d["periodEnd"].date()
        res[canon(d["_id"])] = sum(1 for u in tgt["usageEvents"] if canon(u["tenantId"]) == canon(d["tenantId"]) and ps <= u["occurredAt"].astimezone(timezone.utc).date() <= pe)
    return res
cs, ct = contained_src(), contained_tgt()
report["period_containment"] = {"periods": len(cs), "events_in_some_period_source": sum(cs.values()), "events_in_some_period_target": sum(ct.values()),
                                "per_period_mismatches": sum(1 for k in cs if cs[k] != ct.get(k))}

# boundaries and DATE / TIMESTAMPTZ representation on target
period_end_src = {canon(p["id"]): p["period_end"] for p in src["rating_periods"]}
def not_midnight(v):
    return isinstance(v, datetime) and (v.hour, v.minute, v.second, v.microsecond) != (0, 0, 0, 0)
def mm(vals):
    vals = [v.to_decimal() if isinstance(v, Decimal128) else v for v in vals if v is not None]
    return [canon(min(vals)), canon(max(vals))] if vals else None
date_fields = {"ratingPeriods.periodStart": [d.get("periodStart") for d in tgt["ratingPeriods"]],
               "ratingPeriods.periodEnd": [d.get("periodEnd") for d in tgt["ratingPeriods"]]}
midnight = {k: {"values": sum(1 for v in vs if v is not None), "non_midnight": sum(1 for v in vs if not_midnight(v)),
                "not_a_bson_date": sum(1 for v in vs if v is not None and not isinstance(v, datetime))} for k, vs in date_fields.items()}
midnight["all_midnight_utc"] = all(m["non_midnight"] == 0 and m["not_a_bson_date"] == 0 for m in midnight.values())
ts_fields = {"usageEvents.occurredAt": ([r["occurred_at"] for r in src["usage_events"]], [d.get("occurredAt") for d in tgt["usageEvents"]]),
             "ratingPeriods.rating.createdAt": ([r["created_at"] for r in src["rating_results"]], [d["rating"].get("createdAt") for d in tgt["ratingPeriods"] if isinstance(d.get("rating"), dict)])}
ts = {k: {"source_sub_ms_precision_values": sum(1 for v in s if v is not None and v.microsecond % 1000), "target_values": sum(1 for v in t if v is not None),
          "target_not_a_bson_date": sum(1 for v in t if v is not None and not isinstance(v, datetime)),
          "target_multiset_equals_source_at_ms": sorted(canon(v) for v in s) == sorted(canon(v) for v in t)} for k, (s, t) in ts_fields.items()}
report["boundaries"] = {
    "ratingPeriods.periodStart": {"source": mm([r["period_start"] for r in src["rating_periods"]]), "target": mm([d["periodStart"] for d in tgt["ratingPeriods"]])},
    "ratingPeriods.periodEnd": {"source": mm([r["period_end"] for r in src["rating_periods"]]), "target": mm([d["periodEnd"] for d in tgt["ratingPeriods"]])},
    "periodEnd_before_periodStart": {"source": sum(1 for r in src["rating_periods"] if r["period_end"] < r["period_start"]), "target": sum(1 for d in tgt["ratingPeriods"] if d["periodEnd"] < d["periodStart"])},
    "usageEvents.occurredAt": {"source": mm([r["occurred_at"] for r in src["usage_events"]]), "target": mm([d["occurredAt"] for d in tgt["usageEvents"]])},
    "usageEvents.units": {"source": mm([r["units"] for r in src["usage_events"]]), "target": mm([d["units"] for d in tgt["usageEvents"]])},
    "usageEvents.units_sum": {"source": sum(r["units"] for r in src["usage_events"]), "target": sum(d["units"] for d in tgt["usageEvents"])},
    "usageEvents.kind_domain": {"source": sorted({r["kind"] for r in src["usage_events"]}), "target": sorted({d["kind"] for d in tgt["usageEvents"]})},
    "usageEvents.kind_trailing_or_leading_space_target": sum(1 for d in tgt["usageEvents"] if d["kind"] != d["kind"].strip()),
    "rating.overageAmount": {"source": mm([r["overage_amount"] for r in src["rating_results"]]), "target": mm([d["rating"]["overageAmount"] for d in tgt["ratingPeriods"] if isinstance(d.get("rating"), dict)])},
    "rating.overageAmount_scale_gt_2_target": sum(1 for d in tgt["ratingPeriods"] if isinstance(d.get("rating"), dict) and -d["rating"]["overageAmount"].to_decimal().as_tuple().exponent > 2),
    "rating.int_fields_negative_target": sum(1 for d in tgt["ratingPeriods"] if isinstance(d.get("rating"), dict) for f in ("usedUnits", "quotaUnits", "rolloverUnits", "billableUnits") if d["rating"].get(f, 0) < 0),
    "rating.rolloverUnits_eq_max_quota_minus_used_0": {"source": sum(1 for r in src["rating_results"] if r["rollover_units"] == max(r["quota_units"] - r["used_units"], 0)), "target": sum(1 for d in tgt["ratingPeriods"] if isinstance(d.get("rating"), dict) and d["rating"]["rolloverUnits"] == max(d["rating"]["quotaUnits"] - d["rating"]["usedUnits"], 0))},
    "rating.createdAt_eq_periodEnd": {"source": sum(1 for r in src["rating_results"] if canon(r["created_at"]) == canon(period_end_src.get(canon(r["period_id"])))),
                                     "target": sum(1 for d in tgt["ratingPeriods"] if isinstance(d.get("rating"), dict) and d["rating"]["createdAt"] == d["periodEnd"])},
    "date_midnight_utc": midnight,
    "timestamptz_fields": ts,
}

# write fence: wave-2 write targets plus wave-1 collections only
expected = {"plans", "tenants", "subscriptions", "usageEvents", "ratingPeriods"}
report["write_fence"] = {"unexpected_collections_in_target_db": sorted(c for c in out["collections_in_target_db"] if c not in expected),
                         "later_wave_collections_present": sorted(c for c in out["collections_in_target_db"] if c in {"invoices", "notifications"}),
                         "source_later_wave_row_counts": {r["t"]: r["n"] for r in pg.execute("SELECT 'invoices' AS t, count(*) AS n FROM billing.invoices UNION ALL SELECT 'invoice_lines', count(*) FROM billing.invoice_lines UNION ALL SELECT 'dunning_attempts', count(*) FROM billing.dunning_attempts UNION ALL SELECT 'notifications', count(*) FROM billing.notifications").fetchall()}}
out["probes"] = report
print(json.dumps(out, indent=1, default=str))
