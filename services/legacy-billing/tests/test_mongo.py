"""Mongo backend (U1) against the mongo:7 fixture; skipped unless BILLING_MONGO_FIXTURE_URI is set.

Seeds the static rows of db/oracle/schema/03_seed_static.sql in the migrated shape and replays
the plans scenarios PLANS-001..005 (procs/transcripts/plans) plus the PKG_OW_UTIL helpers.
"""
import os
import sys
from datetime import date, datetime, timezone
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


def test_change_plan_same_day_closes_same_day_subscription(mongo):
    # Oracle backend: UPDATE ... SET ends_on = eff - 1 WHERE ends_on IS NULL AND starts_on = eff
    # (hist pre-image via TRG_SUBSCRIPTIONS_HIST), then sp_change_plan inserts the new row.
    mongo.change_plan(T[1], P[2], "2026-01-01")
    assert _rows(mongo, T[1]) == [(P[1], "2026-01-01", "2025-12-31", "active"), (P[2], "2026-01-01", None, "active")]
    (hist,) = mongo.db().subscriptions_hist.find({"subscriptionId": S[1]})
    assert hist["histOp"] == "UPD" and hist["planId"] == P[1] and "endsOn" not in hist
    (entitled,) = mongo.entitlement(T[1], "2026-01-01")
    assert entitled["plan_code"] == "GROWTH" and entitled["effective_on"] == "2026-01-01"
    # Repeating the same change collides on the deterministic subscription id and rolls back.
    with pytest.raises(mongo.DuplicateKeyError):
        mongo.change_plan(T[1], P[2], "2026-01-01")
    assert _rows(mongo, T[1]) == [(P[1], "2026-01-01", "2025-12-31", "active"), (P[2], "2026-01-01", None, "active")]
    assert mongo.db().subscriptions_hist.count_documents({"subscriptionId": S[1]}) == 1


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


# ---------------------------------------------------------------- U4 invoicing

FEB = (date(2026, 2, 1), date(2026, 2, 28))


@pytest.fixture
def mongo_u4(mongo):
    from bson import Decimal128

    db = mongo.db()
    for name in ("usage_events", "rating_periods", "credit_notes", "invoices"):
        db.drop_collection(name)
    db.codes.insert_many([
        {"_id": {"codeType": "INV_STATUS", "codeVal": 20}, "codeDesc": "issued"},
        {"_id": {"codeType": "INV_STATUS", "codeVal": 30}, "codeDesc": "paid"},
    ])
    db.usage_events.insert_many([
        {"_id": "u1", "tenantId": T[1], "units": 100, "occurredAt": day("2026-02-03")},
        {"_id": "u2", "tenantId": T[1], "units": 100, "occurredAt": day("2026-02-28")},
        {"_id": "u3", "tenantId": T[1], "units": 12, "occurredAt": day("2026-02-15")},
        {"_id": "u4", "tenantId": T[1], "units": 999, "occurredAt": day("2026-03-01")},
    ])
    db.credit_notes.insert_many([
        {"_id": "n-newer", "tenantId": T[1], "issuedOn": day("2026-01-10"), "amount": Decimal128("3.00"), "remainingAmount": Decimal128("3.00")},
        {"_id": "n-older", "tenantId": T[1], "issuedOn": day("2026-01-05"), "amount": Decimal128("100.00"), "remainingAmount": Decimal128("100.00")},
        {"_id": "n-spent", "tenantId": T[1], "issuedOn": day("2025-12-01"), "amount": Decimal128("50.00"), "remainingAmount": Decimal128("0.00")},
    ])
    db.invoices.insert_one({
        "_id": "inv-seeded", "tenantId": T[4], "periodId": "p-seeded", "issuedAt": day("2026-01-31"),
        "subtotal": Decimal128("161.29"), "tax": Decimal128("0.00"), "total": Decimal128("161.29"), "statusCd": 30,
        "lines": [
            {"id": "l2", "lineNo": 2, "lineType": "usage", "description": "usage overage", "amount": Decimal128("12.29")},
            {"id": "l1", "lineNo": 1, "lineType": "plan", "description": "GROWTH", "amount": Decimal128("149.00")},
        ],
    })
    db.rating_periods.insert_one({"_id": "p-seeded", "tenantId": T[4], "periodStart": day("2026-01-01"), "periodEnd": day("2026-01-31")})
    return mongo


def _by_type(lines):
    return {line["line_type"] + ("" if line["line_type"] != "tax" else line["description"]): line for line in lines}


def test_invoice_preview_five_lines_rated_and_taxed(mongo_u4):
    lines = mongo_u4.invoice_preview(T[1], *FEB)
    assert [(l["line_no"], l["line_type"], l["description"]) for l in lines] == [
        ("1", "plan", "STARTER"), ("2", "usage", "usage overage"), ("3", "tax", "regional tax"),
        ("4", "tax", "local tax"), ("5", "credit", "credit notes"),
    ]
    by = _by_type(lines)
    assert by["plan"]["amount"] == "49" and by["plan"]["total"] == "49"
    # 212 units in period (the March event is outside), 100 included: 101 at 0.05 + 11 at 0.075 = 5.875 -> 5.88
    assert by["usage"]["amount"] == "5.88"
    # (49 + 5.88) * 0.0825 = 4.5276, split in two unrounded halves as fn_invoice_preview does
    assert by["taxregional tax"]["amount"] == by["taxlocal tax"]["amount"] == "2.2638"
    # 103.00 of open credit, capped at ROUND(49 + 5.88 + 4.5276, 2) = 59.41; spent notes do not count
    assert by["credit"]["amount"] == "0" and by["credit"]["credit_applied"] == "59.41" and by["credit"]["total"] == "-59.41"
    assert all(l["tax_amount"] == "0" for l in lines)


def test_invoice_preview_without_usage_or_credit(mongo_u4):
    by = _by_type(mongo_u4.invoice_preview(T[4], *FEB))
    assert (by["plan"]["amount"], by["usage"]["amount"], by["credit"]["total"]) == ("49", "0", "0")
    assert by["taxregional tax"]["amount"] == "2.02125"


def test_invoice_preview_tax_exempt_tenant(mongo_u4):
    mongo_u4.db().tenants.update_one({"_id": T[4]}, {"$set": {"taxExemptYn": "Y"}})
    by = _by_type(mongo_u4.invoice_preview(T[4], *FEB))
    assert by["taxregional tax"]["amount"] == by["taxlocal tax"]["amount"] == "0"


def test_issue_invoice_is_deterministic_rebuilds_lines_and_burns_credit_oldest_first(mongo_u4):
    from bson import Decimal128

    db = mongo_u4.db()
    mongo_u4.issue_invoice(T[1], *FEB)
    period_id = mongo_u4.f_md5_uuid(f"{T[1]}2026-02-01")
    invoice_id = mongo_u4.f_md5_uuid(f"{period_id}invoice")
    invoice = db.invoices.find_one({"_id": invoice_id})
    assert invoice["tenantId"] == T[1] and invoice["periodId"] == period_id and invoice["statusCd"] == 20
    # sp_issue_invoice sums the two rounded tax lines (2.26 + 2.26) but caps the credit on the
    # unrounded tax (59.41), so the Oracle total for a fully covered invoice here is -0.01
    assert (invoice["subtotal"], invoice["tax"], invoice["total"]) == (Decimal128("54.88"), Decimal128("4.52"), Decimal128("-0.01"))
    assert [(l["lineNo"], l["lineType"], l["amount"]) for l in invoice["lines"]] == [
        (1, "plan", Decimal128("49.00")), (2, "usage", Decimal128("5.88")), (3, "tax", Decimal128("2.26")),
        (4, "tax", Decimal128("2.26")), (5, "credit", Decimal128("-59.41")),
    ]
    assert all(isinstance(l["amount"], Decimal128) for l in invoice["lines"])
    assert len({l["id"] for l in invoice["lines"]}) == 5
    remaining = {n["_id"]: n["remainingAmount"] for n in db.credit_notes.find({"tenantId": T[1]})}
    assert remaining == {"n-older": Decimal128("40.59"), "n-newer": Decimal128("3.00"), "n-spent": Decimal128("0.00")}

    period = db.rating_periods.find_one({"_id": period_id})
    assert period["tenantId"] == T[1] and period["periodStart"] == day("2026-02-01") and period["periodEnd"] == day("2026-02-28")
    assert period["result"]["usedUnits"] == 212 and period["result"]["billableUnits"] == 112
    assert period["result"]["overageAmount"] == Decimal128("5.88") and period["result"]["subscriptionId"] == S[1]
    assert db.billing_audit_log.count_documents({"module": "INVOICING", "message": {"$regex": f"issued invoice={invoice_id} total=-0\\.01$"}}) == 1

    mongo_u4.issue_invoice(T[1], *FEB)
    assert db.invoices.count_documents({"tenantId": T[1]}) == 1
    again = db.invoices.find_one({"_id": invoice_id})
    assert again["statusCd"] == 20 and len(again["lines"]) == 5
    assert again["total"] == Decimal128("15.81"), "43.59 of credit left against 59.40 of charges"
    assert {n["_id"]: n["remainingAmount"] for n in db.credit_notes.find({"tenantId": T[1]})} == {
        "n-older": Decimal128("0.00"), "n-newer": Decimal128("0.00"), "n-spent": Decimal128("0.00")}


def test_issue_invoice_without_covering_plan_rolls_back(mongo_u4):
    db = mongo_u4.db()
    with pytest.raises(ValueError, match="no covering plan"):
        mongo_u4.issue_invoice(T[9], *FEB)
    assert db.invoices.count_documents({"tenantId": T[9]}) == 0
    assert db.rating_periods.count_documents({"tenantId": T[9]}) == 0


def test_invoice_lines_and_listing(mongo_u4):
    assert mongo_u4.invoice_lines("inv-seeded") == [
        {"line_no": "1", "line_type": "plan", "description": "GROWTH", "amount": "149"},
        {"line_no": "2", "line_type": "usage", "description": "usage overage", "amount": "12.29"},
    ]
    assert mongo_u4.invoice_lines("missing") == []
    assert mongo_u4.invoice_owned("inv-seeded", T[4]) is True
    assert mongo_u4.invoice_owned("inv-seeded", T[1]) is False

    mongo_u4.issue_invoice(T[4], *FEB)
    listing = mongo_u4.invoices_for_tenant(T[4])
    assert [(i["period_start"], i["period_end"], i["status"]) for i in listing] == [
        ("2026-02-01", "2026-02-28", "issued"), ("2026-01-01", "2026-01-31", "paid")]
    assert (listing[0]["subtotal"], listing[0]["tax"], listing[0]["total"]) == ("49", "4.04", "53.04")
    assert listing[1]["invoice_id"] == "inv-seeded" and "lines" not in listing[1]
    assert mongo_u4.invoices_for_tenant(T[1]) == []
