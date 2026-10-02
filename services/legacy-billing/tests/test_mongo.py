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
    for name in ("codes", "tenants", "plans", "subscriptions", "subscriptions_hist", "billing_audit_log",
                 "customers", "customers_hist"):
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
    db.customers.insert_one(_admin_customer())
    yield backend
    backend.client().drop_database("ow_tp_billing_pytest")


ADMIN_TENANT = "a0000000-0000-0000-0000-000000000001"
ADMIN_CUST = "40000000-0000-0000-0000-00000000a001"


def _admin_customer():
    """03_seed_static.sql's customer_master row and its four EAV rows in the migrated shape (U2)."""
    from bson import Decimal128, Int64

    def eav(n, name, value):
        return {"eavId": Int64(99000000000000 + n), "name": name, "value": value, "type": "STR",
                "createdDt": "20-FEB-26", "createdDate": day("2026-02-20"), "typed": value}

    return {
        "_id": ADMIN_CUST, "custSeqNo": Int64(100000), "tenantId": ADMIN_TENANT, "custNo": "OW-ADMIN-0001",
        "custName": "OtterWorks Admin", "custNameUpper": "OTTERWORKS ADMIN", "legalName": "OtterWorks Admin",
        "addrLine1": "1 OtterWorks Way", "city": "Springfield", "stateCd": "IL", "zip": "62701", "countryCd": "US",
        "phone1": "217-555-0100", "phone1TypeCd": 1, "email1": "admin@otterworks.dev",
        "signupDt": "01-JAN-26", "signupDate": day("2026-01-01"),
        "lastActivityDt": "20-FEB-26", "lastActivityDate": day("2026-02-20"),
        "statusCd": 1, "subStatusCd": 1, "custTypeCd": 1, "segmentCd": 1, "regionCd": 1,
        "taxExemptYn": "N", "creditHoldYn": "N", "dunningExemptYn": "N", "vipYn": "Y",
        "curBalAmt": Decimal128("149"), "pastDueAmt": Decimal128("0"), "ytdBilledAmt": Decimal128("149"),
        "ltdBilledAmt": Decimal128("149"), "ytdPaidAmt": Decimal128("149"), "creditLimitAmt": Decimal128("5000"),
        "createdBy": "SEED", "createdDt": day("2026-01-01"), "updatedBy": "SEED", "updatedDt": day("2026-02-20"),
        "rowVersionNo": 1,
        "attributes": [eav(1, "TAX_REGION_OVERRIDE", "US-IL"), eav(2, "tax_region_override", "us-il"),
                       eav(3, "PORTAL_THEME", "dark"), eav(4, "LEGACY_TIER", "priority")],
    }


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


# ------------------------------------------------------------------ U2 customers


def test_customer_summary_renders_like_oracle(mongo):
    assert mongo.customer_summary(ADMIN_TENANT) == {
        "cust_no": "OW-ADMIN-0001", "cust_name": "OtterWorks Admin", "cur_bal_amt": "149",
        "past_due_amt": "0", "credit_hold_yn": "N",
    }
    assert mongo.customer_summary("missing") is None


def test_customer_is_select_star_plus_attributes(mongo):
    body = mongo.customer(ADMIN_TENANT)
    assert set(body) == set(mongo.CUSTOMER_COLUMNS) | {"attributes"}
    assert len(mongo.CUSTOMER_COLUMNS) == 155
    assert body["cust_id"] == ADMIN_CUST and body["cust_seq_no"] == "100000" and body["phone1_type_cd"] == "1"
    assert body["signup_dt"] == "01-JAN-26" and body["created_dt"] == "2026-01-01"
    assert body["credit_limit_amt"] == "5000" and body["addr_line_2"] is None and body["udf_amt_10"] is None
    assert not {"signup_date", "signupDate", "related_acct_ids_list", "_id"} & set(body)
    assert [a["eav_id"] for a in body["attributes"]] == [str(99000000000000 + n) for n in (1, 2, 3, 4)]
    assert body["attributes"][1] == {
        "eav_id": "99000000000002", "entity_type": "CUSTOMER", "entity_id": ADMIN_CUST,
        "attr_name": "tax_region_override", "attr_value": "us-il", "attr_type": "STR", "created_dt": "20-FEB-26",
    }
    assert mongo.customer("missing") is None


def test_customer_picks_lowest_cust_seq_no(mongo):
    second = {**_admin_customer(), "_id": "second", "custSeqNo": 99999, "custNo": "OW-SECOND"}
    second.pop("attributes")
    mongo.db().customers.insert_one(second)
    assert mongo.customer_summary(ADMIN_TENANT)["cust_no"] == "OW-SECOND"
    assert mongo.customer(ADMIN_TENANT)["attributes"] == []


def test_customer_columns_match_mapping_spec(mongo):
    import json

    spec_path = Path(__file__).resolve().parents[3] / "migration" / "billing" / "mapping_spec.json"
    if not spec_path.exists():
        pytest.skip("mapping_spec.json not checked out")
    spec = json.loads(spec_path.read_text())
    customers = next(c for c in spec["collections"] if c["name"] == "customers")
    flat = {f["field"]: f["source"] for f in customers["fields"] if "(derived)" not in f["source"]}
    assert customers["_id"]["from"] == ["CUSTOMER_MASTER.CUST_ID"]
    assert {mongo._camel(c): f"CUSTOMER_MASTER.{c.upper()}" for c in mongo.CUSTOMER_COLUMNS if c != "cust_id"} == flat
    eav = customers["embedded"][0]
    assert eav["source_table"] == "ENTITY_ATTR_VALUE" and eav["path"] == "attributes"
    assert {f["source"].split(".")[1].lower() for f in eav["fields"] if "(derived)" not in f["source"]} == {
        "eav_id", "attr_name", "attr_value", "attr_type", "created_dt"}
    assert set(mongo.EAV_COLUMNS) == {"eav_id", "entity_type", "entity_id", "attr_name", "attr_value",
                                      "attr_type", "created_dt"}


def test_update_customer_writes_pre_image_in_the_same_transaction(mongo):
    import re

    from pymongo.errors import PyMongoError

    hist = mongo.db().customers_hist
    updated = mongo.update_customer(ADMIN_CUST, {"custName": "Renamed", "creditHoldYn": "Y"})
    assert updated["custName"] == "Renamed" and updated["creditHoldYn"] == "Y"
    assert mongo.customer_summary(ADMIN_TENANT)["credit_hold_yn"] == "Y"
    rows = list(hist.find())
    assert len(rows) == 1
    pre = rows[0]
    assert pre["_id"] == 1 and pre["histOp"] == "UPD" and pre["custId"] == ADMIN_CUST
    assert pre["custName"] == "OtterWorks Admin" and pre["creditHoldYn"] == "N" and "attributes" not in pre
    assert re.fullmatch(r"\d{2}-[A-Z]{3}-\d{2} \d{2}:\d{2}:\d{2}", pre["histDt"])
    assert pre["histDate"] == mongo._as_bson_date(mongo.f_str2dt(pre["histDt"]))
    assert pre["histDate"].time() == datetime.min.time()
    assert pre["signupDate"] == day("2026-01-01") and pre["curBalAmt"] == updated["curBalAmt"]

    assert mongo.update_customer("missing", {"custName": "x"}) is None
    with pytest.raises(PyMongoError):
        mongo.update_customer(ADMIN_CUST, {"$illegal": 1})
    assert hist.count_documents({}) == 1
    assert mongo.db().customers.find_one({"_id": ADMIN_CUST})["custName"] == "Renamed"


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


# ------------------------------------------------------------------------- U5: dunning + audit
# Seeds the dunning slice of 03_seed_static.sql (invoices 1-3, attempt 1 on invoice 2, the kind-2
# notification) on top of the U1 fixture and replays DUNNING-001..005 (procs/transcripts/dunning).

INV = [f"60000000-0000-0000-0000-00000000000{n}" for n in range(0, 4)]
PERIOD = "40000000-0000-0000-0000-000000000001"
DUNNING_TRANSCRIPTS = Path(__file__).resolve().parents[3] / "procs" / "transcripts" / "dunning"
DUN_STATUS = {10: "scheduled", 20: "sent", 30: "skipped"}


def transcript(scenario):
    import json

    return json.loads((DUNNING_TRANSCRIPTS / f"{scenario}.json").read_text())


@pytest.fixture
def dunning(mongo):
    from bson import Decimal128

    db = mongo.db()
    for name in ("invoices", "dunning_attempts", "notifications"):
        db.drop_collection(name)
    db.codes.insert_many([{"_id": {"codeType": "DUN_STATUS", "codeVal": k}, "codeDesc": v} for k, v in DUN_STATUS.items()])
    # 03_seed_static.sql: Tenant Two is suspended, Tenant Five active on GROWTH, Tenant Six active.
    db.tenants.update_one({"_id": T[2]}, {"$set": {"statusCd": 20}})
    db.tenants.insert_one({"_id": T[6], "name": "Tenant Six", "taxExemptYn": "N", "statusCd": 10})
    db.subscriptions.update_one({"_id": S[5]}, {"$set": {"planId": P[2], "statusCd": 10}})
    db.subscriptions.insert_one({"_id": S[6], "tenantId": T[6], "planId": P[1], "startsOn": day("2026-01-01"), "statusCd": 10})
    money = {"subtotal": Decimal128("149.00"), "tax": Decimal128("12.29"), "total": Decimal128("161.29")}
    db.invoices.insert_many([
        {"_id": INV[1], "tenantId": T[2], "periodId": PERIOD, "issuedAt": day("2026-02-01"), **money, "statusCd": 40, "lines": []},
        {"_id": INV[2], "tenantId": T[5], "periodId": PERIOD, "issuedAt": day("2026-02-13"), **money, "statusCd": 40, "lines": []},
        {"_id": INV[3], "tenantId": T[6], "periodId": PERIOD, "issuedAt": day("2026-02-28"), "subtotal": Decimal128("49.00"),
         "tax": Decimal128("4.04"), "total": Decimal128("53.04"), "statusCd": 20, "lines": []},
    ])
    db.dunning_attempts.create_index([("invoiceId", 1), ("attemptNo", 1)], unique=True, name="uq_dunning_attempts_invoice_attempt")
    db.dunning_attempts.create_index([("scheduledFor", -1), ("_id", -1)], name="ix_dunning_attempts_scheduled")
    db.dunning_attempts.insert_one({"_id": "80000000-0000-0000-0000-000000000001", "tenantId": T[5], "invoiceId": INV[2],
                                    "attemptNo": 1, "scheduledFor": day("2026-02-16"), "statusCd": 20})
    db.notifications.create_index([("tenantId", 1), ("kindCd", 1), ("sentAt", 1)], unique=True, name="uq_notifications_tenant_kind_sent")
    db.notifications.insert_one({"_id": "90000000-0000-0000-0000-000000000001", "tenantId": T[5], "kindCd": 2,
                                 "sentAt": day("2026-02-16T09:00:00")})
    return mongo


def _schedule_rows(mongo):
    return [
        {"attempt_no": d["attemptNo"], "invoice_id": d["invoiceId"], "scheduled_for": d["scheduledFor"].date().isoformat(),
         "status": DUN_STATUS[d["statusCd"]]}
        for d in mongo.db().dunning_attempts.find().sort([("invoiceId", 1), ("attemptNo", 1)])
    ]


def _suspension_notifications(mongo):
    return [
        {"id": d["_id"], "kind": "suspension", "sent_at": d["sentAt"].strftime("%Y-%m-%dT%H:%M:%SZ"), "tenant_id": d["tenantId"]}
        for d in mongo.db().notifications.find({"kindCd": 3}).sort([("tenantId", 1), ("sentAt", 1)])
    ]


def _audit(mongo):
    return [(a["module"], a["message"]) for a in mongo.db().billing_audit_log.find().sort("_id", 1)]


def test_dunning_001_overdue(dunning):
    rows = dunning.overdue("2026-02-28")
    expected = transcript("DUNNING-001")["business_fields"]
    assert [r["tenant_id"] for r in rows] == expected["tenant_ids"]
    assert [int(r["days_overdue"]) for r in rows] == expected["days_overdue"]
    assert rows[0] == {"tenant_id": T[2], "invoice_id": INV[1], "total": "161.29", "days_overdue": "27", "tenant_status": "suspended"}
    assert rows[1]["tenant_status"] == "active" and "lines" not in rows[1]
    # TO_CHAR(issued_at, 'YYYYMMDD') < TO_CHAR(as_of, 'YYYYMMDD'): the issue day itself is not overdue.
    assert [r["invoice_id"] for r in dunning.overdue("2026-02-13")] == [INV[1]]
    assert dunning.overdue("2026-02-01") == []
    dunning.db().tenants.delete_one({"_id": T[2]})
    assert dunning.overdue("2026-02-28")[0]["tenant_status"] == "UNKNOWN"  # tenants t (+) outer join
    assert _audit(dunning) == []  # fn_overdue_accounts does not log


def test_dunning_002_schedule_saturday(dunning):
    dunning.schedule_dunning("2026-02-14")  # Saturday -> Monday 16th
    two = transcript("DUNNING-002")
    assert _schedule_rows(dunning) == two["probes"]["schedule_rows"]
    latest = dunning.db().dunning_attempts.find_one({"invoiceId": INV[1]}, sort=[("attemptNo", -1)])
    assert (latest["scheduledFor"].date().isoformat(), DUN_STATUS[latest["statusCd"]]) == (
        two["business_fields"]["scheduled_for"], two["business_fields"]["status"])
    assert latest["_id"] == dunning.f_md5_uuid(f"{INV[1]}1") and latest["tenantId"] == T[2]
    assert _audit(dunning) == [("DUNNING", "scheduled 2 attempts as of 14-FEB-26")]
    dunning.schedule_dunning("2026-02-14")  # a rerun numbers the next attempt; nothing is overwritten
    assert [r["attempt_no"] for r in _schedule_rows(dunning)] == [1, 2, 1, 2, 3]
    assert _audit(dunning)[-1] == ("DUNNING", "scheduled 2 attempts as of 14-FEB-26")


def test_dunning_003_schedule_with_existing_attempt(dunning):
    dunning.schedule_dunning("2026-02-17")  # Tuesday; invoice 2 already has attempt 1
    three = transcript("DUNNING-003")
    assert _schedule_rows(dunning) == three["probes"]["schedule_rows"]
    latest = dunning.db().dunning_attempts.find_one({"invoiceId": INV[2]}, sort=[("attemptNo", -1)])
    assert (latest["attemptNo"], latest["scheduledFor"].date().isoformat()) == (
        three["business_fields"]["attempt_no"], three["business_fields"]["scheduled_for"])
    assert latest["_id"] == dunning.f_md5_uuid(f"{INV[2]}2")
    assert _audit(dunning) == [("DUNNING", "scheduled 2 attempts as of 17-FEB-26")]


def test_schedule_dunning_sunday_and_conflict_swallowed(dunning):
    # A foreign row already holding the deterministic id of invoice 1 attempt 1: the Oracle
    # EXCEPTION WHEN OTHERS swallows the ORA-00001 and the loop moves on.
    dunning.db().dunning_attempts.insert_one({"_id": dunning.f_md5_uuid(f"{INV[1]}1"), "tenantId": T[9], "invoiceId": "other",
                                              "attemptNo": 1, "scheduledFor": day("2026-01-01"), "statusCd": 30})
    dunning.schedule_dunning("2026-02-15")  # Sunday -> Monday 16th
    rows = _schedule_rows(dunning)
    assert [r for r in rows if r["invoice_id"] == INV[1]] == []
    assert [r for r in rows if r["invoice_id"] == INV[2]] == [
        {"attempt_no": 1, "invoice_id": INV[2], "scheduled_for": "2026-02-16", "status": "sent"},
        {"attempt_no": 2, "invoice_id": INV[2], "scheduled_for": "2026-02-16", "status": "scheduled"},
    ]
    assert _audit(dunning) == [("DUNNING", "scheduled 1 attempts as of 15-FEB-26")]
    # uq_dunning_attempts_invoice_attempt refuses a racing duplicate (invoiceId, attemptNo).
    with pytest.raises(dunning.DuplicateKeyError):
        dunning.db().dunning_attempts.insert_one({"_id": "race", "tenantId": T[5], "invoiceId": INV[2], "attemptNo": 2,
                                                  "scheduledFor": day("2026-02-16"), "statusCd": 10})


def test_dunning_004_005_suspend(dunning):
    dunning.suspend_overdue("2026-02-28")
    four = transcript("DUNNING-004")
    (sub,) = dunning.db().subscriptions.find({"tenantId": T[5]})
    assert (dunning.SUBSCRIPTION_STATUSES[sub["statusCd"]], sub["suspendedOn"].date().isoformat()) == (
        four["business_fields"]["status"], four["business_fields"]["suspended_on"])
    assert _suspension_notifications(dunning) == four["probes"]["suspension_notifications"]
    assert dunning.db().tenants.find_one({"_id": T[5]})["statusCd"] == 20
    # Tenant Two is already suspended (status 20): untouched, no notification, no audit row.
    assert dunning.db().tenants.find_one({"_id": T[2]})["statusCd"] == 20
    assert dunning.db().subscriptions.find_one({"_id": S[2]})["suspendedOn"] == day("2026-02-15")
    # Tenant Six's invoice is not overdue: untouched.
    assert dunning.db().tenants.find_one({"_id": T[6]})["statusCd"] == 10
    (hist,) = dunning.db().subscriptions_hist.find()  # TRG_SUBSCRIPTIONS_HIST pre-image of S5
    assert (hist["histOp"], hist["subscriptionId"], hist["statusCd"]) == ("UPD", S[5], 10) and "suspendedOn" not in hist
    assert _audit(dunning) == [("DUNNING", f"suspended tenant={T[5]}")]

    dunning.suspend_overdue("2026-02-28")  # DUNNING-005: second run, nothing to do
    five = transcript("DUNNING-005")
    assert [n["kind"] for n in _suspension_notifications(dunning)] == five["business_fields"]["notification_kinds"]
    assert _suspension_notifications(dunning) == five["probes"]["suspension_notifications"]
    assert dunning.db().subscriptions_hist.count_documents({}) == 1
    assert _audit(dunning) == [("DUNNING", f"suspended tenant={T[5]}")]
    # The suspend transaction is atomic: a uq_notifications_tenant_kind_sent conflict rolls the tenant back.
    dunning.db().tenants.update_one({"_id": T[6]}, {"$set": {"statusCd": 10}})
    dunning.db().invoices.update_one({"_id": INV[3]}, {"$set": {"statusCd": 40}})
    dunning.db().notifications.insert_one({"_id": "foreign", "tenantId": T[6], "kindCd": 3, "sentAt": day("2026-03-20")})
    with pytest.raises(dunning.DuplicateKeyError):
        dunning.db().notifications.insert_one({"_id": "dup", "tenantId": T[6], "kindCd": 3, "sentAt": day("2026-03-20")})
    dunning.suspend_overdue("2026-03-20")  # NOT EXISTS: the existing notification is kept, tenant still suspended
    assert dunning.db().tenants.find_one({"_id": T[6]})["statusCd"] == 20
    assert dunning.db().notifications.count_documents({"tenantId": T[6]}) == 1


def test_suspend_overdue_window(dunning):
    # issued day <= as_of - 14: invoice 2 (13 Feb) qualifies on 27 Feb, not on 26 Feb.
    dunning.suspend_overdue("2026-02-26")
    assert dunning.db().tenants.find_one({"_id": T[5]})["statusCd"] == 10
    dunning.suspend_overdue("2026-02-27")
    assert dunning.db().tenants.find_one({"_id": T[5]})["statusCd"] == 20
    assert dunning.db().subscriptions.find_one({"_id": S[5]})["suspendedOn"] == day("2026-02-27")
    assert dunning.db().notifications.find_one({"tenantId": T[5], "kindCd": 3})["_id"] == dunning.f_md5_uuid(
        f"{T[5]}suspension2026-02-27")


def test_dunning_attempts_listing(dunning):
    dunning.schedule_dunning("2026-02-14")
    listing = dunning.dunning_attempts("2026-02-28")
    expected = sorted(
        [(INV[2], "2", "2026-02-16", "scheduled", dunning.f_md5_uuid(f"{INV[2]}2")),
         (INV[1], "1", "2026-02-16", "scheduled", dunning.f_md5_uuid(f"{INV[1]}1")),
         (INV[2], "1", "2026-02-16", "sent", "80000000-0000-0000-0000-000000000001")],
        key=lambda r: (r[2], r[4]), reverse=True)  # ORDER BY scheduled_for DESC, id DESC
    assert [(r["invoice_id"], r["attempt_no"], r["scheduled_for"], r["status"], r["id"]) for r in listing] == expected
    assert set(listing[0]) == {"id", "tenant_id", "invoice_id", "attempt_no", "scheduled_for", "status"}
    assert dunning.dunning_attempts("2026-02-15") == []
    dunning.db().codes.delete_one({"_id": {"codeType": "DUN_STATUS", "codeVal": 20}})
    assert [r["status"] for r in dunning.dunning_attempts("2026-02-16") if r["attempt_no"] == "1" and r["invoice_id"] == INV[2]] == [None]  # LEFT JOIN codes
    assert sorted(i["name"] for i in dunning.db().billing_audit_log.list_indexes()) == ["_id_"]  # d-audit-retention: no TTL


def test_dunning_routes_on_mongo(dunning):
    from app import app

    client = app.test_client()
    admin = {"X-User-ID": T[1], "X-User-Roles": "ADMIN"}
    overdue = client.get("/api/v1/billing/admin/overdue", query_string={"as_of": "2026-02-28"}, headers=admin)
    assert overdue.status_code == 200
    assert [(r["tenant_id"], r["amount"], r["total"]) for r in overdue.get_json()] == [(T[2], "161.29", "161.29"), (T[5], "161.29", "161.29")]
    assert client.get("/api/v1/billing/admin/overdue", headers={"X-User-ID": T[1]}).status_code == 403
    assert client.get("/api/v1/billing/admin/dunning", query_string={"as_of": "tomorrow"}, headers=admin).status_code == 400
    assert client.get("/api/dunning/overdue", query_string={"as_of": "2026-02-28"}).get_json() == dunning.overdue("2026-02-28")
    assert client.post("/api/dunning/schedule", data={"as_of": "2026-02-14"}).get_json() == {"status": "scheduled"}
    assert client.post("/api/dunning/suspend", data={"as_of": "2026-02-28"}).get_json() == {"status": "suspended"}
    listing = client.get("/api/v1/billing/admin/dunning", query_string={"as_of": "2026-02-28"}, headers=admin)
    assert listing.status_code == 200 and listing.get_json() == dunning.dunning_attempts("2026-02-28")
    assert dunning.db().tenants.find_one({"_id": T[5]})["statusCd"] == 20


def test_nightly_dunning_command(dunning):
    from app import app

    result = app.test_cli_runner().invoke(args=["nightly-dunning", "--as-of", "2026-02-28"])
    assert result.exit_code == 0, result.output
    assert "as_of=2026-02-28 backend=mongo" in result.output
    assert _audit(dunning) == [("DUNNING", "scheduled 2 attempts as of 28-FEB-26"), ("DUNNING", f"suspended tenant={T[5]}")]
    assert dunning.db().dunning_attempts.count_documents({}) == 3
