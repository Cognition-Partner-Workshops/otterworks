import sys
from datetime import date, datetime
from pathlib import Path

import mongomock
import pytest
from bson import Decimal128, Int64
from flask import Flask
from pymongo.errors import DuplicateKeyError, OperationFailure, WriteError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from ow_billing import NS_VALUE, Store, dunning, jobs, routes


TENANT_1 = "00000000-0000-0000-0000-000000000001"
TENANT_5 = "00000000-0000-0000-0000-000000000005"
INVOICE_1 = "60000000-0000-0000-0000-000000000001"
INVOICE_2 = "60000000-0000-0000-0000-000000000002"


def _store():
    store = Store(mongomock.MongoClient(), "ow_tp_mongodb_205236", "replay_u9_")
    store.coll("counters").insert_one(
        {"_id": "seq_billing_audit_log", "seq": Int64(0), "ns": NS_VALUE}
    )
    store.coll("counters").insert_one(
        {"_id": dunning.util.SEQ_SUBSCRIPTIONS_HIST, "seq": Int64(0), "ns": NS_VALUE}
    )
    store.coll("dunning_attempts").create_index(
        [("invoice_id", 1), ("attempt_no", 1)], unique=True
    )
    store.coll("notifications").create_index(
        [("tenant_id", 1), ("kind_cd", 1), ("sent_at", 1)], unique=True
    )
    return store


class _TransactionSession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def with_transaction(self, callback):
        return callback(None)


def _enable_transactions(monkeypatch, store):
    monkeypatch.setattr(store.client, "start_session", lambda: _TransactionSession())


def _invoice(store, invoice_id, tenant_id, issued_at, status=40, total="10.00"):
    store.coll("billing_invoices").insert_one(
        {
            "_id": invoice_id,
            "id": invoice_id,
            "tenant_id": tenant_id,
            "issued_at": issued_at,
            "total": Decimal128(total),
            "status_cd": status,
            "ns": NS_VALUE,
        }
    )


def test_overdue_outer_join_string_window_and_order():
    store = _store()
    _invoice(store, "i2", "missing", datetime(2026, 2, 1), total="2")
    _invoice(store, "i1", TENANT_1, datetime(2026, 2, 1, 1), total="1")
    _invoice(store, "same", TENANT_1, datetime(2026, 2, 28, 23), total="3")
    store.coll("tenants").insert_one({"_id": TENANT_1, "status_cd": 10, "ns": NS_VALUE})
    rows = dunning.fn_overdue_accounts(store, datetime(2026, 2, 28, 18))
    assert [row["invoice_id"] for row in rows] == ["i2", "i1"]
    assert rows[0]["tenant_status"] == "UNKNOWN"
    assert rows[1]["tenant_status"] == "active"
    assert rows[0]["total"] == 2
    assert rows[0]["days_overdue"] == 27


def test_schedule_weekend_attempts_and_deterministic_ids():
    store = _store()
    _invoice(store, INVOICE_1, TENANT_1, datetime(2026, 2, 1))
    _invoice(store, INVOICE_2, TENANT_5, datetime(2026, 2, 2))
    store.coll("dunning_attempts").insert_one(
        {
            "_id": "prior",
            "id": "prior",
            "tenant_id": TENANT_5,
            "invoice_id": INVOICE_2,
            "attempt_no": 1,
            "scheduled_for": datetime(2026, 2, 10),
            "status_cd": 20,
            "ns": NS_VALUE,
        }
    )
    assert dunning.sp_schedule_dunning(store, date(2026, 2, 14)) == 2
    rows = list(
        store.coll("dunning_attempts").find({"invoice_id": INVOICE_2}).sort("attempt_no", 1)
    )
    assert rows[1]["scheduled_for"] == datetime(2026, 2, 16)
    assert rows[1]["attempt_no"] == 2
    assert rows[1]["_id"] == dunning.util.f_md5_uuid(f"{INVOICE_2}2")
    count = store.coll("dunning_attempts").count_documents({})
    assert dunning.sp_schedule_dunning(store, date(2026, 2, 14)) == 2
    assert store.coll("dunning_attempts").count_documents({}) == count + 2
    invoice_1_attempt_2 = store.coll("dunning_attempts").find_one(
        {"invoice_id": INVOICE_1, "attempt_no": 2}
    )
    invoice_2_attempt_3 = store.coll("dunning_attempts").find_one(
        {"invoice_id": INVOICE_2, "attempt_no": 3}
    )
    assert invoice_1_attempt_2["scheduled_for"] == datetime(2026, 2, 16)
    assert invoice_2_attempt_3["scheduled_for"] == datetime(2026, 2, 16)
    assert invoice_1_attempt_2["_id"] == dunning.util.f_md5_uuid(f"{INVOICE_1}2")
    assert invoice_2_attempt_3["_id"] == dunning.util.f_md5_uuid(f"{INVOICE_2}3")


def test_schedule_duplicate_key_is_noop_but_logs(monkeypatch):
    store = _store()
    _invoice(store, INVOICE_1, TENANT_1, datetime(2026, 2, 1))
    attempts = store.coll("dunning_attempts")

    def raise_duplicate(doc):
        raise DuplicateKeyError("dup")

    monkeypatch.setattr(attempts, "insert_one", raise_duplicate)
    assert dunning.sp_schedule_dunning(store, date(2026, 2, 14)) == 0
    assert attempts.count_documents({}) == 0
    assert store.coll("billing_audit_log").count_documents({}) == 1


@pytest.mark.parametrize("error", [WriteError("bad"), OperationFailure("bad")])
def test_schedule_propagates_non_duplicate_errors(monkeypatch, error):
    store = _store()
    _invoice(store, INVOICE_1, TENANT_1, datetime(2026, 2, 1))
    monkeypatch.setattr(store.coll("dunning_attempts"), "insert_one", lambda doc: (_ for _ in ()).throw(error))
    with pytest.raises(type(error)):
        dunning.sp_schedule_dunning(store, date(2026, 2, 14))


def test_suspend_updates_active_records_once(monkeypatch):
    store = _store()
    _enable_transactions(monkeypatch, store)
    _invoice(store, "old", TENANT_5, datetime(2026, 2, 1))
    _invoice(store, "new", TENANT_1, datetime(2026, 2, 20))
    store.coll("tenants").insert_many(
        [
            {"_id": TENANT_5, "status_cd": 10, "ns": NS_VALUE},
            {"_id": TENANT_1, "status_cd": 20, "ns": NS_VALUE},
        ]
    )
    store.coll("subscriptions").insert_many(
        [
            {"_id": "a", "tenant_id": TENANT_5, "status_cd": 10, "ns": NS_VALUE},
            {"_id": "b", "tenant_id": TENANT_5, "status_cd": 20, "ns": NS_VALUE},
        ]
    )
    assert dunning.sp_suspend_overdue(store, date(2026, 2, 28)) == [TENANT_5]
    assert store.coll("tenants").find_one({"_id": TENANT_5})["status_cd"] == 20
    sub = store.coll("subscriptions").find_one({"_id": "a"})
    assert sub["status_cd"] == 20 and sub["suspended_on"] == datetime(2026, 2, 28)
    assert store.coll("subscriptions").find_one({"_id": "b"})["status_cd"] == 20
    history = store.coll("subscriptions_history").find_one({"id": "a"})
    assert history["hist_id"] == Int64(1)
    assert history["status_cd"] == 10
    assert history["suspended_on"] is None
    assert history["hist_op"] == "UPD"
    assert store.coll("subscriptions_history").count_documents({"id": "b"}) == 0
    notification = store.coll("notifications").find_one()
    assert notification["id"] == "8cd558f5-d843-8d3d-be19-fb94c21ab81f"
    assert dunning.sp_suspend_overdue(store, date(2026, 2, 28)) == []
    assert store.coll("notifications").count_documents({}) == 1


def test_jobs_disabled_and_runner(monkeypatch, capsys):
    monkeypatch.delenv("OW_BILLING_JOB_NIGHTLY_DUNNING_ENABLED", raising=False)
    monkeypatch.setattr(jobs.routes, "_store", lambda: (_ for _ in ()).throw(AssertionError()))
    assert jobs.main(["nightly-dunning"]) == 0
    assert "JOB_NIGHTLY_DUNNING is disabled" in capsys.readouterr().out
    calls = []
    monkeypatch.setattr(jobs.dunning, "sp_schedule_dunning", lambda store, day: calls.append("schedule") or 2)
    monkeypatch.setattr(jobs.dunning, "sp_suspend_overdue", lambda store, day: calls.append("suspend") or ["t"])
    assert jobs.run_nightly_dunning(object(), date(2026, 2, 28)) == {"scheduled": 2, "suspended": ["t"]}
    assert calls == ["schedule", "suspend"]


def test_dunning_blueprint_accepts_query_form_and_json(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(routes.plans_api)
    monkeypatch.setattr(routes, "_store", lambda: object())
    monkeypatch.setattr(
        routes.dunning,
        "fn_overdue_accounts",
        lambda store, day: [
            {"tenant_id": "t", "invoice_id": "i", "total": 1, "days_overdue": 2, "tenant_status": "active"}
        ],
    )
    monkeypatch.setattr(
        routes.dunning,
        "sp_schedule_dunning",
        lambda store, day: 1,
    )
    monkeypatch.setattr(
        routes.dunning,
        "sp_suspend_overdue",
        lambda store, day: ["t"],
    )
    client = app.test_client()
    assert client.get("/api/dunning/overdue?as_of=2026-02-28").get_json()[0]["days_overdue"] == 2
    assert client.post("/api/dunning/schedule", data={"as_of": "2026-02-28"}).get_json() == {
        "status": "scheduled",
        "scheduled": 1,
    }
    assert client.post("/api/dunning/suspend", json={"as_of": "2026-02-28"}).get_json() == {
        "status": "suspended",
        "tenant_ids": ["t"],
    }
    assert client.get("/api/dunning/overdue?as_of=bad").status_code == 400
    assert client.post("/api/dunning/schedule", data={"as_of": "bad"}).status_code == 400
    assert client.post("/api/dunning/suspend", json={"as_of": "bad"}).status_code == 400
