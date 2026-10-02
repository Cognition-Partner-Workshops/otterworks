"""Mongo backend (U1, U3) against the mongo:7 fixture; skipped unless BILLING_MONGO_FIXTURE_URI is set.

Seeds the static rows of db/oracle/schema/03_seed_static.sql in the migrated shape and replays
the plans scenarios PLANS-001..005 (procs/transcripts/plans), the rating scenarios
RATING-001..008 (procs/transcripts/rating) plus the PKG_OW_UTIL helpers.
"""
import json
import os
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
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
        mongo.overdue("2026-02-28")


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
    assert [(ln["line_no"], ln["line_type"], ln["description"]) for ln in lines] == [
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
    assert all(ln["tax_amount"] == "0" for ln in lines)


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
    assert [(ln["lineNo"], ln["lineType"], ln["amount"]) for ln in invoice["lines"]] == [
        (1, "plan", Decimal128("49.00")), (2, "usage", Decimal128("5.88")), (3, "tax", Decimal128("2.26")),
        (4, "tax", Decimal128("2.26")), (5, "credit", Decimal128("-59.41")),
    ]
    assert all(isinstance(ln["amount"], Decimal128) for ln in invoice["lines"])
    assert len({ln["id"] for ln in invoice["lines"]}) == 5
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
    with pytest.raises(ValueError, match="no plan covers"):
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


# -------------------------------------------------- U3: usage + rating (PKG_RATING)

TRANSCRIPTS = Path(__file__).resolve().parents[3] / "procs" / "transcripts" / "rating"
E = [f"30000000-0000-0000-0000-0000000000{n:02d}" for n in range(0, 12)]
RP = [f"40000000-0000-0000-0000-00000000000{n}" for n in range(0, 4)]
RR = [f"50000000-0000-0000-0000-00000000000{n}" for n in range(0, 4)]


def stamp(text):
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


@pytest.fixture
def rating(mongo):
    """U3 rows of 03_seed_static.sql on top of the plans fixture (plans at their seeded rates)."""
    from bson import Decimal128, Int64

    db = mongo.db()
    for name in ("usage_events", "rating_periods"):
        db.drop_collection(name)
    db.codes.insert_many([
        {"_id": {"codeType": "USAGE_KIND", "codeVal": 1}, "codeDesc": "api"},
        {"_id": {"codeType": "USAGE_KIND", "codeVal": 2}, "codeDesc": "storage"},
        {"_id": {"codeType": "USAGE_KIND", "codeVal": 3}, "codeDesc": "compute"},
    ])
    db.plans.update_one({"_id": P[1]}, {"$set": {"overageRate": Decimal128("0.055")}})
    db.plans.update_one({"_id": P[3]}, {"$set": {"includedUnits": 2000, "overageRate": Decimal128("0.02")}})
    db.tenants.insert_many([{"_id": T[n], "name": f"Tenant {n}", "taxExemptYn": "N", "statusCd": 10} for n in (3, 6, 7, 8, 9)])
    db.subscriptions.insert_many(
        [{"_id": S[3], "tenantId": T[3], "planId": P[3], "startsOn": day("2026-01-01"), "statusCd": 10}]
        + [{"_id": S[n], "tenantId": T[n], "planId": P[1], "startsOn": day("2026-01-01"), "statusCd": 10} for n in (6, 7, 8, 9)]
    )
    db.usage_events.create_index([("tenantId", 1), ("occurredAt", -1), ("_id", -1)], name="ix_usage_events_tenant_occurred")
    db.rating_periods.create_index([("tenantId", 1), ("periodStart", 1)], unique=True, name="uq_rating_periods_tenant_start")
    events = [
        (E[1], T[1], "2026-02-10T10:00:00", 260, 1), (E[3], T[2], "2026-02-10T10:00:00", 700, 1),
        (E[4], T[3], "2026-02-10T10:00:00", 2201, 3), (E[5], T[4], "2026-02-05T10:00:00", 20, 1),
        (E[8], T[4], "2026-02-06T10:00:00", 30, 2), (E[6], T[5], "2026-02-01T10:00:00", 610, 1),
        (E[7], T[6], "2026-02-28T10:00:00", 201, 1), (E[9], T[7], "2026-02-10T10:00:00", 260, 1),
        (E[10], T[8], "2026-02-28T10:00:00", 202, 1), (E[11], T[9], "2026-02-10T10:00:00", 1, 1),
    ]
    db.usage_events.insert_many([
        {"_id": i, "tenantId": t, "occurredAt": stamp(at), "units": Int64(units), "kindCd": kind}
        for i, t, at, units, kind in events
    ])
    db.rating_periods.insert_many([
        {"_id": RP[n], "tenantId": T[1], "periodStart": day(start), "periodEnd": day(end),
         "result": {"id": RR[n], "subscriptionId": S[1], "usedUnits": Int64(0), "quotaUnits": Int64(100),
                    "rolloverUnits": Int64(100), "billableUnits": Int64(0), "overageAmount": Decimal128("0"),
                    "createdAt": day(end)}}
        for n, start, end in ((3, "2025-11-01", "2025-11-30"), (1, "2025-12-01", "2025-12-31"), (2, "2026-01-01", "2026-01-31"))
    ])
    return mongo


def transcript(scenario_id):
    return json.loads((TRANSCRIPTS / f"{scenario_id}.json").read_text())


def graded(row, fields):
    """business_fields the way procs/harness grades them: integers as int, decimals at 2 places."""
    out = {}
    for name, value in fields.items():
        actual = row[name]
        out[name] = str(Decimal(actual).quantize(Decimal("0.01"))) if isinstance(value, str) else int(actual)
    return out


@pytest.mark.parametrize("scenario_id, tenant", [
    ("RATING-001", 7), ("RATING-002", 1), ("RATING-003", 2), ("RATING-004", 6), ("RATING-005", 8), ("RATING-006", 3),
])
def test_rating_001_006_usage_rating(rating, scenario_id, tenant):
    expected = transcript(scenario_id)["business_fields"]
    (row,) = rating.usage_rating(T[tenant], "2026-02-01", "2026-02-28")
    assert graded(row, expected) == expected
    assert row["tenant_id"] == T[tenant] and (row["period_start"], row["period_end"]) == ("2026-02-01", "2026-02-28")
    assert all(isinstance(row[k], str) for k in ("used_units", "quota_units", "billable_units", "overage_amount"))


def test_rating_003_suspension_prorates_from_oracle_rounding(rating):
    (row,) = rating.usage_rating(T[2], "2026-02-01", "2026-02-28")
    assert (row["used_units"], row["quota_units"], row["billable_units"]) == ("700", "500", "100")
    assert row["overage_amount"] == "4.37"  # 8.73 * 14/28 = 4.365 -> ROUND half up, no trailing zeros
    (row,) = rating.usage_rating(T[1], "2026-02-01", "2026-02-28")
    assert row["overage_amount"] == "0" and row["rollover_units"] == "200"  # min(2 * quota, 300 prior)


def test_rating_without_covering_plan_has_no_quota(rating):
    rows = rating.usage_rating(T[7], "2025-12-01", "2025-12-31")
    assert rows == [{"tenant_id": T[7], "period_start": "2025-12-01", "period_end": "2025-12-31", "used_units": "0",
                     "quota_units": None, "rollover_units": "0", "billable_units": "0", "first_tier_units": "0",
                     "second_tier_units": "0", "overage_amount": None}]
    with pytest.raises(ValueError):
        rating.finalize_rating(T[7], "2025-12-01", "2025-12-31")
    assert rating.db().rating_periods.count_documents({"tenantId": T[7]}) == 0


def test_rating_007_usage_summary(rating):
    expected = transcript("RATING-007")["business_fields"]
    rows = rating.usage_summary(T[4], "2026-02-01", "2026-02-28")
    assert [r["kind"] for r in rows] == expected["kinds"]
    assert [int(r["units"]) for r in rows] == expected["units"]
    assert rows == [{"kind": "api", "event_count": "1", "units": "20"}, {"kind": "storage", "event_count": "1", "units": "30"}]
    assert rating.usage_summary(T[4], "2026-03-01", "2026-03-31") == []


def test_rating_008_finalize_rating(rating):
    from bson import Decimal128, Int64

    expected = transcript("RATING-008")
    period_id = rating.finalize_rating(T[1], "2026-02-01", "2026-02-28")
    assert period_id == rating.f_md5_uuid(f"{T[1]}2026-02-01")
    doc = rating.db().rating_periods.find_one({"_id": period_id})
    assert (doc["tenantId"], doc["periodStart"], doc["periodEnd"]) == (T[1], day("2026-02-01"), day("2026-02-28"))
    result = doc["result"]
    assert result == {
        "id": rating.f_md5_uuid(period_id), "subscriptionId": S[1], "usedUnits": 260, "quotaUnits": 100,
        "rolloverUnits": 0, "billableUnits": 0, "overageAmount": Decimal128("0"), "createdAt": day("2026-02-28"),
    }
    assert all(isinstance(result[k], Int64) for k in ("usedUnits", "quotaUnits", "rolloverUnits", "billableUnits"))
    probe = [{"used_units": int(result["usedUnits"]), "quota_units": int(result["quotaUnits"]),
              "rollover_units": int(result["rolloverUnits"]), "billable_units": int(result["billableUnits"]),
              "overage_amount": str(result["overageAmount"].to_decimal().quantize(Decimal("0.01")))}]
    assert probe == expected["probes"]["rating_result"]
    assert [a["message"] for a in rating.db().billing_audit_log.find({"module": "RATING"})][-1] == f"finalized period={period_id}"


def test_finalize_rating_rerun_updates_in_place(rating):
    from bson import Int64

    period_id = rating.finalize_rating(T[1], "2026-02-01", "2026-02-28")
    rating.db().usage_events.insert_one(
        {"_id": E[0], "tenantId": T[1], "occurredAt": stamp("2026-02-20T10:00:00"), "units": Int64(100), "kindCd": 1})
    assert rating.finalize_rating(T[1], "2026-02-01", "2026-02-27") == period_id
    assert rating.db().rating_periods.count_documents({"tenantId": T[1], "periodStart": day("2026-02-01")}) == 1
    doc = rating.db().rating_periods.find_one({"_id": period_id})
    assert doc["periodEnd"] == day("2026-02-27")
    assert (doc["result"]["usedUnits"], doc["result"]["billableUnits"]) == (360, 60)
    assert doc["result"]["id"] == rating.f_md5_uuid(period_id) and doc["result"]["createdAt"] == day("2026-02-28")


def test_finalize_rating_joins_callers_transaction(rating):
    client = rating.client()
    with client.start_session() as session:
        session.start_transaction()
        period_id = rating.finalize_rating(T[6], "2026-02-01", "2026-02-28", session=session)
        assert rating.db().rating_periods.find_one({"_id": period_id}) is None  # not visible outside the txn
        session.abort_transaction()
    assert rating.db().rating_periods.count_documents({"tenantId": T[6]}) == 0
    with client.start_session() as session:
        with session.start_transaction():
            rating.finalize_rating(T[6], "2026-02-01", "2026-02-28", session=session)
    doc = rating.db().rating_periods.find_one({"tenantId": T[6]})
    assert str(doc["result"]["overageAmount"]) == "5.56" and doc["result"]["billableUnits"] == 101


def test_record_usage_event_and_listing(rating):
    from bson import Int64

    new = "30000000-0000-0000-0000-00000000ffff"
    assert rating.record_usage_event(new, T[4], "2026-02-07T12:30:00Z", 5, "compute") == "recorded"
    assert rating.record_usage_event(new, T[4], "2026-02-07T12:30:00Z", 5, "compute") == "duplicate"
    stored = rating.db().usage_events.find_one({"_id": new})
    assert stored == {"_id": new, "tenantId": T[4], "occurredAt": stamp("2026-02-07T12:30:00"), "units": 5, "kindCd": 3}
    assert isinstance(stored["units"], Int64)
    with pytest.raises(rating.UsageEventRejected):
        rating.record_usage_event("30000000-0000-0000-0000-00000000fffe", T[4], "2026-02-07T12:30:00Z", 5, "bandwidth")
    with pytest.raises(rating.UsageEventRejected):
        rating.record_usage_event("30000000-0000-0000-0000-00000000fffe", T[4], "2026-02-07T12:30:00Z", 0, "api")
    assert rating.usage_events(T[4], "2026-02-01", "2026-02-28") == [
        {"id": new, "occurred_at": "2026-02-07T12:30:00", "units": "5", "kind": "compute"},
        {"id": E[8], "occurred_at": "2026-02-06T10:00:00", "units": "30", "kind": "storage"},
        {"id": E[5], "occurred_at": "2026-02-05T10:00:00", "units": "20", "kind": "api"},
    ]
    assert rating.usage_events(T[4], "2026-02-01", "2026-02-28", limit=1) == [
        {"id": new, "occurred_at": "2026-02-07T12:30:00", "units": "5", "kind": "compute"}]
    assert rating.usage_summary(T[4], "2026-02-01", "2026-02-28")[1] == {"kind": "compute", "event_count": "1", "units": "5"}
