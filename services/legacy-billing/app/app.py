import os
import uuid
from datetime import date
from decimal import Decimal

import psycopg
from flask import Flask, jsonify, redirect, render_template, request, url_for

import mongo_backend
from reports import reports

app = Flask(__name__)
app.register_blueprint(reports)

BACKENDS = ("postgres", "mongo")


def backend():
    name = os.getenv("BILLING_BACKEND", "postgres")
    if name not in BACKENDS:
        raise RuntimeError(f"BILLING_BACKEND must be one of {BACKENDS}, got {name!r}")
    return name


def is_mongo():
    return backend() == "mongo"


def not_on_mongo(route):
    return (
        jsonify(
            error="not implemented on the mongo backend",
            detail=f"{route} writes through a PostgreSQL procedure; set BILLING_BACKEND=postgres",
        ),
        501,
    )


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


@app.get("/health")
def health():
    if is_mongo():
        mongo_backend.ping()
    else:
        select("SELECT 1")
    return jsonify(status="UP", service="legacy-billing", backend=backend())


def list_plans():
    if is_mongo():
        return mongo_backend.list_plans()
    return select("SELECT * FROM billing.fn_list_plans()")


@app.get("/")
def index():
    return render_template("index.html", plans=list_plans(), backend=backend())


@app.get("/plans")
def plans():
    return jsonify(list_plans())


@app.get("/plans/<tenant_id>/entitlement")
def entitlement(tenant_id):
    on = request.args.get("on", "2026-02-28")
    if is_mongo():
        return jsonify(mongo_backend.entitlement(tenant_id, on))
    return jsonify(select(
        "SELECT * FROM billing.fn_entitlement(%s, %s)",
        (tenant_id, on),
    ))


@app.post("/plans/<tenant_id>/change")
def change_plan(tenant_id):
    if is_mongo():
        return not_on_mongo("/plans/<tenant_id>/change")
    execute(
        "CALL billing.sp_change_plan(%s, %s, %s)",
        (tenant_id, request.form["plan_id"], request.form["effective_on"]),
    )
    return redirect(url_for("entitlement", tenant_id=tenant_id, on=request.form["effective_on"]))


@app.post("/api/rating/preview")
def rating_preview():
    payload = request.get_json(force=True)
    if is_mongo():
        rating = mongo_backend.usage_rating(
            payload["tenant_id"], payload["period_start"], payload["period_end"])
        rating.pop("_plan", None)
        rating["overage_amount"] = mongo_backend.num(rating["overage_amount"])
        return jsonify([rating])
    return jsonify(select(
        "SELECT * FROM billing.fn_usage_rating(%s, %s, %s)",
        (payload["tenant_id"], payload["period_start"], payload["period_end"]),
    ))


@app.post("/api/rating/finalize")
def rating_finalize():
    payload = request.get_json(force=True)
    if is_mongo():
        return not_on_mongo("/api/rating/finalize")
    execute(
        "CALL billing.sp_finalize_rating(%s, %s, %s)",
        (payload["tenant_id"], payload["period_start"], payload["period_end"]),
    )
    return jsonify(status="finalized")


@app.get("/api/invoices/<tenant_id>/preview")
def invoice_preview(tenant_id):
    start = request.args.get("period_start", "2026-02-01")
    end = request.args.get("period_end", "2026-02-28")
    if is_mongo():
        return jsonify(mongo_backend.invoice_preview(tenant_id, start, end))
    return jsonify(select(
        "SELECT * FROM billing.fn_invoice_preview(%s, %s, %s)",
        (tenant_id, start, end),
    ))


@app.post("/api/invoices/<tenant_id>/issue")
def invoice_issue(tenant_id):
    if is_mongo():
        return not_on_mongo("/api/invoices/<tenant_id>/issue")
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
    if is_mongo():
        return jsonify(mongo_backend.invoice_lines(invoice_id))
    return jsonify(select("SELECT * FROM billing.fn_invoice_lines(%s)", (invoice_id,)))


@app.get("/api/dunning/overdue")
def overdue():
    as_of = request.args.get("as_of", "2026-02-28")
    if is_mongo():
        return jsonify(mongo_backend.overdue_accounts(as_of))
    return jsonify(select(
        "SELECT * FROM billing.fn_overdue_accounts(%s)",
        (as_of,),
    ))


@app.post("/api/dunning/schedule")
def schedule_dunning():
    if is_mongo():
        return not_on_mongo("/api/dunning/schedule")
    execute("CALL billing.sp_schedule_dunning(%s)", (request.form["as_of"],))
    return jsonify(status="scheduled")


@app.post("/api/dunning/suspend")
def suspend_overdue():
    if is_mongo():
        return not_on_mongo("/api/dunning/suspend")
    execute("CALL billing.sp_suspend_overdue(%s)", (request.form["as_of"],))
    return jsonify(status="suspended")
