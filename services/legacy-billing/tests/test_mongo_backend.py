import sys
from datetime import datetime
from pathlib import Path

import pytest
from pymongo.errors import DuplicateKeyError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import backends
from backends import mongo

from app import app


class FakeCollection:
    def __init__(self, docs=None, fail=None):
        self.docs = list(docs or [])
        self.fail = fail
        self.inserted = []

    def insert_one(self, doc):
        if self.fail:
            raise self.fail
        if any(d["_id"] == doc["_id"] for d in self.docs + self.inserted):
            raise DuplicateKeyError("duplicate key")
        self.inserted.append(doc)


@pytest.fixture
def mongo_backend(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "mongo")
    monkeypatch.setenv("USAGE_INTERNAL_TOKEN", "test-token")
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
    yield


def _post_event(client, **overrides):
    payload = {
        "event_id": "11111111-2222-3333-4444-555555555555",
        "tenant_id": "t-1",
        "kind": "api",
        "units": 5,
        "occurred_at": "2026-02-10T10:00:00Z",
    }
    payload.update(overrides)
    return client.post(
        "/internal/usage/events",
        json=payload,
        headers={"X-Internal-Token": "test-token"},
    )


def test_backend_name_mongo(mongo_backend):
    assert backends.backend_name() == "mongo"


def test_record_usage_event_rejects_bad_units(mongo_backend):
    with pytest.raises(ValueError, match="units must be > 0"):
        mongo.record_usage_event("e1", "t-1", datetime(2026, 2, 1), 0, "api")


def test_record_usage_event_rejects_unknown_kind(mongo_backend):
    with pytest.raises(ValueError, match="unknown usage kind bogus"):
        mongo.record_usage_event("e1", "t-1", datetime(2026, 2, 1), 5, "bogus")


def test_usage_event_records(mongo_backend, monkeypatch):
    collection = FakeCollection()
    monkeypatch.setattr(mongo, "_collection", lambda name: collection)
    response = _post_event(app.test_client())
    assert response.status_code == 201
    assert response.get_json() == {"status": "recorded"}
    doc = collection.inserted[0]
    assert doc["_id"] == "11111111-2222-3333-4444-555555555555"
    assert doc["occurredAt"] == datetime(2026, 2, 10, 10, 0)
    assert int(doc["units"]) == 5
    assert int(doc["kindCd"]) == 1


def test_usage_event_duplicate(mongo_backend, monkeypatch):
    collection = FakeCollection(
        docs=[{"_id": "11111111-2222-3333-4444-555555555555"}]
    )
    monkeypatch.setattr(mongo, "_collection", lambda name: collection)
    response = _post_event(app.test_client())
    assert response.status_code == 200
    assert response.get_json() == {"status": "duplicate"}


def test_usage_event_units_422(mongo_backend, monkeypatch):
    monkeypatch.setattr(mongo, "_collection", lambda name: FakeCollection())
    response = _post_event(app.test_client(), units=0)
    assert response.status_code == 400


def test_usage_event_unavailable(mongo_backend, monkeypatch):
    from pymongo.errors import ConnectionFailure

    collection = FakeCollection(fail=ConnectionFailure("down"))
    monkeypatch.setattr(mongo, "_collection", lambda name: collection)
    response = _post_event(app.test_client())
    assert response.status_code == 503


def test_usage_returns_summary_rating_events(mongo_backend, monkeypatch):
    monkeypatch.setattr(
        mongo,
        "usage_summary",
        lambda *_a: [{"kind": "api", "event_count": "1", "units": "5"}],
    )
    monkeypatch.setattr(mongo, "usage_events", lambda *_a: [])
    response = app.test_client().get(
        "/api/v1/billing/usage?period_start=2026-02-01&period_end=2026-02-28",
        headers={"X-User-ID": "t-1"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert set(body) == {"summary", "rating", "events"}
    assert body["rating"] == []
    assert body["summary"][0]["kind"] == "api"
