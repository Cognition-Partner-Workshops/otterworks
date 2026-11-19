"""Plans REST handlers and legacy request/response adapters."""

from flask import jsonify, redirect, request, url_for
from werkzeug.exceptions import NotFound

from .pagination import paginate
from .validation import date_value, json_body, required, uuid_value


def list_plans():
    from app import select
    return [{("id" if key == "plan_id" else key): value for key, value in row.items()}
            for row in select("SELECT * FROM billing.fn_list_plans()")]


def entitlement(tenant_id, on):
    from app import select
    return [{("status" if key == "subscription_status" else key): value
             for key, value in row.items()}
            for row in select("SELECT * FROM billing.fn_entitlement(%s, %s)", (tenant_id, on))]


def change_plan(tenant_id, plan_id, effective_on):
    from app import execute
    execute("CALL billing.sp_change_plan(%s, %s, %s)", (tenant_id, plan_id, effective_on))


def single_entitlement(tenant_id, on):
    result = entitlement(tenant_id, on)
    if not result:
        raise NotFound()
    return result[0]


def register(app, blueprint):
    @blueprint.get("/plans")
    def plans_list():
        return jsonify(paginate(list_plans()))

    @blueprint.get("/tenants/<tenant_id>/entitlement")
    def plans_entitlement(tenant_id):
        tenant_id = uuid_value(tenant_id, "tenant_id")
        on = date_value(required(request.args, "on"), "on")
        return jsonify(data=single_entitlement(tenant_id, on))

    @blueprint.post("/tenants/<tenant_id>/subscriptions")
    def plans_subscribe(tenant_id):
        tenant_id = uuid_value(tenant_id, "tenant_id")
        payload = json_body()
        plan_id = uuid_value(required(payload, "plan_id"), "plan_id")
        effective_on = date_value(required(payload, "effective_on"), "effective_on")
        change_plan(tenant_id, plan_id, effective_on)
        response = jsonify(data=single_entitlement(tenant_id, effective_on))
        response.status_code = 201
        response.headers["Location"] = url_for(
            "billing_v1.plans_entitlement", tenant_id=tenant_id, on=effective_on)
        return response

    def legacy_plans():
        return jsonify([{("plan_id" if key == "id" else key): value
                         for key, value in row.items()} for row in list_plans()])

    def legacy_entitlement(tenant_id):
        return jsonify([{("subscription_status" if key == "status" else key): value
                         for key, value in row.items()}
                        for row in entitlement(tenant_id, request.args.get("on", "2026-02-28"))])

    def legacy_change(tenant_id):
        change_plan(tenant_id, request.form["plan_id"], request.form["effective_on"])
        return redirect(url_for("entitlement", tenant_id=tenant_id, on=request.form["effective_on"]))

    for endpoint, adapter in (("plans", legacy_plans), ("entitlement", legacy_entitlement),
                              ("change_plan", legacy_change)):
        if endpoint in app.view_functions:
            app.view_functions[endpoint] = adapter

    @app.after_request
    def deprecate_plans(response):
        parts = request.path.strip("/").split("/")
        successor = None
        if parts == ["plans"]:
            successor = "/api/v1/billing/plans"
        elif len(parts) == 3 and parts[0] == "plans" and parts[2] in ("entitlement", "change"):
            resource = "entitlement" if parts[2] == "entitlement" else "subscriptions"
            successor = f"/api/v1/billing/tenants/{parts[1]}/{resource}"
        if successor:
            response.headers["Deprecation"] = "true"
            response.headers["Link"] = f'<{successor}>; rel="successor-version"'
        return response
