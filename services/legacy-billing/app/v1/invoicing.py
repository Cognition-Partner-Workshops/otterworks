"""Versioned invoicing entrypoints and legacy request/response adapters."""

from functools import wraps

from flask import jsonify, request
from werkzeug.exceptions import HTTPException, NotFound

from .pagination import paginate
from .validation import date_value, json_body, required, uuid_value


def _period(values, legacy):
    if legacy:
        return values["period_start"], values["period_end"]
    return tuple(date_value(required(values, field), field)
                 for field in ("period_start", "period_end"))


def _lines(kind, identifier, values, legacy=False):
    from app import select

    if not legacy:
        identifier = uuid_value(identifier, "tenant_id" if kind == "preview" else "invoice_id")
    if kind == "preview":
        if not legacy and not select("SELECT id FROM billing.tenants WHERE id = %s", (identifier,)):
            raise NotFound()
        result = select("SELECT * FROM billing.fn_invoice_preview(%s, %s, %s)",
                        (identifier, *_period(values, legacy)))
    else:
        result = select("SELECT * FROM billing.fn_invoice_lines(%s)", (identifier,))
    if legacy:
        return jsonify(result)
    result = [{({"line_no": "number", "line_type": "type"}.get(key, key)): value
               for key, value in row.items()} for row in result]
    return jsonify(paginate(result))


def _issue(tenant_id, values, legacy=False):
    from app import execute, select

    if not legacy:
        tenant_id = uuid_value(tenant_id, "tenant_id")
    start, end = _period(values, legacy)
    execute("CALL billing.sp_issue_invoice(%s, %s, %s)", (tenant_id, start, end))
    if legacy:
        return jsonify(status="issued")
    invoice = select(
        "SELECT i.id, i.tenant_id, p.period_start, p.period_end, i.status "
        "FROM billing.invoices i JOIN billing.rating_periods p ON p.id = i.period_id "
        "WHERE i.tenant_id = %s AND p.tenant_id = %s "
        "AND p.period_start = %s AND p.period_end = %s",
        (tenant_id, tenant_id, start, end),
    )[0]
    response = jsonify(data=invoice)
    response.status_code = 201
    response.headers["Location"] = f"/api/v1/billing/invoices/{invoice['id']}/lines"
    return response


def register(app, blueprint):
    @blueprint.get("/tenants/<tenant_id>/invoice-preview")
    def invoicing_preview(tenant_id):
        return _lines("preview", tenant_id, request.args)

    @blueprint.post("/tenants/<tenant_id>/invoices")
    def invoicing_issue(tenant_id):
        return _issue(tenant_id, json_body())

    @blueprint.get("/invoices/<invoice_id>/lines")
    def invoicing_lines(invoice_id):
        return _lines("persisted", invoice_id, request.args)

    def adapter(successor):
        def decorate(handler):
            @wraps(handler)
            def wrapped(**kwargs):
                try:
                    response = app.make_response(handler(**kwargs))
                except HTTPException as error:
                    response = error.get_response()
                except Exception as error:
                    response = app.handle_exception(error)
                response.headers["Deprecation"] = "true"
                response.headers["Link"] = f'<{successor.format(**kwargs)}>; rel="successor-version"'
                return response
            return wrapped
        return decorate

    @adapter("/api/v1/billing/tenants/{tenant_id}/invoice-preview")
    def preview_adapter(tenant_id):
        return _lines("preview", tenant_id, {
            "period_start": request.args.get("period_start", "2026-02-01"),
            "period_end": request.args.get("period_end", "2026-02-28"),
        }, legacy=True)

    @adapter("/api/v1/billing/tenants/{tenant_id}/invoices")
    def issue_adapter(tenant_id):
        return _issue(tenant_id, request.form, legacy=True)

    @adapter("/api/v1/billing/invoices/{invoice_id}/lines")
    def lines_adapter(invoice_id):
        return _lines("persisted", invoice_id, request.args, legacy=True)

    app.view_functions["invoice_preview"] = preview_adapter
    app.view_functions["invoice_issue"] = issue_adapter
    app.view_functions["invoice_lines"] = lines_adapter
