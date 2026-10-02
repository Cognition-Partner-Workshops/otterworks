"""MongoDB backend: U1 (foundation + plans) and U4 (invoicing) of the Oracle -> Atlas migration.

Ports PKG_OW_UTIL (f_md5_uuid, f_code_desc, f_dt2str, f_str2dt, log_msg), PKG_PLANS
(fn_list_plans, fn_entitlement, sp_change_plan), the ensure_tenant bootstrap and the two
subscription triggers (TRG_SUBSCRIPTIONS_HIST pre-image copy, TRG_SUB_NO_UNCANCEL), and
PKG_INVOICING (fn_invoice_preview, fn_invoice_lines, sp_issue_invoice as one transaction over
rating_periods + invoices + credit_notes) onto the documents produced by
migration/billing/recon/recon.py's reference mapping. Every statement names the migration
database explicitly; nothing else is ever touched.
"""
import calendar
import hashlib
import os
import re
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, localcontext
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


def customer_summary(tenant_id):
    """customers is a U2 collection; GET /me.customer stays null on Mongo until U2."""
    return None


# ------------------------------------------------------------ PKG_INVOICING


TAX_RATE = Decimal("0.0825")
INVOICE_STATUS_ISSUED = 20
SUBSCRIPTION_SUSPENDED = 20
TIER_BREAK_UNITS = 101
CENTS = Decimal("0.01")


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


def _greatest(a, b):
    return None if a is None or b is None else max(a, b)


def _money(value):
    """Store as the NUMBER(12,2) column did: rounded to cents, Decimal128."""
    return Decimal128(_round(value))


def _add_months(d, months):
    """Oracle ADD_MONTHS: a month-end day stays a month-end day."""
    index = d.month - 1 + months
    year, month = d.year + index // 12, index % 12 + 1
    last = calendar.monthrange(year, month)[1]
    day = last if d.day == calendar.monthrange(d.year, d.month)[1] else min(d.day, last)
    return date(year, month, day)


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


def _rating_quantities(tenant_id, start, end, session=None):
    """pkg_rating.compute_rating: the rated quantities of one period (the package globals).

    Carried here for the issue transaction; the U3 port owns the rating entrypoints."""
    start_d, end_d = _as_date(start), _as_date(end)
    subs = _period_subscriptions(tenant_id, start_d, end_d, session)
    sub = subs[0] if subs else None
    plan = _plan_doc(sub.get("planId"), session) if sub else None
    included = None if plan is None or plan.get("includedUnits") is None else int(plan["includedUnits"])
    rate = None if plan is None else _decimal(plan.get("overageRate"))

    used = 0
    for event in db().usage_events.find({"tenantId": tenant_id}, {"units": 1, "occurredAt": 1}, session=session):
        occurred = event.get("occurredAt")
        if occurred is not None and start_d <= _as_date(occurred) <= end_d:
            used += int(_nvl(event.get("units"), 0))

    prior = 0
    for period in db().rating_periods.find(
        {
            "tenantId": tenant_id,
            "periodStart": {"$lt": _as_bson_date(start_d), "$gte": _as_bson_date(_add_months(start_d, -3))},
            "result": {"$exists": True},
        },
        {"result.rolloverUnits": 1},
        session=session,
    ):
        prior += int(_nvl(period["result"].get("rolloverUnits"), 0))
    cap = None if included is None else 2 * included
    prior = _least(_nvl(cap, prior), prior)

    rollover = _least(prior, _nvl(cap, prior))
    billable = _greatest(_nvl(None if included is None else used - rollover - included, 0), 0)
    first_tier = _least(billable, TIER_BREAK_UNITS)
    second_tier = _greatest(billable - TIER_BREAK_UNITS, 0)
    overage = None if rate is None else _round(first_tier * rate + second_tier * rate * Decimal("1.5"))

    suspended_on = sub.get("suspendedOn") if sub else None
    if sub and sub.get("statusCd") == SUBSCRIPTION_SUSPENDED and suspended_on is not None:
        suspended = _as_date(suspended_on)
        if start_d <= suspended <= end_d:
            with localcontext() as ctx:
                ctx.prec = 38
                factor = Decimal((end_d - suspended).days + 1) / Decimal((end_d - start_d).days + 1)
                billable = int(_round(billable * factor, 0))
                overage = None if overage is None else _round(overage * factor)

    log_msg("RATING", f"compute tenant={tenant_id} used={_num(_nvl(used, -1))} billable={_num(_nvl(billable, -1))}")
    return {
        "subscription": sub,
        "used_units": used,
        "quota_units": included,
        "rollover_units": rollover,
        "billable_units": billable,
        "first_tier_units": first_tier,
        "second_tier_units": second_tier,
        "overage_amount": overage,
    }


def _finalize_rating_period(tenant_id, start, end, session):
    """pkg_rating.sp_finalize_rating, the first step of sp_issue_invoice: upsert the rating
    period and its embedded result inside the issue transaction (U3 owns the standalone
    finalize_rating entrypoint; issue_invoice calls the merged implementation)."""
    start_d, end_d = _as_date(start), _as_date(end)
    period_id = f_md5_uuid(f"{tenant_id}{start_d.isoformat()}")
    subs = _period_subscriptions(tenant_id, start_d, end_d, session)
    sub_id = subs[0]["_id"] if subs else None
    periods = db().rating_periods
    period = periods.find_one({"tenantId": tenant_id, "periodStart": _as_bson_date(start_d)}, session=session)
    if period is None:
        period = {"_id": period_id, "tenantId": tenant_id, "periodStart": _as_bson_date(start_d), "periodEnd": _as_bson_date(end_d)}
        periods.insert_one(period, session=session)
    else:
        periods.update_one({"_id": period["_id"]}, {"$set": {"periodEnd": _as_bson_date(end_d)}}, session=session)

    rating = _rating_quantities(tenant_id, start_d, end_d, session)
    quota, used = rating["quota_units"], rating["used_units"]
    if quota is None or rating["billable_units"] is None or rating["overage_amount"] is None:
        raise ValueError(f"tenant {tenant_id} has no covering plan for {start_d.isoformat()}; rating result cannot be finalized")
    rated = {
        "usedUnits": Int64(used),
        "rolloverUnits": Int64(max(quota - used, 0)),
        "billableUnits": Int64(rating["billable_units"]),
        "overageAmount": _money(rating["overage_amount"]),
    }
    if period.get("result") is not None:
        periods.update_one({"_id": period["_id"]}, {"$set": {f"result.{k}": v for k, v in rated.items()}}, session=session)
        return period["_id"]
    result = {"id": f_md5_uuid(period_id), "quotaUnits": Int64(quota), "createdAt": _as_bson_date(end_d), **rated}
    if sub_id is not None:
        result["subscriptionId"] = sub_id
    periods.update_one({"_id": period["_id"]}, {"$set": {"result": result}}, session=session)
    log_msg("RATING", f"finalized period={period_id}")
    return period["_id"]


def _preview_amounts(tenant_id, start, end, session=None):
    """pkg_invoicing.compute_preview: plan code and fee, rated overage, open credit and tax."""
    start_d, end_d = _as_date(start), _as_date(end)
    plan_code = plan_fee = None
    for sub in _period_subscriptions(tenant_id, start_d, end_d, session):
        plan = _plan_doc(sub.get("planId"), session)
        if plan is not None:
            plan_code, plan_fee = plan.get("code"), _decimal(plan.get("monthlyFee"))
            break
    overage = _rating_quantities(tenant_id, start_d, end_d, session)["overage_amount"]
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
        _finalize_rating_period(tenant, start_d, end_d, session)
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


def usage_rating(tenant, start, end):
    _not_ported("pkg_rating.fn_usage_rating", "U3")


def usage_summary(tenant, start, end):
    _not_ported("pkg_rating.fn_usage_summary", "U3")


def finalize_rating(tenant, start, end):
    _not_ported("pkg_rating.sp_finalize_rating", "U3")


def overdue(as_of):
    _not_ported("pkg_dunning.fn_overdue_accounts", "U5")


def schedule_dunning(as_of):
    _not_ported("pkg_dunning.sp_schedule_dunning", "U5")


def suspend_overdue(as_of):
    _not_ported("pkg_dunning.sp_suspend_overdue", "U5")

