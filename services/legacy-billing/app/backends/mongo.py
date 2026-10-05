"""MongoDB backend: U1 (foundation + plans) of the Oracle -> Atlas migration.

Ports PKG_OW_UTIL (f_md5_uuid, f_code_desc, f_dt2str, f_str2dt, log_msg), PKG_PLANS
(fn_list_plans, fn_entitlement, sp_change_plan), the ensure_tenant bootstrap and the two
subscription triggers (TRG_SUBSCRIPTIONS_HIST pre-image copy, TRG_SUB_NO_UNCANCEL) onto the
documents produced by migration/billing/recon/recon.py's reference mapping. Every statement
names the migration database explicitly; nothing else is ever touched.
"""
import hashlib
import os
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
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
    hexdigest = hashlib.md5(str(text).encode("utf-8"), usedforsecurity=False).hexdigest()
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


# -------------------------------------------------- modules not ported yet


def _not_ported(entrypoint, unit):
    raise NotImplementedError(f"{entrypoint} is not ported to the Mongo backend until {unit}")


def usage_rating(tenant, start, end):
    _not_ported("pkg_rating.fn_usage_rating", "U3")


def usage_summary(tenant, start, end):
    _not_ported("pkg_rating.fn_usage_summary", "U3")


def finalize_rating(tenant, start, end):
    _not_ported("pkg_rating.sp_finalize_rating", "U3")


def invoice_preview(tenant, start, end):
    _not_ported("pkg_invoicing.fn_invoice_preview", "U4")


def issue_invoice(tenant, start, end):
    _not_ported("pkg_invoicing.sp_issue_invoice", "U4")


def invoice_lines(invoice_id):
    _not_ported("pkg_invoicing.fn_invoice_lines", "U4")


def overdue(as_of):
    _not_ported("pkg_dunning.fn_overdue_accounts", "U5")


def schedule_dunning(as_of):
    _not_ported("pkg_dunning.sp_schedule_dunning", "U5")


def suspend_overdue(as_of):
    _not_ported("pkg_dunning.sp_suspend_overdue", "U5")

