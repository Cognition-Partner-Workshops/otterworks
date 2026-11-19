"""Dunning REST resources and compatibility adapters."""

from functools import wraps

from flask import jsonify, request
from werkzeug.exceptions import HTTPException

from .pagination import paginate
from .validation import date_value, json_body, required


def overdue_invoices(as_of):
    from app import select

    return [{("id" if key == "invoice_id" else key): value
             for key, value in row.items()} for row in select(
        "SELECT * FROM billing.fn_overdue_accounts(%s)", (as_of,))]


def run_dunning(action, as_of):
    from app import execute

    if action == "schedule":
        execute("CALL billing.sp_schedule_dunning(%s)", (as_of,))
        status = "scheduled"
    else:
        execute("CALL billing.sp_suspend_overdue(%s)", (as_of,))
        status = "suspended"
    return {"as_of": str(as_of), "status": status}


def register(app, blueprint):
    @blueprint.get("/overdue-invoices")
    def dunning_overdue():
        as_of = date_value(required(request.args, "as_of"), "as_of")
        return jsonify(paginate(overdue_invoices(as_of)))

    @blueprint.post("/dunning-schedules")
    def dunning_schedule():
        as_of = date_value(required(json_body(), "as_of"), "as_of")
        return jsonify(data=run_dunning("schedule", as_of)), 201

    @blueprint.post("/suspensions")
    def dunning_suspend():
        as_of = date_value(required(json_body(), "as_of"), "as_of")
        return jsonify(data=run_dunning("suspend", as_of)), 201

    def adapter(path):
        def decorate(handler):
            @wraps(handler)
            def wrapped():
                try:
                    response = app.make_response(handler())
                except HTTPException as error:
                    response = error.get_response()
                except Exception as error:
                    response = app.handle_exception(error)
                response.headers["Deprecation"] = "true"
                response.headers["Link"] = f'</api/v1/billing/{path}>; rel="successor-version"'
                return response
            return wrapped
        return decorate

    @adapter("overdue-invoices")
    def legacy_overdue():
        items = overdue_invoices(request.args.get("as_of", "2026-02-28"))
        return jsonify([{("invoice_id" if key == "id" else key): value
                         for key, value in row.items()} for row in items])

    @adapter("dunning-schedules")
    def legacy_schedule():
        return jsonify(status=run_dunning("schedule", request.form["as_of"])["status"])

    @adapter("suspensions")
    def legacy_suspend():
        return jsonify(status=run_dunning("suspend", request.form["as_of"])["status"])

    app.view_functions["overdue"] = legacy_overdue
    app.view_functions["schedule_dunning"] = legacy_schedule
    app.view_functions["suspend_overdue"] = legacy_suspend
