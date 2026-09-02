import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from ow_billing import routes
from ow_billing.plans import SUB_STATUS, TIER, decode
from ow_billing.util import f_dt2str, f_md5_uuid, f_str2dt


def test_utility_functions():
    assert f_md5_uuid("abc") == "90015098-3cd2-4fb0-d696-3f7d28e17f72"
    derived = f_md5_uuid(
        "00000000-0000-0000-0000-000000000001"
        "10000000-0000-0000-0000-0000000000022026-03-01"
    )
    assert len(derived) == 36
    assert [derived[index] for index in (8, 13, 18, 23)] == ["-", "-", "-", "-"]
    assert f_dt2str(datetime(2026, 3, 1)) == "01-MAR-26"
    assert f_dt2str(date(2026, 3, 1)) == "01-MAR-26"
    assert f_str2dt("01-MAR-26") == datetime(2026, 3, 1)
    assert f_str2dt("31-FEB-24") is None
    assert f_str2dt("N/A") is None
    assert f_str2dt(None) is None


def test_decode_tables():
    assert decode(TIER, 1) == "starter"
    assert decode(TIER, None) == "UNKNOWN"
    assert decode(SUB_STATUS, 30) == "cancelled"


def test_entitlement_lookups_use_store_prefixed_names():
    class Collection:
        def __init__(self, name):
            self.name = name
            self.pipeline = None

        def aggregate(self, pipeline):
            self.pipeline = pipeline
            return []

    class Store:
        def __init__(self):
            self.collections = {}

        def coll(self, name):
            return self.collections.setdefault(name, Collection(f"replay_u6_{name}"))

    store = Store()
    assert routes.plans.fn_entitlement(store, "tenant-1", date(2026, 2, 28)) is None
    lookups = [
        stage["$lookup"]
        for stage in store.collections["subscriptions"].pipeline
        if "$lookup" in stage
    ]
    assert [lookup["from"] for lookup in lookups] == [
        "replay_u6_tenants",
        "replay_u6_plans",
    ]


def test_entrypoint_response_shapes(monkeypatch):
    store = object()
    monkeypatch.setattr(
        routes.plans,
        "fn_list_plans",
        lambda value: [
            {
                "plan_id": "p1",
                "code": "STARTER",
                "tier": "starter",
                "monthly_fee": Decimal("49"),
                "included_units": 100,
                "overage_rate": Decimal("0.123456"),
            }
        ],
    )
    assert routes.call_entrypoint(store, "billing.fn_list_plans", {}) == [
        {
            "plan_id": "p1",
            "code": "STARTER",
            "tier": "starter",
            "monthly_fee": "49.00",
            "included_units": 100,
            "overage_rate": "0.123456",
        }
    ]

    monkeypatch.setattr(
        routes.plans,
        "fn_entitlement",
        lambda value, tenant_id, on: {
            "tenant_id": tenant_id,
            "plan_code": "STARTER",
            "tier": "starter",
            "monthly_fee": Decimal("49"),
            "included_units": 100,
            "subscription_status": "active",
            "effective_on": on,
        },
    )
    assert routes.call_entrypoint(
        store,
        "billing.fn_entitlement",
        {"tenant_id": "t1", "as_of": "2026-02-28"},
    ) == {
        "tenant_id": "t1",
        "plan_code": "STARTER",
        "tier": "starter",
        "monthly_fee": "49.00",
        "included_units": 100,
        "subscription_status": "active",
        "effective_on": "2026-02-28",
    }

    monkeypatch.setattr(
        routes.plans,
        "sp_change_plan",
        lambda value, tenant_id, plan_id, effective_on: [
            {
                "plan_id": "p1",
                "starts_on": date(2026, 1, 1),
                "ends_on": date(2026, 2, 28),
                "status": "active",
            },
            {
                "plan_id": plan_id,
                "starts_on": effective_on,
                "ends_on": None,
                "status": "active",
            },
        ],
    )
    assert routes.call_entrypoint(
        store,
        "billing.sp_change_plan",
        {"tenant_id": "t1", "plan_id": "p2", "effective_on": "2026-03-01"},
    ) == {
        "latest_plan": "p2",
        "latest_start": "2026-03-01",
        "subscriptions": [
            {
                "plan_id": "p1",
                "starts_on": "2026-01-01",
                "ends_on": "2026-02-28",
                "status": "active",
            },
            {
                "plan_id": "p2",
                "starts_on": "2026-03-01",
                "ends_on": None,
                "status": "active",
            },
        ],
    }


def test_plans_blueprint_status_codes(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(routes.plans_api)
    monkeypatch.setattr(routes, "_store", lambda: object())
    monkeypatch.setattr(routes.plans, "fn_list_plans", lambda store: [])
    monkeypatch.setattr(routes.plans, "fn_entitlement", lambda store, tenant_id, on: None)
    monkeypatch.setattr(
        routes.plans,
        "sp_change_plan",
        lambda store, tenant_id, plan_id, effective_on: (_ for _ in ()).throw(
            LookupError("unknown")
        ),
    )
    client = app.test_client()
    assert client.get("/api/plans").status_code == 200
    response = client.get("/api/tenants/t1/entitlement")
    assert response.status_code == 404
    assert response.get_json() == {"detail": "entitlement not found"}
    response = client.post(
        "/api/tenants/t1/plan-change",
        json={"plan_id": "p2", "effective_on": "2026-03-01"},
    )
    assert response.status_code == 400
    assert response.get_json() == {"detail": "invalid plan change"}
