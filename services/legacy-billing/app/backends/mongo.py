"""MongoDB backend: U1 (foundation + plans), U3 (usage + rating) and U4 (invoicing) of the Oracle -> Atlas migration.

Ports PKG_OW_UTIL (f_md5_uuid, f_code_desc, f_dt2str, f_str2dt, log_msg), PKG_PLANS
(fn_list_plans, fn_entitlement, sp_change_plan), the ensure_tenant bootstrap, the two
subscription triggers (TRG_SUBSCRIPTIONS_HIST pre-image copy, TRG_SUB_NO_UNCANCEL), PKG_RATING
(fn_usage_rating, fn_usage_summary, sp_finalize_rating), TRG_USAGE_EVENTS_CHECK and
PKG_INVOICING (fn_invoice_preview, fn_invoice_lines, sp_issue_invoice as one transaction over
rating_periods + invoices + credit_notes) onto the documents produced by
migration/billing/recon/recon.py's reference mapping. Every statement names the migration
database explicitly; nothing else is ever touched.
"""
import hashlib
import os
import re
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import NAMESPACE_URL, uuid5

from bson import Decimal128, Int64
from pymongo import DESCENDING, MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError

NAME = "mongo"
DATABASE = "ow_tp_billing_20261001T233613Z"
URI_ENV = "MONGODB_ATLAS_URI"
DATABASE_ENV = "MONGODB_DATABASE"
ESTATE_ERRORS = (PyMongoError,)
UNAVAILABLE = {
    "error": "legacy estate unavailable",
    "detail": "the MongoDB billing database is not reachable",
}

TIERS = {1: "starter", 2: "growth", 3: "scale"}
SUBSCRIPTION_STATUSES = {10: "active", 20: "suspended", 30: "cancelled"}
STATUS_CANCELLED = 30
STATUS_ACTIVE = 10
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
DDMONYY_RE = re.compile(r"^(\d{1,2})-([A-Z]{3})-(\d{2})(?:\s.*)?$")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}

_client = None


def _uri():
    uri = os.getenv(URI_ENV)
    if not uri:
        raise RuntimeError(f"{URI_ENV} is not set")
    return uri


def database_name():
    """Always the migration database; an override is honoured only on a loopback fixture."""
    override = os.getenv(DATABASE_ENV)
    if not override or override == DATABASE:
        return DATABASE
    if not all(host in LOCAL_HOSTS for host, _port in client().nodes):
        raise RuntimeError(f"{DATABASE_ENV} may only override the database on a local fixture")
    return override


def client():
    global _client
    if _client is None:
        _client = MongoClient(
            _uri(),
            tz_aware=True,
            serverSelectionTimeoutMS=int(os.getenv("MONGODB_SERVER_SELECTION_MS", "10000")),
            appname="ow-legacy-billing",
        )
    return _client


def db():
    return client()[database_name()]


def health():
    client().admin.command("ping")
    db().command("ping")


# ---------------------------------------------------------------- PKG_OW_UTIL


def f_md5_uuid(text):
    hexdigest = hashlib.md5(str(text).encode("utf-8")).hexdigest()
    return f"{hexdigest[:8]}-{hexdigest[8:12]}-{hexdigest[12:16]}-{hexdigest[16:20]}-{hexdigest[20:]}"


def f_code_desc(code_type, code_val, session=None):
    if code_val is not None:
        doc = db().codes.find_one(
            {"_id": {"codeType": code_type, "codeVal": int(code_val)}},
            {"codeDesc": 1},
            session=session,
        )
        if doc and doc.get("codeDesc") is not None:
            return doc["codeDesc"]
    return f"UNKNOWN({-1 if code_val is None else int(code_val)})"


def f_dt2str(value):
    if value is None:
        return None
    d = value.date() if isinstance(value, datetime) else value
    return f"{d.day:02d}-{MONTHS[d.month - 1]}-{d.year % 100:02d}"


def f_str2dt(text):
    if not text:
        return None
    match = DDMONYY_RE.match(str(text).strip().upper())
    if not match:
        return None
    day, mon, yy = int(match.group(1)), match.group(2), int(match.group(3))
    if mon not in MONTHS:
        return None
    year = 2000 + yy if yy < 50 else 1900 + yy
    try:
        return date(year, MONTHS.index(mon) + 1, day)
    except ValueError:
        return None


def _next_id(collection, session=None):
    last = collection.find_one({}, {"_id": 1}, sort=[("_id", DESCENDING)], session=session)
    return Int64((int(last["_id"]) if last else 0) + 1)


def log_msg(module, message):
    """Shared audit writer (PKG_OW_UTIL.log_msg). Runs outside any business transaction, as
    the autonomous transaction did; an insert failure is raised to the caller."""
    audit = db().billing_audit_log
    doc = {
        "loggedAt": _now(),
        "module": str(module)[:30],
        "message": str(message)[:4000],
    }
    for _attempt in range(5):
        try:
            audit.insert_one({"_id": _next_id(audit), **doc})
            return
        except DuplicateKeyError:
            continue
    audit.insert_one({"_id": _next_id(audit), **doc})


# ------------------------------------------------------------------- helpers


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _as_bson_date(value):
    d = _as_date(value)
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def _json_value(value):
    """Render like the Oracle backend: NUMBER columns arrive as Decimal and serialise as strings."""
    if isinstance(value, Decimal128):
        return str(value.to_decimal())
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, datetime):
        if value.time() == datetime.min.time():
            return value.date().isoformat()
        return value.replace(tzinfo=None).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _decimal(value):
    if value is None:
        return None
    if isinstance(value, Decimal128):
        return value.to_decimal()
    return Decimal(str(value))


def _transaction(work):
    with client().start_session() as session:
        return session.with_transaction(lambda s: work(s))


# --------------------------------------------------------------- PKG_PLANS


def _active_plans(session=None):
    plans = list(db().plans.find({"activeYn": "Y"}, session=session))
    plans.sort(key=lambda p: (_decimal(p.get("monthlyFee")) or Decimal(0), p.get("code") or ""))
    return plans


def list_plans():
    log_msg("PLANS", "fn_list_plans")
    return [
        {
            "plan_id": plan["_id"],
            "code": plan.get("code"),
            "tier": TIERS.get(plan.get("tierCd"), "UNKNOWN"),
            "monthly_fee": _json_value(plan.get("monthlyFee")),
            "included_units": _json_value(plan.get("includedUnits")),
            "overage_rate": _json_value(plan.get("overageRate")),
        }
        for plan in _active_plans()
    ]


def _covering_subscription(tenant_id, on, session=None):
    on_dt = _as_bson_date(on)
    return db().subscriptions.find_one(
        {
            "tenantId": tenant_id,
            "startsOn": {"$lte": on_dt},
            "$or": [{"endsOn": None}, {"endsOn": {"$gte": on_dt}}],
        },
        sort=[("startsOn", DESCENDING)],
        session=session,
    )


def entitlement(tenant_id, on):
    on_date = _as_date(on)
    tenant = db().tenants.find_one({"_id": tenant_id}, {"_id": 1})
    if tenant is None:
        return []
    sub = _covering_subscription(tenant_id, on_date)
    if sub is None:
        return []
    plan = db().plans.find_one({"_id": sub.get("planId")}) if sub.get("planId") is not None else None
    plan = plan or {}
    starts_on = _as_date(sub["startsOn"])
    return [
        {
            "tenant_id": tenant_id,
            "plan_code": plan.get("code"),
            "tier": TIERS.get(plan.get("tierCd"), "UNKNOWN"),
            "monthly_fee": _json_value(plan.get("monthlyFee")),
            "included_units": _json_value(plan.get("includedUnits")),
            "subscription_status": SUBSCRIPTION_STATUSES.get(sub.get("statusCd"), "UNKNOWN"),
            "effective_on": max(starts_on, on_date).isoformat(),
        }
    ]


def _write_pre_image(sub, op, session):
    """TRG_SUBSCRIPTIONS_HIST: copy the :OLD row before an UPDATE/DELETE."""
    hist = db().subscriptions_hist
    now = _now()
    doc = {
        "_id": _next_id(hist, session),
        "histDt": f"{f_dt2str(now)} {now.strftime('%H:%M:%S')}",
        "histOp": op,
        "subscriptionId": sub["_id"],
        "tenantId": sub.get("tenantId"),
    }
    for field in ("planId", "startsOn", "endsOn", "statusCd", "suspendedOn"):
        if sub.get(field) is not None:
            doc[field] = sub[field]
    parsed = f_str2dt(doc["histDt"])
    if parsed is not None:
        doc["histDate"] = _as_bson_date(parsed)
    hist.insert_one(doc, session=session)


def _close_subscription(sub, ends_on, session):
    # TRG_SUB_NO_UNCANCEL: a cancelled subscription never leaves the cancelled state.
    status = STATUS_CANCELLED if sub.get("statusCd") == STATUS_CANCELLED else STATUS_ACTIVE
    _write_pre_image(sub, "UPD", session)
    db().subscriptions.update_one(
        {"_id": sub["_id"]},
        {"$set": {"endsOn": _as_bson_date(ends_on), "statusCd": status}},
        session=session,
    )


def change_plan(tenant_id, plan_id, effective_on):
    effective_date = _as_date(effective_on)
    log_msg(
        "PLANS",
        f"sp_change_plan tenant={tenant_id} plan={plan_id} eff={effective_date.isoformat()}",
    )
    new_id = f_md5_uuid(f"{tenant_id}{plan_id}{effective_date.isoformat()}")

    def work(session):
        # Same order as the Oracle backend: the facade's same-day close (starts_on = eff)
        # first, then sp_change_plan's cursor over the still-open rows (starts_on < eff).
        for starts_on in ({"$eq": _as_bson_date(effective_date)}, {"$lt": _as_bson_date(effective_date)}):
            open_subs = db().subscriptions.find(
                {"tenantId": tenant_id, "endsOn": None, "startsOn": starts_on},
                session=session,
            )
            for sub in open_subs:
                _close_subscription(sub, effective_date - timedelta(days=1), session)
        db().subscriptions.insert_one(
            {
                "_id": new_id,
                "tenantId": tenant_id,
                "planId": plan_id,
                "startsOn": _as_bson_date(effective_date),
                "statusCd": STATUS_ACTIVE,
            },
            session=session,
        )

    _transaction(work)


# ------------------------------------------------------------ tenant bootstrap


def ensure_tenant(tenant_id, email):
    if db().tenants.find_one({"_id": tenant_id}, {"_id": 1}):
        return False

    def work(session):
        try:
            db().tenants.insert_one(
                {"_id": tenant_id, "name": email or tenant_id, "taxExemptYn": "N", "statusCd": STATUS_ACTIVE},
                session=session,
            )
        except DuplicateKeyError:
            session.abort_transaction()
            return False
        plans = _active_plans(session)
        plans.sort(key=lambda p: (_decimal(p.get("monthlyFee")) or Decimal(0), p["_id"]))
        if not plans:
            raise RuntimeError("no active billing plan")
        try:
            db().subscriptions.insert_one(
                {
                    "_id": str(uuid5(NAMESPACE_URL, f"ow:{tenant_id}:sub")),
                    "tenantId": tenant_id,
                    "planId": plans[0]["_id"],
                    "startsOn": _as_bson_date(_now()),
                    "statusCd": STATUS_ACTIVE,
                },
                session=session,
            )
        except DuplicateKeyError:
            session.abort_transaction()
            return False
        return True

    return _transaction(work)


def tenant_profile(tenant_id):
    tenant = db().tenants.find_one({"_id": tenant_id})
    if tenant is None:
        return []
    status = db().codes.find_one(
        {"_id": {"codeType": "TENANT_STATUS", "codeVal": tenant.get("statusCd")}}, {"codeDesc": 1}
    )
    return [
        {
            "tenant_id": tenant["_id"],
            "name": tenant.get("name"),
            "status": status.get("codeDesc") if status else None,
            "tax_exempt": tenant.get("taxExemptYn"),
        }
    ]


# ----------------------------------------------------------- customers (U2)

# CUSTOMER_MASTER columns in table order; the document field is the camelCase of the column
# (mapping_spec.json#customers, d-flat-customer-columns) and CUST_ID is _id.
CUSTOMER_COLUMNS = (
    "cust_id cust_seq_no tenant_id cust_no cust_name cust_name_upper legal_name dba_name addr_line_1 "
    "addr_line_2 addr_line_3 addr_line_4 addr_line_5 addr_line_6 city state_cd zip zip4 country_cd "
    "mail_addr_line_1 mail_addr_line_2 mail_addr_line_3 mail_addr_line_4 mail_addr_line_5 mail_addr_line_6 "
    "mail_city mail_state_cd mail_zip phone1 phone2 phone3 phone4 phone1_type_cd phone2_type_cd "
    "phone3_type_cd phone4_type_cd fax email_1 email_2 email_3 signup_dt last_activity_dt last_invoice_dt "
    "last_payment_dt terminate_dt status_cd sub_status_cd cust_type_cd segment_cd region_cd territory_cd "
    "channel_cd rate_class_cd tax_exempt_yn credit_hold_yn dunning_exempt_yn vip_yn cur_bal_amt past_due_amt "
    "ytd_billed_amt ltd_billed_amt ytd_paid_amt credit_limit_amt related_acct_ids child_acct_ids "
    "promo_codes_csv contact_notes legacy_sys_key mainframe_acct_no conversion_batch_no flag_01 flag_02 "
    "flag_03 flag_04 flag_05 flag_06 flag_07 flag_08 flag_09 flag_10 flag_11 flag_12 flag_13 flag_14 flag_15 "
    "flag_16 flag_17 flag_18 flag_19 flag_20 udf_01 udf_02 udf_03 udf_04 udf_05 udf_06 udf_07 udf_08 udf_09 "
    "udf_10 udf_11 udf_12 udf_13 udf_14 udf_15 udf_16 udf_17 udf_18 udf_19 udf_20 udf_21 udf_22 udf_23 "
    "udf_24 udf_25 udf_26 udf_27 udf_28 udf_29 udf_30 udf_31 udf_32 udf_33 udf_34 udf_35 udf_36 udf_37 "
    "udf_38 udf_39 udf_40 udf_amt_01 udf_amt_02 udf_amt_03 udf_amt_04 udf_amt_05 udf_amt_06 udf_amt_07 "
    "udf_amt_08 udf_amt_09 udf_amt_10 udf_dt_01 udf_dt_02 udf_dt_03 udf_dt_04 udf_dt_05 udf_dt_06 udf_dt_07 "
    "udf_dt_08 udf_dt_09 udf_dt_10 created_by created_dt updated_by updated_dt row_version_no"
).split()
EAV_COLUMNS = ("eav_id", "entity_type", "entity_id", "attr_name", "attr_value", "attr_type", "created_dt")
CUSTOMER_SUMMARY_COLUMNS = ("cust_no", "cust_name", "cur_bal_amt", "past_due_amt", "credit_hold_yn")


def _camel(column):
    head, *rest = column.lower().split("_")
    return head + "".join(part.capitalize() for part in rest)


def _first_customer(tenant_id, session=None):
    """facade: SELECT * FROM customer_master WHERE tenant_id = :1 ORDER BY cust_seq_no FETCH FIRST 1 ROWS ONLY."""
    return db().customers.find_one({"tenantId": tenant_id}, sort=[("custSeqNo", 1)], session=session)


def _customer_row(doc, columns):
    """The row as the Oracle backend renders it: every column, NULL as null; the typed siblings
    (*Date, *List, attributes[].typed, createdDate) are document-only and never surface here."""
    return {
        column: _json_value(doc.get("_id") if column == "cust_id" else doc.get(_camel(column)))
        for column in columns
    }


def _attribute_rows(doc):
    """SELECT * FROM entity_attr_value WHERE entity_type = 'CUSTOMER' AND entity_id = :1 ORDER BY eav_id."""
    elements = sorted(doc.get("attributes") or [], key=lambda el: int(el["eavId"]))
    return [
        {
            "eav_id": _json_value(el.get("eavId")),
            "entity_type": "CUSTOMER",
            "entity_id": doc["_id"],
            "attr_name": el.get("name"),
            "attr_value": el.get("value"),
            "attr_type": el.get("type"),
            "created_dt": el.get("createdDt"),
        }
        for el in elements
    ]


def customer_summary(tenant_id):
    doc = _first_customer(tenant_id)
    return _customer_row(doc, CUSTOMER_SUMMARY_COLUMNS) if doc else None


def customer(tenant_id):
    """GET /customer: the tenant's first customer with its attributes, or None (404)."""
    doc = _first_customer(tenant_id)
    if doc is None:
        return None
    return {**_customer_row(doc, CUSTOMER_COLUMNS), "attributes": _attribute_rows(doc)}


def _write_customer_pre_image(customer_doc, op, session):
    """TRG_CUSTOMER_MASTER_HIST: copy the :OLD customer_master row (not its EAV rows) before an
    UPDATE/DELETE; HIST_DT as the trigger writes it, DD-MON-YY HH24:MI:SS, with the parsed day."""
    hist = db().customers_hist
    now = _now()
    doc = {
        "_id": _next_id(hist, session),
        "histDt": f"{f_dt2str(now)} {now.strftime('%H:%M:%S')}",
        "histOp": op,
        "custId": customer_doc["_id"],
    }
    doc.update({k: v for k, v in customer_doc.items() if k not in ("_id", "attributes")})
    parsed = f_str2dt(doc["histDt"])
    if parsed is not None:
        doc["histDate"] = _as_bson_date(parsed)
    hist.insert_one(doc, session=session)


def update_customer(cust_id, changes):
    """No app write path exists today (customer_master: 3 reads, 0 writes); when one arrives, the
    pre-image copy and the update are one transaction. Returns the updated document or None."""
    fields = {k: v for k, v in changes.items() if k not in ("_id", "attributes")}
    if not fields:
        raise ValueError("update_customer needs at least one customer field")

    def work(session):
        customers = db().customers
        current = customers.find_one({"_id": cust_id}, session=session)
        if current is None:
            return None
        _write_customer_pre_image(current, "UPD", session)
        customers.update_one({"_id": cust_id}, {"$set": fields}, session=session)
        return customers.find_one({"_id": cust_id}, session=session)

    return _transaction(work)


# -------------------------------------------------------------- PKG_RATING (U3)

USAGE_KINDS = {1: "api", 2: "storage", 3: "compute"}
STATUS_SUSPENDED = 20
FIRST_TIER_UNITS = 101
SECOND_TIER_FACTOR = Decimal("1.5")
CENTS = Decimal("0.01")


class UsageEventRejected(ValueError):
    """TRG_USAGE_EVENTS_CHECK: units must be > 0 and kind must be a CODES('USAGE_KIND') row."""


def _round_half_up(value, places):
    return value.quantize(places, rounding=ROUND_HALF_UP)


def _oracle_number(value):
    """Oracle NUMBER keeps no trailing fraction zeros (ROUND(0, 2) reads back as 0, 5.50 as 5.5)."""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".") or "0"
    return Decimal(text)


def _add_months(day, months):
    """Oracle ADD_MONTHS: a last-day-of-month input yields the last day of the result month."""
    year = day.year + (day.month - 1 + months) // 12
    month = (day.month - 1 + months) % 12 + 1
    last = monthrange(year, month)[1]
    if day.day == monthrange(day.year, day.month)[1] or day.day > last:
        return date(year, month, last)
    return date(year, month, day.day)


def _period_filter(tenant_id, start, end):
    """Same window as the PL/SQL TO_CHAR(occurred_at, 'YYYYMMDD') BETWEEN start AND end."""
    return {
        "tenantId": tenant_id,
        "occurredAt": {"$gte": _as_bson_date(start), "$lt": _as_bson_date(end) + timedelta(days=1)},
    }


def _period_subscription(tenant_id, start, end, session=None):
    """compute_rating's cursor: the newest subscription overlapping the period."""
    return db().subscriptions.find_one(
        {
            "tenantId": tenant_id,
            "startsOn": {"$lte": _as_bson_date(end)},
            "$or": [{"endsOn": None}, {"endsOn": {"$gte": _as_bson_date(start)}}],
        },
        sort=[("startsOn", DESCENDING)],
        session=session,
    )


def _usage_kind(kind, session=None):
    for code in db().codes.find({"_id.codeType": "USAGE_KIND"}, {"codeDesc": 1}, session=session):
        if str(code.get("codeDesc") or "").lower() == str(kind or "").lower():
            return int(code["_id"]["codeVal"])
    return None


def _compute_rating(tenant_id, start, end, session=None):
    """PKG_RATING.compute_rating; the package-global g_* state becomes this dict."""
    period_start, period_end = _as_date(start), _as_date(end)
    sub = _period_subscription(tenant_id, period_start, period_end, session)
    plan = None
    if sub is not None and sub.get("planId") is not None:
        plan = db().plans.find_one({"_id": sub["planId"]}, session=session)
    included = None if plan is None or plan.get("includedUnits") is None else int(plan["includedUnits"])
    rate = None if plan is None else _decimal(plan.get("overageRate"))

    used = 0
    for event in db().usage_events.find(_period_filter(tenant_id, period_start, period_end), {"units": 1}, session=session):
        used += int(event.get("units") or 0)

    prior = 0
    for period in db().rating_periods.find(
        {
            "tenantId": tenant_id,
            "periodStart": {"$gte": _as_bson_date(_add_months(period_start, -3)), "$lt": _as_bson_date(period_start)},
        },
        {"result.rolloverUnits": 1},
        session=session,
    ):
        prior += int((period.get("result") or {}).get("rolloverUnits") or 0)
    rollover = prior if included is None else min(2 * included, prior)
    billable = 0 if included is None else max(used - rollover - included, 0)
    first_tier = min(billable, FIRST_TIER_UNITS)
    second_tier = max(billable - FIRST_TIER_UNITS, 0)
    overage = None
    if rate is not None:
        overage = _round_half_up(first_tier * rate + second_tier * rate * SECOND_TIER_FACTOR, CENTS)

    suspended_on = sub.get("suspendedOn") if sub is not None else None
    if sub is not None and sub.get("statusCd") == STATUS_SUSPENDED and suspended_on is not None:
        suspended_on = _as_date(suspended_on)
        if period_start <= suspended_on <= period_end:
            factor = Decimal((period_end - suspended_on).days + 1) / Decimal((period_end - period_start).days + 1)
            billable = int(_round_half_up(billable * factor, Decimal(1)))
            if overage is not None:
                overage = _round_half_up(overage * factor, CENTS)
    if overage is not None:
        overage = _oracle_number(overage)

    log_msg("RATING", f"compute tenant={tenant_id} used={used} billable={billable}")
    return {
        "tenant_id": tenant_id,
        "period_start": period_start,
        "period_end": period_end,
        "subscription_id": None if sub is None else sub["_id"],
        "used_units": used,
        "quota_units": included,
        "rollover_units": rollover,
        "billable_units": billable,
        "first_tier_units": first_tier,
        "second_tier_units": second_tier,
        "overage_amount": overage,
    }


def usage_rating(tenant, start, end):
    rating = _compute_rating(tenant, start, end)
    return [
        {
            key: _json_value(rating[key])
            for key in (
                "tenant_id", "period_start", "period_end", "used_units", "quota_units", "rollover_units",
                "billable_units", "first_tier_units", "second_tier_units", "overage_amount",
            )
        }
    ]


def usage_summary(tenant, start, end):
    by_kind = {}
    for event in db().usage_events.find(_period_filter(tenant, start, end), {"units": 1, "kindCd": 1}):
        kind = USAGE_KINDS.get(event.get("kindCd"), "UNKNOWN")
        count, units = by_kind.get(kind, (0, 0))
        by_kind[kind] = (count + 1, units + int(event.get("units") or 0))
    return [
        {"kind": kind, "event_count": _json_value(count), "units": _json_value(units)}
        for kind, (count, units) in sorted(by_kind.items())
    ]


def usage_events(tenant, start, end, limit=50):
    """GET /usage's event list: newest first, kind resolved through CODES('USAGE_KIND')."""
    kinds = {
        int(code["_id"]["codeVal"]): code.get("codeDesc")
        for code in db().codes.find({"_id.codeType": "USAGE_KIND"}, {"codeDesc": 1})
    }
    cursor = db().usage_events.find(_period_filter(tenant, start, end)).sort(
        [("occurredAt", DESCENDING), ("_id", DESCENDING)]
    ).limit(limit)
    return [
        {
            "id": event["_id"],
            "occurred_at": _json_value(event["occurredAt"]),
            "units": _json_value(event.get("units")),
            "kind": kinds.get(event.get("kindCd")),
        }
        for event in cursor
    ]


def _finalize_rating(tenant_id, start, end, session):
    period_start, period_end = _as_date(start), _as_date(end)
    periods = db().rating_periods
    existing = periods.find_one({"tenantId": tenant_id, "periodStart": _as_bson_date(period_start)}, session=session)
    period_id = existing["_id"] if existing else f_md5_uuid(f"{tenant_id}{period_start.isoformat()}")
    periods.update_one(
        {"_id": period_id},
        {"$set": {"tenantId": tenant_id, "periodStart": _as_bson_date(period_start), "periodEnd": _as_bson_date(period_end)}},
        upsert=True,
        session=session,
    )
    rating = _compute_rating(tenant_id, period_start, period_end, session)
    if rating["subscription_id"] is None or rating["quota_units"] is None or rating["overage_amount"] is None:
        raise ValueError(f"no plan covers tenant {tenant_id} for {period_start.isoformat()}..{period_end.isoformat()}")
    result = {
        "usedUnits": Int64(rating["used_units"]),
        "rolloverUnits": Int64(max(rating["quota_units"] - rating["used_units"], 0)),
        "billableUnits": Int64(rating["billable_units"]),
        "overageAmount": Decimal128(rating["overage_amount"]),
    }
    if existing is not None and isinstance(existing.get("result"), dict):
        update = {"$set": {f"result.{key}": value for key, value in result.items()}}
    else:
        result.update(
            id=f_md5_uuid(period_id),
            subscriptionId=rating["subscription_id"],
            quotaUnits=Int64(rating["quota_units"]),
            createdAt=_as_bson_date(period_end),
        )
        update = {"$set": {"result": result}}
    periods.update_one({"_id": period_id}, update, session=session)
    return period_id


def finalize_rating(tenant, start, end, session=None):
    """sp_finalize_rating: period header + embedded result in one transaction.

    Pass `session` to run inside a caller-owned transaction (U4's issue_invoice port).
    """
    if session is None:
        period_id = _transaction(lambda s: _finalize_rating(tenant, start, end, s))
    else:
        period_id = _finalize_rating(tenant, start, end, session)
    log_msg("RATING", f"finalized period={period_id}")
    return period_id


def record_usage_event(event_id, tenant_id, occurred_at, units, kind):
    """POST /internal/usage/events insert; returns 'recorded' or 'duplicate' (the ORA-00001 contract)."""
    if units is None or int(units) <= 0:
        raise UsageEventRejected("units must be > 0")
    kind_cd = _usage_kind(kind)
    if kind_cd is None:
        raise UsageEventRejected(f"unknown usage kind {kind}")
    occurred = occurred_at if isinstance(occurred_at, datetime) else datetime.fromisoformat(str(occurred_at).replace("Z", "+00:00"))
    occurred = occurred.replace(tzinfo=timezone.utc)
    try:
        db().usage_events.insert_one(
            {"_id": event_id, "tenantId": tenant_id, "occurredAt": occurred, "units": Int64(units), "kindCd": kind_cd}
        )
    except DuplicateKeyError:
        return "duplicate"
    return "recorded"


# ------------------------------------------------------------ PKG_INVOICING


TAX_RATE = Decimal("0.0825")
INVOICE_STATUS_ISSUED = 20


def _round(value, places=2):
    """Oracle ROUND(n, places): ties away from zero; NULL in, NULL out."""
    if value is None:
        return None
    return Decimal(value).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def _num(value):
    """Render a NUMBER as python-oracledb hands it to the Oracle backend: no trailing zeros."""
    if value is None:
        return None
    d = _decimal(value)
    if d == d.to_integral_value():
        return str(int(d))
    return format(d.normalize(), "f")


def _nvl(value, default):
    return default if value is None else value


def _least(a, b):
    return None if a is None or b is None else min(a, b)


def _money(value):
    """Store as the NUMBER(12,2) column did: rounded to cents, Decimal128."""
    return Decimal128(_round(value))


def _period_subscriptions(tenant_id, start, end, session=None):
    """The tenant's subscriptions covering the period, latest starts_on first."""
    start_dt, end_dt = _as_bson_date(start), _as_bson_date(end)
    return list(
        db().subscriptions.find(
            {
                "tenantId": tenant_id,
                "startsOn": {"$lte": end_dt},
                "$or": [{"endsOn": None}, {"endsOn": {"$gte": start_dt}}],
            },
            sort=[("startsOn", DESCENDING)],
            session=session,
        )
    )


def _plan_doc(plan_id, session=None):
    if plan_id is None:
        return None
    return db().plans.find_one({"_id": plan_id}, session=session)



def _preview_amounts(tenant_id, start, end, session=None):
    """pkg_invoicing.compute_preview: plan code and fee, rated overage, open credit and tax."""
    start_d, end_d = _as_date(start), _as_date(end)
    plan_code = plan_fee = None
    for sub in _period_subscriptions(tenant_id, start_d, end_d, session):
        plan = _plan_doc(sub.get("planId"), session)
        if plan is not None:
            plan_code, plan_fee = plan.get("code"), _decimal(plan.get("monthlyFee"))
            break
    overage = _compute_rating(tenant_id, start_d, end_d, session)["overage_amount"]
    credit = Decimal(0)
    for note in db().credit_notes.find({"tenantId": tenant_id, "remainingAmount": {"$gt": 0}}, {"remainingAmount": 1}, session=session):
        credit += _nvl(_decimal(note.get("remainingAmount")), Decimal(0))
    tenant = db().tenants.find_one({"_id": tenant_id}, {"taxExemptYn": 1}, session=session)
    exempt = _nvl((tenant or {}).get("taxExemptYn"), "N")
    if exempt == "Y":
        tax = Decimal(0)
    elif plan_fee is None or overage is None:
        tax = None
    else:
        tax = (plan_fee + overage) * TAX_RATE
    return plan_code, plan_fee, overage, credit, tax


def _preview_lines(tenant_id, start, end, session=None):
    """fn_invoice_preview's five rows, with Decimal (or None) amounts."""
    plan_code, plan_fee, overage, credit, tax = _preview_amounts(tenant_id, start, end, session)
    charge_cap = None if plan_fee is None or overage is None or tax is None else _round(plan_fee + overage + tax)
    credit_applied = _least(credit, _nvl(charge_cap, credit))
    half_tax = None if tax is None else tax / 2
    zero = Decimal(0)

    def line(line_no, line_type, description, amount, credit_part, total):
        return {
            "line_no": line_no,
            "line_type": line_type,
            "description": description,
            "amount": amount,
            "tax_amount": zero,
            "credit_applied": credit_part,
            "total": total,
        }

    return [
        line(1, "plan", plan_code, _round(plan_fee), zero, _round(plan_fee)),
        line(2, "usage", "usage overage", _round(overage), zero, _round(overage)),
        line(3, "tax", "regional tax", half_tax, zero, half_tax),
        line(4, "tax", "local tax", half_tax, zero, half_tax),
        line(5, "credit", "credit notes", zero, credit_applied, -credit_applied),
    ]


def _render_line(line):
    return {k: (_num(v) if isinstance(v, (Decimal, Decimal128, int)) else v) for k, v in line.items()}


def invoice_preview(tenant, start, end):
    return [_render_line(line) for line in _preview_lines(tenant, start, end)]


def invoice_lines(invoice_id):
    invoice = db().invoices.find_one({"_id": invoice_id}, {"lines": 1})
    lines = sorted((invoice or {}).get("lines") or [], key=lambda line: int(line.get("lineNo", 0)))
    return [
        {
            "line_no": _num(line.get("lineNo")),
            "line_type": line.get("lineType"),
            "description": line.get("description"),
            "amount": _num(line.get("amount")),
        }
        for line in lines
    ]


def issue_invoice(tenant, start, end):
    """sp_issue_invoice: finalize the rating period, upsert the invoice header with its lines
    rebuilt from the preview, and burn open credit notes oldest-first, in one transaction.
    Only status 20 (issued) is ever written. The audit append runs after the commit."""
    start_d, end_d = _as_date(start), _as_date(end)
    period_id = f_md5_uuid(f"{tenant}{start_d.isoformat()}")
    invoice_id = f_md5_uuid(f"{period_id}invoice")

    def work(session):
        finalize_rating(tenant, start_d, end_d, session=session)
        invoices = db().invoices
        if invoices.find_one({"_id": invoice_id}, {"_id": 1}, session=session) is None:
            invoices.insert_one(
                {
                    "_id": invoice_id,
                    "tenantId": tenant,
                    "periodId": period_id,
                    "issuedAt": _as_bson_date(end_d),
                    "subtotal": _money(0),
                    "tax": _money(0),
                    "total": _money(0),
                    "statusCd": INVOICE_STATUS_ISSUED,
                },
                session=session,
            )
        else:
            invoices.update_one({"_id": invoice_id}, {"$set": {"statusCd": INVOICE_STATUS_ISSUED}}, session=session)

        subtotal = tax = Decimal(0)
        credit = Decimal(0)
        lines = []
        for row in _preview_lines(tenant, start_d, end_d, session):
            amount = row["total"] if row["line_type"] == "credit" else row["amount"]
            if amount is None or row["description"] is None:
                raise ValueError(f"tenant {tenant} has no covering plan for {start_d.isoformat()}; invoice line {row['line_no']} would be NULL")
            lines.append(
                {
                    "id": f_md5_uuid(f"{invoice_id}{row['line_no']}"),
                    "lineNo": row["line_no"],
                    "lineType": row["line_type"],
                    "description": row["description"],
                    "amount": _money(amount),
                }
            )
            if row["line_type"] in ("plan", "usage"):
                subtotal += _round(row["amount"])
            elif row["line_type"] == "tax":
                tax += _round(row["amount"])
            elif row["line_type"] == "credit":
                credit = row["credit_applied"]
        total = _round(subtotal + tax - credit)
        invoices.update_one(
            {"_id": invoice_id},
            {"$set": {"subtotal": _money(subtotal), "tax": _money(tax), "total": _money(total), "lines": lines}},
            session=session,
        )

        notes = db().credit_notes
        for note in notes.find({"tenantId": tenant, "remainingAmount": {"$gt": 0}}, sort=[("issuedOn", 1), ("_id", 1)], session=session):
            if credit <= 0:
                break
            remaining = _decimal(note.get("remainingAmount"))
            notes.update_one({"_id": note["_id"]}, {"$set": {"remainingAmount": _money(max(remaining - credit, Decimal(0)))}}, session=session)
            credit = max(credit - remaining, Decimal(0))
        return total

    total = _transaction(work)
    log_msg("INVOICING", f"issued invoice={invoice_id} total={_num(_nvl(total, 0))}")


def invoices_for_tenant(tenant_id):
    """GET /invoices: headers joined to their rating period and INV_STATUS code, newest first."""
    pipeline = [
        {"$match": {"tenantId": tenant_id}},
        {"$lookup": {"from": "rating_periods", "localField": "periodId", "foreignField": "_id", "as": "period"}},
        {"$unwind": "$period"},
        {
            "$lookup": {
                "from": "codes",
                "let": {"cd": "$statusCd"},
                "pipeline": [
                    {"$match": {"$expr": {"$and": [{"$eq": ["$_id.codeType", "INV_STATUS"]}, {"$eq": ["$_id.codeVal", "$$cd"]}]}}},
                    {"$project": {"_id": 0, "codeDesc": 1}},
                ],
                "as": "status",
            }
        },
        {"$project": {"lines": 0}},
        {"$sort": {"issuedAt": DESCENDING, "_id": DESCENDING}},
    ]
    return [
        {
            "invoice_id": doc["_id"],
            "period_start": _json_value(doc["period"].get("periodStart")),
            "period_end": _json_value(doc["period"].get("periodEnd")),
            "subtotal": _num(doc.get("subtotal")),
            "tax": _num(doc.get("tax")),
            "total": _num(doc.get("total")),
            "status": doc["status"][0].get("codeDesc") if doc.get("status") else None,
        }
        for doc in db().invoices.aggregate(pipeline)
    ]


def invoice_owned(invoice_id, tenant_id):
    return db().invoices.find_one({"_id": invoice_id, "tenantId": tenant_id}, {"_id": 1}) is not None


# -------------------------------------------------- modules not ported yet


def _not_ported(entrypoint, unit):
    raise NotImplementedError(f"{entrypoint} is not ported to the Mongo backend until {unit}")


def overdue(as_of):
    _not_ported("pkg_dunning.fn_overdue_accounts", "U5")


def schedule_dunning(as_of):
    _not_ported("pkg_dunning.sp_schedule_dunning", "U5")


def suspend_overdue(as_of):
    _not_ported("pkg_dunning.sp_suspend_overdue", "U5")

