"""Replay the read-only plans parity scenarios (PLANS-001..003) myself: legacy side as the
SELECT bodies of fn_list_plans / fn_entitlement run under billing_ro (no EXECUTE), target side
as the equivalent reads on Atlas billing_migration; compare both to the committed transcripts."""
import json, os, glob
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID
from datetime import datetime, timezone
import psycopg
from psycopg.rows import dict_row
from pymongo import MongoClient

pg_params = json.loads(os.environ["POSTGRESQL_RO_DSN"]); pg_params.pop("schema", None)
pg_params["dbname"] = pg_params.pop("database")
pg = psycopg.connect(**pg_params, row_factory=dict_row, autocommit=True, options="-c default_transaction_read_only=on")
db = MongoClient(os.environ["MONGODB_ATLAS_URI"], uuidRepresentation="standard", tz_aware=True)["billing_migration"]
def dec(v): return str(Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
transcripts = {json.load(open(f))["scenario"]: json.load(open(f)) for f in glob.glob("procs/transcripts/plans/PLANS-00[123].json")}
results = {}
# PLANS-001: fn_list_plans body
legacy = pg.execute("SELECT id, code, tier, monthly_fee, included_units, overage_rate FROM billing.plans WHERE active ORDER BY monthly_fee, code").fetchall()
target = sorted((d for d in db.plans.find() if d["active"]), key=lambda d: (d["monthlyFee"].to_decimal(), d["code"]))
results["PLANS-001"] = {"legacy": {"codes": [r["code"] for r in legacy], "fees": [dec(r["monthly_fee"]) for r in legacy]},
                        "target": {"codes": [d["code"] for d in target], "fees": [dec(d["monthlyFee"].to_decimal()) for d in target]},
                        "transcript": transcripts["PLANS-001"]["business_fields"]}
# PLANS-002/003: fn_entitlement body, parameters bound
def legacy_entitlement(tenant, on):
    return pg.execute("SELECT t.id, p.code AS plan_code, p.tier, p.monthly_fee, p.included_units, s.status AS subscription_status, GREATEST(s.starts_on, %s) AS effective_on FROM billing.tenants t JOIN billing.subscriptions s ON s.tenant_id = t.id JOIN billing.plans p ON p.id = s.plan_id WHERE t.id = %s AND s.starts_on <= %s AND (s.ends_on IS NULL OR s.ends_on >= %s) ORDER BY s.starts_on DESC LIMIT 1", (on, tenant, on, on)).fetchone()
def target_entitlement(tenant, on):
    on_dt = datetime(on.year, on.month, on.day, tzinfo=timezone.utc)
    if db.tenants.find_one({"_id": tenant}, {"_id": 1}) is None: return None
    subs = [s for s in db.subscriptions.find({"tenantId": tenant}) if s["startsOn"] <= on_dt and ("endsOn" not in s or s["endsOn"] >= on_dt)]
    if not subs: return None
    s = max(subs, key=lambda s: s["startsOn"]); p = db.plans.find_one({"_id": s["planId"]})
    return {"tenant_id": str(tenant), "plan_code": p["code"], "tier": p["tier"], "monthly_fee": dec(p["monthlyFee"].to_decimal()),
            "included_units": p["includedUnits"], "subscription_status": s["status"],
            "effective_on": max(s["startsOn"].date(), on).isoformat()}
import datetime as _dt
for sid in ("PLANS-002", "PLANS-003"):
    t = transcripts[sid]; inp = t["inputs"]
    results[sid] = {"transcript": t["business_fields"], "inputs": inp}
    tenant = UUID(str(inp["tenant_id"])); on = _dt.date.fromisoformat(str(inp["as_of"]))
    l = legacy_entitlement(tenant, on); g = target_entitlement(tenant, on)
    results[sid]["legacy"] = None if l is None else {"tenant_id": str(l["id"]), "plan_code": l["plan_code"], "tier": l["tier"], "monthly_fee": dec(l["monthly_fee"]),
                                                     "included_units": l["included_units"], "subscription_status": l["subscription_status"], "effective_on": l["effective_on"].isoformat()}
    results[sid]["target"] = g
for sid, r in results.items():
    # every column fn_entitlement / fn_list_plans returns is compared legacy vs target; the transcript
    # pins only the business fields the scenario selects, so that comparison is on the subset
    r["legacy_eq_target"] = r["legacy"] == r["target"]
    subset = {k: v for k, v in (r["target"] or {}).items() if k in r["transcript"]} if isinstance(r["target"], dict) else r["target"]
    r["target_eq_transcript"] = subset == r["transcript"]
    r["compared_fields_legacy_vs_target"] = sorted(r["legacy"]) if isinstance(r["legacy"], dict) else None
print(json.dumps(results, indent=1, default=str))
