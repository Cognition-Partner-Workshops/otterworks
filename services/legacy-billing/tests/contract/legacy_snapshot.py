"""Capture status, exact response bytes and content type against any git ref.

Run with the same disposable DB_* environment as the contract tests.
Pass --ref origin/demo-odl for the before side, omit for the working tree.
"""

import argparse
import base64
import json
import subprocess
import sys
import types

from conftest import ROOT, reset_seed

TENANT = "00000000-0000-0000-0000-000000000001"
PLAN = "10000000-0000-0000-0000-000000000002"
PERIOD = {"period_start": "2026-02-01", "period_end": "2026-02-28"}


def cases():
    yield "health", {"path": "/health"}, {"path": "/health", "method": "POST"}
    yield "index", {"path": "/"}, {"path": "/", "method": "POST"}
    yield "plans", {"path": "/plans"}, {"path": "/plans", "method": "POST"}
    yield "entitlement", {"path": f"/plans/{TENANT}/entitlement"}, {"path": f"/plans/{TENANT}/entitlement?on=bad"}
    yield "change", {"path": f"/plans/{TENANT}/change", "method": "POST", "data": {"plan_id": PLAN, "effective_on": "2026-03-01"}}, {"path": f"/plans/{TENANT}/change", "method": "POST"}
    for action in ("preview", "finalize"):
        yield f"rating_{action}", {"path": f"/api/rating/{action}", "method": "POST", "json": {"tenant_id": TENANT, **PERIOD}}, {"path": f"/api/rating/{action}", "method": "POST", "data": "{", "content_type": "application/json"}
    yield "invoice_preview", {"path": f"/api/invoices/{TENANT}/preview"}, {"path": f"/api/invoices/{TENANT}/preview?period_start=bad"}
    yield "invoice_issue", {"path": f"/api/invoices/{TENANT}/issue", "method": "POST", "data": PERIOD}, {"path": f"/api/invoices/{TENANT}/issue", "method": "POST"}
    # The seeded overdue invoice has persisted lines.
    yield "invoice_lines", {"path": "/api/invoices/60000000-0000-0000-0000-000000000001/lines"}, {"path": "/api/invoices/bad/lines"}
    yield "overdue", {"path": "/api/dunning/overdue"}, {"path": "/api/dunning/overdue?as_of=bad"}
    for action in ("schedule", "suspend"):
        yield action, {"path": f"/api/dunning/{action}", "method": "POST", "data": {"as_of": "2026-02-28"}}, {"path": f"/api/dunning/{action}", "method": "POST"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ref")
    args = parser.parse_args()
    if args.ref:
        source = subprocess.check_output(["git", "show", f"{args.ref}:services/legacy-billing/app/app.py"], text=True)
        module = types.ModuleType("legacy_baseline")
        module.__file__ = str(ROOT / "app/app.py")
        sys.modules[module.__name__] = module
        exec(compile(source, module.__file__, "exec"), module.__dict__)
        app = module.app
    else:
        from app import app
    result = {}
    for name, normal, error in cases():
        for suffix, request in (("success", normal), ("error", error)):
            reset_seed()
            response = app.test_client().open(**request)
            result[f"{name}:{suffix}"] = {
                "status": response.status_code,
                "content_type": response.content_type,
                "body_base64": base64.b64encode(response.data).decode(),
            }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
