import sys
from datetime import datetime
from pathlib import Path

import pytest
from bson.decimal128 import Decimal128
from pymongo.errors import PyMongoError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import facade as facade_module
from app import app
from backends import mongo


def _matches(doc, query):
    for key, cond in query.items():
        if key == "$or":
            if not any(_matches(doc, branch) for branch in cond):
                return False
        elif isinstance(cond, dict):
            for op, operand in cond.items():
                present = key in doc
                if op == "$exists" and present != operand:
                    return False
                if op == "$lte" and not (present and doc[key] <= operand):
                    return False
                if op == "$gte" and not (present and doc[key] >= operand):
                    return False
        elif doc.get(key) != cond:
            return False
    return True


class FakeCollection:
    def __init__(self, docs):
        self.docs = docs

    def find(self, query):
        return FakeCursor(d for d in self.docs if _matches(d, query))

    def find_one(self, query, projection=None, sort=None):
        matches = [d for d in self.docs if _matches(d, query)]
        if sort:
            field, direction = sort[0]
            matches = sorted(matches, key=lambda d: d[field], reverse=direction == -1)
        return matches[0] if matches else None

    def aggregate(self, pipeline):
        tenant_id = pipeline[0]["$match"]["_id"]
        return [dict(d, status=[]) for d in self.docs if d["_id"] == tenant_id]


def _sortable(value):
    return value.to_decimal() if isinstance(value, Decimal128) else value


class FakeCursor(list):
    def sort(self, keys):
        for field, direction in reversed(keys):
            self[:] = sorted(self, key=lambda d: _sortable(d[field]), reverse=direction == -1)
        return self


class FakeDb:
    def __init__(self):
        self.plans = FakeCollection([
            {"_id": "p2", "code": "GROWTH", "tierCd": 2, "monthlyFee": Decimal128("149.00"),
             "includedUnits": 500, "overageRate": Decimal128("0.035000"), "active": True},
            {"_id": "p1", "code": "STARTER", "tierCd": 1, "monthlyFee": Decimal128("49.00"),
             "includedUnits": 100, "overageRate": Decimal128("0.055000"), "active": True},
            {"_id": "p9", "code": "LEGACY", "tierCd": 1, "monthlyFee": Decimal128("1.00"),
             "includedUnits": 1, "overageRate": Decimal128("1.000000"), "active": False},
        ])
        self.tenants = FakeCollection([{"_id": "t1", "name": "Tenant One", "statusCd": 1,
                                        "taxExempt": False}])
        self.subscriptions = FakeCollection([
            {"_id": "s1", "tenantId": "t1", "planId": "p2",
             "startsOn": datetime(2026, 1, 1), "statusCd": 20},  # noqa: DTZ001 BSON date
        ])


@pytest.fixture
def mongo_tenancy(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "oracle")
    monkeypatch.setenv("TENANCY_BACKEND", "mongo")
    monkeypatch.setattr(mongo, "_db", lambda: FakeDb())
    monkeypatch.setattr(facade_module, "_ensure", lambda _: None)
    monkeypatch.setattr(facade_module.oracle, "query", lambda *_a, **_k: [])


def test_plans_served_from_mongo_with_oracle_number_rendering(mongo_tenancy):
    response = app.test_client().get("/api/v1/billing/plans", headers={"X-User-ID": "t1"})
    assert response.status_code == 200
    assert [p["plan_code"] for p in response.json] == ["STARTER", "GROWTH"]
    assert response.json[0] == {
        "plan_id": "p1", "plan_code": "STARTER", "tier": "starter",
        "monthly_fee": "49", "included_units": "100", "overage_rate": "0.055",
    }


def test_me_and_entitlement_from_mongo(mongo_tenancy):
    client = app.test_client()
    body = client.get("/api/v1/billing/me?on=2026-03-01", headers={"X-User-ID": "t1"}).json
    assert body["tenant_id"] == "t1" and body["tax_exempt"] == "N" and body["status"] is None
    assert body["entitlement"] == [{
        "tenant_id": "t1", "plan_code": "GROWTH", "tier": "growth", "monthly_fee": "149",
        "included_units": "500", "subscription_status": "suspended", "effective_on": "2026-03-01",
    }]
    before = client.get("/api/v1/billing/entitlement?on=2025-12-31", headers={"X-User-ID": "t1"})
    assert before.json == []
    unknown = client.get("/api/v1/billing/entitlement", headers={"X-User-ID": "nobody"})
    assert unknown.json == []


def test_mongo_failure_maps_to_503(monkeypatch, mongo_tenancy):
    def boom():
        raise PyMongoError("down")

    monkeypatch.setattr(mongo, "_db", boom)
    response = app.test_client().get("/api/v1/billing/plans", headers={"X-User-ID": "t1"})
    assert response.status_code == 503


def test_default_tenancy_backend_is_oracle(monkeypatch):
    monkeypatch.delenv("TENANCY_BACKEND", raising=False)
    assert facade_module._tenancy() is facade_module.oracle
