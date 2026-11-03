import os
import uuid
from datetime import date
from decimal import Decimal

import jwt
import psycopg
from flask import Flask, abort, g, jsonify, redirect, render_template, request, url_for
from werkzeug.exceptions import HTTPException

app = Flask(__name__)

JWT_ALGORITHMS = ["HS256", "HS384"]
ADMIN_ROLE = "ADMIN"
PUBLIC_ENDPOINTS = {"health", "index", "plans"}
OPERATOR_ENDPOINTS = {"overdue", "schedule_dunning", "suspend_overdue"}
BODY_TENANT_ENDPOINTS = {"rating_preview", "rating_finalize"}


def db_connect():
    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "billing_dev"),
        user=os.getenv("DB_USER", "billing"),
        password=os.getenv("DB_PASSWORD", "billing"),
    )


def json_value(value):
    if isinstance(value, (Decimal, date)):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def rows(cursor):
    names = [column.name for column in cursor.description]
    return [{name: json_value(value) for name, value in zip(names, row)} for row in cursor]


def select(sql, params=()):
    with db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return rows(cursor)


def execute(sql, params=()):
    with db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)


def parse_uuid(value):
    try:
        return str(uuid.UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        abort(400, description="malformed identifier")


def bearer_token():
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def tenant_scope(claims):
    raw = claims.get("tenant_ids")
    if raw is None:
        raw = [claims["tenant_id"]] if claims.get("tenant_id") else []
    if not isinstance(raw, list):
        abort(401, description="invalid token")
    scope = set()
    for value in raw:
        try:
            scope.add(str(uuid.UUID(str(value))))
        except (TypeError, ValueError, AttributeError):
            abort(401, description="invalid token")
    return scope


def authenticate():
    secret = os.getenv("JWT_SECRET", "")
    token = bearer_token()
    if not secret or token is None:
        abort(401, description="authentication required")
    try:
        claims = jwt.decode(token, secret, algorithms=JWT_ALGORITHMS)
    except jwt.PyJWTError:
        abort(401, description="invalid token")
    subject = claims.get("user_id") or claims.get("sub")
    if not subject:
        abort(401, description="invalid token")
    roles = claims.get("roles") or []
    if not isinstance(roles, list):
        abort(401, description="invalid token")
    return {
        "subject": str(subject),
        "roles": {str(role) for role in roles},
        "tenant_ids": tenant_scope(claims),
    }


def invoice_tenant_id(invoice_id):
    owners = select("SELECT tenant_id FROM billing.invoices WHERE id = %s", (invoice_id,))
    if not owners:
        abort(404, description="invoice not found")
    return str(owners[0]["tenant_id"])


def requested_tenant_id():
    view_args = request.view_args or {}
    if "tenant_id" in view_args:
        return parse_uuid(view_args["tenant_id"])
    if "invoice_id" in view_args:
        return invoice_tenant_id(parse_uuid(view_args["invoice_id"]))
    if request.endpoint in BODY_TENANT_ENDPOINTS:
        payload = request.get_json(force=True, silent=True) or {}
        if "tenant_id" not in payload:
            abort(400, description="tenant_id is required")
        return parse_uuid(payload["tenant_id"])
    abort(403, description="route is not tenant scoped")


def can_access_tenant(principal, tenant_id):
    return ADMIN_ROLE in principal["roles"] or tenant_id in principal["tenant_ids"]


@app.before_request
def authorize_request():
    if request.endpoint in PUBLIC_ENDPOINTS:
        return
    principal = authenticate()
    g.principal = principal
    if request.endpoint is None:
        return
    if request.endpoint in OPERATOR_ENDPOINTS:
        if ADMIN_ROLE not in principal["roles"]:
            abort(403, description="operator role required")
        return
    if not can_access_tenant(principal, requested_tenant_id()):
        abort(403, description="tenant scope mismatch")


@app.errorhandler(HTTPException)
def http_error(error):
    response = jsonify(error=error.description)
    response.status_code = error.code
    if error.code == 401:
        response.headers["WWW-Authenticate"] = "Bearer"
    return response


@app.get("/health")
def health():
    select("SELECT 1")
    return jsonify(status="UP", service="legacy-billing")


@app.get("/")
def index():
    return render_template("index.html", plans=select("SELECT * FROM billing.fn_list_plans()"))


@app.get("/plans")
def plans():
    return jsonify(select("SELECT * FROM billing.fn_list_plans()"))


@app.get("/plans/<tenant_id>/entitlement")
def entitlement(tenant_id):
    return jsonify(select(
        "SELECT * FROM billing.fn_entitlement(%s, %s)",
        (tenant_id, request.args.get("on", "2026-02-28")),
    ))


@app.post("/plans/<tenant_id>/change")
def change_plan(tenant_id):
    execute(
        "CALL billing.sp_change_plan(%s, %s, %s)",
        (tenant_id, request.form["plan_id"], request.form["effective_on"]),
    )
    return redirect(url_for("entitlement", tenant_id=tenant_id, on=request.form["effective_on"]))


@app.post("/api/rating/preview")
def rating_preview():
    payload = request.get_json(force=True)
    return jsonify(select(
        "SELECT * FROM billing.fn_usage_rating(%s, %s, %s)",
        (payload["tenant_id"], payload["period_start"], payload["period_end"]),
    ))


@app.post("/api/rating/finalize")
def rating_finalize():
    payload = request.get_json(force=True)
    execute(
        "CALL billing.sp_finalize_rating(%s, %s, %s)",
        (payload["tenant_id"], payload["period_start"], payload["period_end"]),
    )
    return jsonify(status="finalized")


@app.get("/api/invoices/<tenant_id>/preview")
def invoice_preview(tenant_id):
    return jsonify(select(
        "SELECT * FROM billing.fn_invoice_preview(%s, %s, %s)",
        (
            tenant_id,
            request.args.get("period_start", "2026-02-01"),
            request.args.get("period_end", "2026-02-28"),
        ),
    ))


@app.post("/api/invoices/<tenant_id>/issue")
def invoice_issue(tenant_id):
    execute(
        "CALL billing.sp_issue_invoice(%s, %s, %s)",
        (
            tenant_id,
            request.form["period_start"],
            request.form["period_end"],
        ),
    )
    return jsonify(status="issued")


@app.get("/api/invoices/<invoice_id>/lines")
def invoice_lines(invoice_id):
    return jsonify(select("SELECT * FROM billing.fn_invoice_lines(%s)", (invoice_id,)))


@app.get("/api/dunning/overdue")
def overdue():
    return jsonify(select(
        "SELECT * FROM billing.fn_overdue_accounts(%s)",
        (request.args.get("as_of", "2026-02-28"),),
    ))


@app.post("/api/dunning/schedule")
def schedule_dunning():
    execute("CALL billing.sp_schedule_dunning(%s)", (request.form["as_of"],))
    return jsonify(status="scheduled")


@app.post("/api/dunning/suspend")
def suspend_overdue():
    execute("CALL billing.sp_suspend_overdue(%s)", (request.form["as_of"],))
    return jsonify(status="suspended")
