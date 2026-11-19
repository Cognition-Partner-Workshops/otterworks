"""Rating resources and legacy compatibility adapters."""

from flask import jsonify, request
from werkzeug.exceptions import NotFound

from .validation import date_value, json_body, required, uuid_value


def preview(tenant_id, period_start, period_end):
    from app import select

    return select("SELECT * FROM billing.fn_usage_rating(%s, %s, %s)",
                  (tenant_id, period_start, period_end))


def finalize(tenant_id, period_start, period_end):
    from app import execute

    execute("CALL billing.sp_finalize_rating(%s, %s, %s)",
            (tenant_id, period_start, period_end))
    return {"tenant_id": tenant_id, "period_start": str(period_start),
            "period_end": str(period_end), "status": "finalized"}


def period(values):
    return tuple(date_value(required(values, field), field)
                 for field in ("period_start", "period_end"))


def register(app, blueprint):
    @blueprint.get("/tenants/<tenant_id>/rating")
    def rating_preview(tenant_id):
        tenant_id = uuid_value(tenant_id, "tenant_id")
        result = preview(tenant_id, *period(request.args))
        if not result:
            raise NotFound()
        return jsonify(data=result[0])

    @blueprint.post("/tenants/<tenant_id>/rating-periods")
    def rating_finalize(tenant_id):
        tenant_id = uuid_value(tenant_id, "tenant_id")
        return jsonify(data=finalize(tenant_id, *period(json_body()))), 201

    def legacy_preview():
        payload = request.get_json(force=True)
        return jsonify(preview(payload["tenant_id"], payload["period_start"], payload["period_end"]))

    def legacy_finalize():
        payload = request.get_json(force=True)
        result = finalize(payload["tenant_id"], payload["period_start"], payload["period_end"])
        return jsonify(status=result["status"])

    app.view_functions["rating_preview"] = legacy_preview
    app.view_functions["rating_finalize"] = legacy_finalize

    @app.after_request
    def rating_deprecation(response):
        resources = {"/api/rating/preview": "rating", "/api/rating/finalize": "rating-periods"}
        if request.path in resources:
            payload = request.get_json(force=True, silent=True)
            tenant_id = payload.get("tenant_id", "{tenant_id}") if isinstance(payload, dict) else "{tenant_id}"
            path = f"/api/v1/billing/tenants/{tenant_id}/{resources[request.path]}"
            response.headers["Deprecation"] = "true"
            response.headers["Link"] = f'<{path}>; rel="successor-version"'
        return response
