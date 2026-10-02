"""Mongo backend (U1) against the mongo:7 fixture; skipped unless BILLING_MONGO_FIXTURE_URI is set.

Seeds the static rows of db/oracle/schema/03_seed_static.sql in the migrated shape and replays
the plans scenarios PLANS-001..005 (procs/transcripts/plans) plus the PKG_OW_UTIL helpers.
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

FIXTURE_URI = os.getenv("BILLING_MONGO_FIXTURE_URI")
pytestmark = pytest.mark.skipif(not FIXTURE_URI, reason="BILLING_MONGO_FIXTURE_URI not set")

T = [f"00000000-0000-0000-0000-00000000000{n}" for n in range(0, 10)]
P = [f"10000000-0000-0000-0000-00000000000{n}" for n in range(0, 4)]
S = [f"20000000-0000-0000-0000-00000000000{n}" for n in range(0, 10)]


def day(text):
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


@pytest.fixture
def mongo(monkeypatch):
    from bson import Decimal128

    monkeypatch.setenv("BILLING_BACKEND", "mongo")
    monkeypatch.setenv("MONGODB_ATLAS_URI", FIXTURE_URI)
    monkeypatch.setenv("MONGODB_DATABASE", "ow_tp_billing_pytest")
    from backends import mongo as backend

    backend._client = None
    db = backend.db()
    for name in ("codes", "tenants", "plans", "subscriptions", "subscriptions_hist", "billing_audit_log"):
        db.drop_collection(name)
    db.codes.insert_many([
        {"_id": {"codeType": "TENANT_STATUS", "codeVal": 10}, "codeDesc": "active"},
        {"_id": {"codeType": "TENANT_STATUS", "codeVal": 20}, "codeDesc": "suspended"},
        {"_id": {"codeType": "SUB_STATUS", "codeVal": 30}, "codeDesc": "cancelled"},
    ])
    db.plans.insert_many([
        {"_id": P[1], "code": "STARTER", "tierCd": 1, "monthlyFee": Decimal128("49.00"), "includedUnits": 100,
         "overageRate": Decimal128("0.050000"), "activeYn": "Y"},
        {"_id": P[2], "code": "GROWTH", "tierCd": 2, "monthlyFee": Decimal128("149.00"), "includedUnits": 500,
         "overageRate": Decimal128("0.035000"), "activeYn": "Y"},
        {"_id": P[3], "code": "SCALE", "tierCd": 3, "monthlyFee": Decimal128("499.00"), "includedUnits": 5000,
         "overageRate": Decimal128("0.020000"), "activeYn": "Y"},
    ])
    db.tenants.create_index("name", unique=True, name="uq_tenants_name")
    db.tenants.insert_many([
        {"_id": T[1], "name": "Tenant One", "taxExemptYn": "N", "statusCd": 10},
        {"_id": T[2], "name": "Tenant Two", "taxExemptYn": "N", "statusCd": 10},
        {"_id": T[4], "name": "Tenant Four", "taxExemptYn": "N", "statusCd": 10},
        {"_id": T[5], "name": "Tenant Five", "taxExemptYn": "N", "statusCd": 10},
    ])
    db.subscriptions.insert_many([
        {"_id": S[1], "tenantId": T[1], "planId": P[1], "startsOn": day("2026-01-01"), "statusCd": 10},
        {"_id": S[2], "tenantId": T[2], "planId": P[2], "startsOn": day("2026-01-01"), "statusCd": 20,
         "suspendedOn": day("2026-02-15")},
        {"_id": S[4], "tenantId": T[4], "planId": P[1], "startsOn": day("2026-01-01"), "statusCd": 10},
        {"_id": S[5], "tenantId": T[5], "planId": P[3], "startsOn": day("2026-01-01"), "statusCd": 30},
    ])
    yield backend
    backend.client().drop_database("ow_tp_billing_pytest")


def test_plans_001_catalog(mongo):
    plans = mongo.list_plans()
    assert [p["code"] for p in plans] == ["STARTER", "GROWTH", "SCALE"]
    assert [p["monthly_fee"] for p in plans] == ["49.00", "149.00", "499.00"]
    assert plans[1] == {"plan_id": P[2], "code": "GROWTH", "tier": "growth", "monthly_fee": "149.00",
                        "included_units": "500", "overage_rate": "0.035000"}
    audit = list(mongo.db().billing_audit_log.find())
    assert [(a["module"], a["message"]) for a in audit] == [("PLANS", "fn_list_plans")]
    assert isinstance(audit[0]["_id"], int) and audit[0]["loggedAt"].tzinfo is not None


def test_plans_002_003_entitlement(mongo):
    (one,) = mongo.entitlement(T[1], "2026-02-28")
    assert one == {"tenant_id": T[1], "plan_code": "STARTER", "tier": "starter", "monthly_fee": "49.00",
                   "included_units": "100", "subscription_status": "active", "effective_on": "2026-02-28"}
    (two,) = mongo.entitlement(T[2], "2026-02-28")
    assert (two["plan_code"], two["tier"], two["included_units"], two["subscription_status"]) == (
        "GROWTH", "growth", "500", "suspended")
    assert mongo.entitlement(T[1], "2025-12-31") == []
    assert mongo.entitlement("nobody", "2026-02-28") == []


def _rows(mongo, tenant_id):
    return [
        (d.get("planId"), d["startsOn"].date().isoformat(), d["endsOn"].date().isoformat() if d.get("endsOn") else None,
         mongo.SUBSCRIPTION_STATUSES[d["statusCd"]])
        for d in mongo.db().subscriptions.find({"tenantId": tenant_id}).sort("startsOn", 1)
    ]


def test_plans_004_change_plan(mongo):
    mongo.change_plan(T[1], P[2], "2026-03-01")
    assert _rows(mongo, T[1]) == [(P[1], "2026-01-01", "2026-02-28", "active"), (P[2], "2026-03-01", None, "active")]
    new = mongo.db().subscriptions.find_one({"tenantId": T[1], "planId": P[2]})
    assert new["_id"] == mongo.f_md5_uuid(f"{T[1]}{P[2]}2026-03-01")
    assert "endsOn" not in new and "suspendedOn" not in new
    (hist,) = mongo.db().subscriptions_hist.find()
    assert hist["histOp"] == "UPD" and hist["subscriptionId"] == S[1] and hist["planId"] == P[1]
    assert hist["_id"] == 1 and "endsOn" not in hist and hist["statusCd"] == 10
    assert hist["histDate"].date() == datetime.now(timezone.utc).date()
    assert mongo.f_str2dt(hist["histDt"]) == hist["histDate"].date()
    audit = mongo.db().billing_audit_log.find_one()
    assert audit["message"] == f"sp_change_plan tenant={T[1]} plan={P[2]} eff=2026-03-01"


def test_plans_005_change_plan(mongo):
    mongo.change_plan(T[4], P[3], "2026-03-15")
    assert _rows(mongo, T[4]) == [(P[1], "2026-01-01", "2026-03-14", "active"), (P[3], "2026-03-15", None, "active")]


def test_change_plan_same_day_leaves_same_day_subscription_open(mongo):
    # sp_change_plan closes rows with starts_on < effective_on only, as the Oracle cursor does.
    mongo.change_plan(T[1], P[2], "2026-01-01")
    assert sorted(_rows(mongo, T[1])) == [(P[1], "2026-01-01", None, "active"), (P[2], "2026-01-01", None, "active")]
    assert mongo.db().subscriptions_hist.count_documents({}) == 0
    with pytest.raises(mongo.DuplicateKeyError):
        mongo.change_plan(T[1], P[2], "2026-01-01")


def test_cancelled_stays_cancelled(mongo):
    mongo.change_plan(T[5], P[1], "2026-04-01")
    assert _rows(mongo, T[5]) == [(P[3], "2026-01-01", "2026-03-31", "cancelled"), (P[1], "2026-04-01", None, "active")]


def test_ensure_tenant_bootstraps_cheapest_plan_once(mongo):
    assert mongo.ensure_tenant("new-tenant", "new@example.com") is True
    assert mongo.ensure_tenant("new-tenant", "new@example.com") is False
    tenant = mongo.db().tenants.find_one({"_id": "new-tenant"})
    assert tenant == {"_id": "new-tenant", "name": "new@example.com", "taxExemptYn": "N", "statusCd": 10}
    (sub,) = mongo.db().subscriptions.find({"tenantId": "new-tenant"})
    assert sub["planId"] == P[1] and sub["statusCd"] == 10 and "endsOn" not in sub
    assert mongo.ensure_tenant("another", "Tenant One") is False  # uq_tenants_name


def test_tenant_profile_and_customer(mongo):
    assert mongo.tenant_profile(T[1]) == [
        {"tenant_id": T[1], "name": "Tenant One", "status": "active", "tax_exempt": "N"}
    ]
    assert mongo.tenant_profile("missing") == []
    assert mongo.customer_summary(T[1]) is None


def test_util_helpers(mongo):
    assert mongo.f_md5_uuid("abc") == "90015098-3cd2-4fb0-d696-3f7d28e17f72"
    assert mongo.f_code_desc("TENANT_STATUS", 10) == "active"
    assert mongo.f_code_desc("TENANT_STATUS", 99) == "UNKNOWN(99)"
    assert mongo.f_code_desc("TENANT_STATUS", None) == "UNKNOWN(-1)"
    assert mongo.f_dt2str(datetime(2026, 3, 1)) == "01-MAR-26"
    assert mongo.f_str2dt("01-MAR-26").isoformat() == "2026-03-01"
    assert mongo.f_str2dt("31-FEB-26") is None and mongo.f_str2dt("garbage") is None
    assert mongo.f_str2dt("15-JUN-99").isoformat() == "1999-06-15"
    with pytest.raises(NotImplementedError):
        mongo.usage_rating(T[1], "2026-02-01", "2026-02-28")
