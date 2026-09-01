"""Unit tests for the converted stored logic.

Parity against `procs/oracle/transcripts/` is the acceptance evidence for this unit; these
tests cover the behaviours a transcript can only show indirectly -- the arithmetic quirks the
conversion had to keep, and the trigger rules no recorded scenario exercises head-on -- so a
regression names itself instead of surfacing as a changed number in one scenario.

Run with the migration venv: `/home/ubuntu/.mongo-venv/bin/python -m pytest .migration/stored_logic`.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
from decimal import Decimal

import billing_logic as bl
import inventory
import pytest
import transcripts as tr
from bson.decimal128 import Decimal128
from mongo_store import MongoStore
from pymongo.errors import DuplicateKeyError

# --- an in-memory stand-in for the collections the store talks to --------------------


class FakeResult:
    def __init__(self, matched_count):
        self.matched_count = matched_count


class FakeCollection:
    def __init__(self, db=None):
        self.docs = {}
        self.unique = []
        self.indexes = []
        self.db = db
        self.sessions = []  # the session each write carried, so "outside the unit" is testable

    def create_index(self, keys, unique=False, **kwargs):
        if unique:
            self.unique.append([k for k, _ in keys])
        self.indexes.append((keys, kwargs))

    def _match(self, doc, query):
        for key, expected in query.items():
            value = doc.get(key)
            if isinstance(expected, dict) and "$size" in expected:
                # As in MongoDB, $size matches an array of that length -- never a missing field.
                if not isinstance(value, list) or len(value) != expected["$size"]:
                    return False
            elif isinstance(expected, dict) and "$in" in expected:
                if value not in expected["$in"]:
                    return False
            elif value != expected:
                return False
        return True

    def _writing(self, session):
        self.sessions.append(session)
        if self.db is not None:
            self.db.enlist(session)

    def find(self, query=None, session=None):
        return [d for d in self.docs.values() if self._match(d, query or {})]

    def find_one(self, query=None, session=None):
        found = self.find(query)
        return found[0] if found else None

    def _violates_unique(self, doc):
        return any(
            all(other.get(k) == doc.get(k) for k in keys)
            for keys in self.unique
            for other in self.docs.values()
            if other["_id"] != doc.get("_id")
        )

    def insert_one(self, doc, session=None):
        self._writing(session)
        doc = dict(doc)
        doc.setdefault("_id", f"auto-{len(self.docs) + 1}")
        if doc["_id"] in self.docs or self._violates_unique(doc):
            raise DuplicateKeyError("duplicate")
        self.docs[doc["_id"]] = doc

    def insert_many(self, docs, session=None):
        for doc in docs:
            self.insert_one(doc, session=session)

    def replace_one(self, query, doc, upsert=False, session=None):
        self._writing(session)
        existing = self.find_one(query)
        if existing is None and not upsert:
            return FakeResult(0)
        self.docs[doc["_id"]] = dict(doc)
        return FakeResult(1)

    def update_one(self, query, update, upsert=False, session=None):
        self._writing(session)
        doc = self.find_one(query)
        if doc is None:
            if not upsert:
                return FakeResult(0)
            doc = {k: v for k, v in query.items() if not isinstance(v, dict)}
            doc.update(update.get("$setOnInsert", {}))
            self.docs[doc["_id"]] = doc
        doc.update(update.get("$set", {}))
        for path, value in update.get("$push", {}).items():
            doc.setdefault(path, []).append(value)
        return FakeResult(1)

    def drop(self):
        self.docs.clear()


class FakeSession:
    """Enough of a client session to tell committed work from rolled-back work."""

    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def start_transaction(self):
        return self


class FakeClient:
    def __init__(self, db):
        self.db = db

    def start_session(self):
        return _Transaction(self.db)


class _Transaction(FakeSession):
    """Snapshots every collection on entry and restores the sessioned ones on failure, which
    is what a rolled-back transaction looks like from the caller's side."""

    def __enter__(self):
        self.snapshot = {name: copy.deepcopy(c.docs) for name, c in self.db.collections.items()}
        self.db.enlisted = set()
        return self

    def __exit__(self, exc_type, *rest):
        if exc_type is not None:
            for name in self.db.enlisted:
                self.db[name].docs = self.snapshot.get(name, {})
        return False


class FakeDB:
    def __init__(self, seed=None, transactional=False):
        self.collections = {}
        self.enlisted = set()
        self.client = FakeClient(self) if transactional else None
        for name, docs in (seed or {}).items():
            for doc in docs:
                self[name].insert_one(doc)

    def __getitem__(self, name):
        return self.collections.setdefault(name, FakeCollection(self))

    def enlist(self, session):
        """Only writes that carry the session take part in the transaction."""
        if session is not None:
            self.enlisted.update(
                name for name, coll in self.collections.items() if coll.sessions[-1:] == [session]
            )


CODES = [
    {"_id": "SUB_STATUS:10", "code_type": "SUB_STATUS", "code_val": 10, "code_desc": "active"},
    {"_id": "SUB_STATUS:20", "code_type": "SUB_STATUS", "code_val": 20, "code_desc": "suspended"},
    {"_id": "SUB_STATUS:30", "code_type": "SUB_STATUS", "code_val": 30, "code_desc": "cancelled"},
    {"_id": "TENANT_STATUS:10", "code_type": "TENANT_STATUS", "code_val": 10, "code_desc": "active"},
    {"_id": "TENANT_STATUS:20", "code_type": "TENANT_STATUS", "code_val": 20,
     "code_desc": "suspended"},
    {"_id": "INV_STATUS:40", "code_type": "INV_STATUS", "code_val": 40, "code_desc": "overdue"},
    {"_id": "DUN_STATUS:10", "code_type": "DUN_STATUS", "code_val": 10, "code_desc": "scheduled"},
    {"_id": "NOTIF_KIND:3", "code_type": "NOTIF_KIND", "code_val": 3, "code_desc": "suspension"},
]

TENANT = "tenant-1"
PLAN = "plan-1"


def store_with(transactional=False, **collections):
    seed = {"codes": CODES, **collections}
    store = MongoStore(FakeDB(seed, transactional=transactional))
    store.ensure_indexes()
    return store


def plan_doc(included=100, rate="0.05", fee="49.00"):
    return {
        "_id": PLAN,
        "code": "GROWTH",
        "tier_cd": 2,
        "monthly_fee": Decimal128(fee),
        "included_units": included,
        "overage_rate": Decimal128(rate),
        "legacy": {"active_yn": "Y"},
    }


def sub_doc(status=bl.SUB_ACTIVE, suspended_on=None, starts="2026-01-01"):
    return {
        "_id": "sub-1",
        "tenant_id": TENANT,
        "plan_id": PLAN,
        "starts_on": dt.datetime.fromisoformat(starts).replace(tzinfo=dt.UTC),
        "ends_on": None,
        "status_cd": status,
        "status": "active",
        "suspended_on": None if suspended_on is None else
        dt.datetime.fromisoformat(suspended_on).replace(tzinfo=dt.UTC),
    }


def usage(units, day="2026-02-10", kind=1):
    return {
        "_id": f"usage-{day}-{units}",
        "tenant_id": TENANT,
        "kind_cd": kind,
        "units": units,
        "occurred_at": dt.datetime.fromisoformat(day).replace(tzinfo=dt.UTC),
    }


FEB = (dt.date(2026, 2, 1), dt.date(2026, 2, 28))


# --- arithmetic the conversion had to keep -------------------------------------------


def test_md5_uuid_matches_the_oracle_digest():
    """The estate's derived keys are only idempotent if this stays bit-identical; the value is
    the suspension notification id recorded in the DUNNING-004 transcript."""
    assert (
        bl.md5_uuid("00000000-0000-0000-0000-000000000005suspension2026-02-28")
        == "8cd558f5-d843-8d3d-be19-fb94c21ab81f"
    )


def test_rounding_is_half_away_from_zero_not_bankers():
    assert bl.rnd(Decimal("2.345")) == Decimal("2.35")
    assert bl.rnd(Decimal("2.355")) == Decimal("2.36")


def test_second_tier_starts_after_101_units_and_costs_half_again():
    store = store_with(plans=[plan_doc()], subscriptions=[sub_doc()], usage_events=[usage(300)])
    r = bl.compute_rating(store, TENANT, *FEB)
    assert (r.billable_units, r.first_tier_units, r.second_tier_units) == (200, 101, 99)
    assert r.overage_amount == Decimal("12.48")  # 101*0.05 + 99*0.05*1.5


def test_a_tenant_without_a_plan_bills_nothing_rather_than_everything():
    """`GREATEST(NVL(used - rollover - included, 0), 0)` with a NULL allowance: the estate
    charges nothing at all, and the conversion must not start charging for the usage."""
    store = store_with(subscriptions=[sub_doc()], usage_events=[usage(300)])
    r = bl.compute_rating(store, TENANT, *FEB)
    assert (r.used_units, r.billable_units, r.overage_amount) == (300, 0, None)


def test_rollover_is_capped_at_twice_the_allowance():
    store = store_with(
        plans=[plan_doc()],
        subscriptions=[sub_doc()],
        usage_events=[usage(500)],
        rating_periods=[
            {
                "_id": "period-jan",
                "tenant_id": TENANT,
                "period_start": dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
                "results": [{"result_id": "r1", "rollover_units": 900}],
            }
        ],
    )
    r = bl.compute_rating(store, TENANT, *FEB)
    assert r.rollover_units == 200
    assert r.billable_units == 200  # 500 - 200 - 100


def test_rollover_older_than_three_months_is_not_counted():
    store = store_with(
        plans=[plan_doc()],
        subscriptions=[sub_doc()],
        usage_events=[usage(500)],
        rating_periods=[
            {
                "_id": "period-old",
                "tenant_id": TENANT,
                "period_start": dt.datetime(2025, 9, 1, tzinfo=dt.UTC),
                "results": [{"result_id": "r1", "rollover_units": 150}],
            }
        ],
    )
    assert bl.compute_rating(store, TENANT, *FEB).rollover_units == 0


def test_a_suspension_mid_period_prorates_by_the_days_that_remain():
    store = store_with(
        plans=[plan_doc()],
        subscriptions=[sub_doc(status=bl.SUB_SUSPENDED, suspended_on="2026-02-14")],
        usage_events=[usage(300)],
    )
    r = bl.compute_rating(store, TENANT, *FEB)
    assert r.billable_units == 107  # 200 * 15/28, rounded half up
    assert r.overage_amount == Decimal("6.69")


def test_finalize_records_the_unused_allowance_as_rollover():
    """The rollover the routine *writes* is the unused quota, not the rollover it consumed --
    a real difference, and the number the next period reads."""
    store = store_with(plans=[plan_doc()], subscriptions=[sub_doc()], usage_events=[usage(30)])
    period_id = bl.finalize_rating(store, TENANT, *FEB)
    result = store.collection("rating_periods").find_one({"_id": period_id})["results"][0]
    assert (result["used_units"], result["rollover_units"]) == (30, 70)


def test_weekend_dunning_is_pushed_to_monday():
    assert bl.next_business_day(dt.date(2026, 2, 14)) == dt.date(2026, 2, 16)  # Sat -> Mon
    assert bl.next_business_day(dt.date(2026, 2, 15)) == dt.date(2026, 2, 16)  # Sun -> Mon
    assert bl.next_business_day(dt.date(2026, 2, 17)) == dt.date(2026, 2, 17)


def test_credit_burn_down_charges_each_note_the_undiminished_balance():
    """The estate decrements one running counter against every note, so a second note is
    reduced by the credit the first already absorbed. Preserved deliberately: the recorded
    invoice transcripts show the resulting balances."""
    store = store_with(
        plans=[plan_doc()],
        subscriptions=[sub_doc()],
        usage_events=[usage(30)],
        credit_notes=[
            {"_id": "cn-1", "tenant_id": TENANT, "issued_on": dt.datetime(2026, 1, 1,
             tzinfo=dt.UTC), "remaining_amount": Decimal128("10.00")},
            {"_id": "cn-2", "tenant_id": TENANT, "issued_on": dt.datetime(2026, 1, 2,
             tzinfo=dt.UTC), "remaining_amount": Decimal128("40.00")},
        ],
        tenants=[{"_id": TENANT, "status_cd": 10, "tax_exempt": False}],
    )
    bl.issue_invoice(store, TENANT, *FEB)
    remaining = {c["_id"]: c["remaining_amount"].to_decimal() for c in store.credit_notes(TENANT)}
    assert remaining == {"cn-1": Decimal("0.00"), "cn-2": Decimal("0.00")}


def test_a_tax_exempt_tenant_is_charged_no_tax():
    store = store_with(
        plans=[plan_doc()],
        subscriptions=[sub_doc()],
        usage_events=[usage(30)],
        tenants=[{"_id": TENANT, "status_cd": 10, "tax_exempt": True}],
    )
    assert bl.compute_preview(store, TENANT, *FEB).tax == Decimal(0)


# --- trigger rules the store enforces -------------------------------------------------


def test_a_cancelled_subscription_cannot_be_reactivated():
    """TRG_SUB_NO_UNCANCEL, now a rule of the only writer of status_cd."""
    store = store_with(subscriptions=[sub_doc(status=bl.SUB_CANCELLED)])
    store.update_subscription("sub-1", {"status_cd": bl.SUB_ACTIVE})
    updated = store.collection("subscriptions").find_one({"_id": "sub-1"})
    assert (updated["status_cd"], updated["status"]) == (bl.SUB_CANCELLED, "cancelled")


def test_every_subscription_update_snapshots_the_previous_row():
    """TRG_SUBSCRIPTIONS_HIST: the snapshot is the row as it was, not as it became."""
    store = store_with(subscriptions=[sub_doc()])
    store.update_subscription("sub-1", {"status_cd": bl.SUB_SUSPENDED})
    updated = store.collection("subscriptions").find_one({"_id": "sub-1"})
    assert updated["status_cd"] == bl.SUB_SUSPENDED
    assert [(h["hist_id"], h["hist_op"], h["status_cd"]) for h in updated["history"]] == [
        (1, "UPD", bl.SUB_ACTIVE)
    ]


def test_the_audit_log_is_purged_by_a_ttl_index_not_a_nightly_delete():
    """JOB_PURGE_AUDIT_LOG's 90-day DELETE, rehomed."""
    store = store_with()
    keys, options = store.collection("billing_audit_log").indexes[0]
    assert keys == "logged_at"
    assert options["expireAfterSeconds"] == 90 * 24 * 3600


def test_a_logging_failure_is_no_longer_swallowed():
    """The autonomous transaction wrapped `WHEN OTHERS THEN NULL`; a lost audit trail was
    invisible. The converted write raises."""
    class RefusingCollection(FakeCollection):
        def insert_one(self, doc):
            raise DuplicateKeyError("the audit write failed")

    store = store_with()
    store.db.collections["billing_audit_log"] = RefusingCollection()
    with pytest.raises(DuplicateKeyError):
        store.log("RATING", "an audit write that the datastore rejects")


# --- fail-closed behaviour ------------------------------------------------------------


def test_scheduling_the_same_attempt_twice_does_not_double_it():
    invoice = {
        "_id": "inv-1",
        "tenant_id": TENANT,
        "status_cd": bl.INVOICE_OVERDUE,
        "issued_at": dt.datetime(2026, 1, 15, tzinfo=dt.UTC),
        "total": Decimal128("59.06"),
    }
    store = store_with(subscription_invoices=[invoice], tenants=[{"_id": TENANT, "status_cd": 10}])
    assert bl.schedule_dunning(store, dt.date(2026, 2, 17)) == 1
    attempts = store.dunning_attempts("inv-1")
    assert [int(a["attempt_no"]) for a in attempts] == [1]


def test_suspension_is_idempotent_for_the_same_day():
    invoice = {
        "_id": "inv-1",
        "tenant_id": TENANT,
        "status_cd": bl.INVOICE_OVERDUE,
        "issued_at": dt.datetime(2026, 1, 15, tzinfo=dt.UTC),
        "total": Decimal128("59.06"),
    }
    store = store_with(
        subscription_invoices=[invoice],
        subscriptions=[sub_doc()],
        tenants=[{"_id": TENANT, "status_cd": 10}],
    )
    bl.suspend_overdue(store, dt.date(2026, 2, 28))
    bl.suspend_overdue(store, dt.date(2026, 2, 28))
    assert len(store.notifications(TENANT)) == 1
    assert store.tenant(TENANT)["status_cd"] == bl.TENANT_SUSPENDED


def test_a_dunning_run_with_nothing_to_suspend_logs_nothing_and_completes():
    """`sp_suspend_overdue` logs one line per tenant it actually suspends, inside the IF -- a
    nightly run over an estate with nothing overdue is a normal, quiet, successful run."""
    store = store_with(tenants=[{"_id": TENANT, "status_cd": 10}])
    bl.suspend_overdue(store, dt.date(2026, 2, 28))
    assert store.tenant(TENANT)["status_cd"] == bl.TENANT_ACTIVE
    assert not [e for e in store.collection("billing_audit_log").docs
                if e["module"] == "DUNNING"]


def test_a_cancellation_that_lands_mid_update_is_not_reverted():
    """TRG_SUB_NO_UNCANCEL held for concurrent sessions too. Read-then-write cannot: the row
    is cancelled after this caller read it as active, and an unguarded write would put it
    back to suspended and reuse hist_id 1."""
    store = store_with(subscriptions=[sub_doc()])
    subscriptions = store.collection("subscriptions")
    original = subscriptions.update_one
    cancellations = []

    def cancel_first_then_update(query, update, **kwargs):
        if not cancellations:  # another session gets there between the read and the write
            cancellations.append(True)
            doc = subscriptions.docs["sub-1"]
            doc["status_cd"], doc["status"] = bl.SUB_CANCELLED, "cancelled"
            doc.setdefault("history", []).append({"hist_id": 1, "hist_op": "UPD"})
        return original(query, update, **kwargs)

    subscriptions.update_one = cancel_first_then_update
    store.update_subscription("sub-1", {"status_cd": bl.SUB_SUSPENDED})

    updated = subscriptions.find_one({"_id": "sub-1"})
    assert (updated["status_cd"], updated["status"]) == (bl.SUB_CANCELLED, "cancelled")
    assert [h["hist_id"] for h in updated["history"]] == [1, 2]


def test_a_subscription_that_never_settles_fails_instead_of_looping():
    store = store_with(subscriptions=[sub_doc()])
    subscriptions = store.collection("subscriptions")
    subscriptions.update_one = lambda *a, **k: FakeResult(0)
    with pytest.raises(RuntimeError):
        store.update_subscription("sub-1", {"status_cd": bl.SUB_SUSPENDED})


# --- procedure-level atomicity --------------------------------------------------------


def invoicing_store():
    return store_with(
        transactional=True,
        plans=[plan_doc()],
        subscriptions=[sub_doc()],
        usage_events=[usage(300)],
        credit_notes=[{"_id": "cn-1", "tenant_id": TENANT,
                       "issued_on": dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
                       "remaining_amount": Decimal128("10.00")}],
        tenants=[{"_id": TENANT, "status_cd": 10, "tax_exempt": False}],
    )


def test_a_write_that_fails_midway_through_issuing_leaves_no_half_invoice():
    """sp_issue_invoice committed once. If the credit burn-down fails after the invoice was
    written, an invoice charging a credit that was never applied must not survive."""
    store = invoicing_store()

    def refuse(*args, **kwargs):
        raise DuplicateKeyError("the credit note write failed")

    store.collection("credit_notes").update_one = refuse
    with pytest.raises(DuplicateKeyError):
        bl.issue_invoice(store, TENANT, *FEB)

    assert store.collection("subscription_invoices").docs == {}
    assert store.collection("rating_periods").docs == {}
    assert store.credit_notes(TENANT)[0]["remaining_amount"].to_decimal() == Decimal("10.00")


def test_issuing_an_invoice_commits_its_writes_as_one_unit():
    store = invoicing_store()
    for collection in store.db.collections.values():
        collection.sessions.clear()  # forget the seeding writes
    bl.issue_invoice(store, TENANT, *FEB)
    for name in ("subscription_invoices", "rating_periods", "credit_notes"):
        assert all(s is not None for s in store.collection(name).sessions), name


def test_the_audit_trail_is_written_outside_the_transaction_that_it_records():
    """PKG_OW_UTIL.log_msg was an autonomous transaction: its entries survived the rollback of
    the work that logged them, and still do."""
    store = invoicing_store()
    bl.issue_invoice(store, TENANT, *FEB)
    assert store.collection("billing_audit_log").sessions
    assert all(s is None for s in store.collection("billing_audit_log").sessions)


def test_repeating_a_plan_change_does_not_overwrite_the_subscription_it_made():
    """The new subscription's id is derived, so a repeat collides with the row the first call
    created -- ORA-00001 in the estate. Overwriting would uncancel it and lose its history,
    and the close-out the retry had already written must not survive either."""
    store = store_with(transactional=True, subscriptions=[sub_doc(starts="2026-01-01")])
    bl.change_plan(store, TENANT, "plan-2", dt.date(2026, 3, 1))
    new_id = bl.md5_uuid(f"{TENANT}plan-22026-03-01")
    store.update_subscription(new_id, {"status_cd": bl.SUB_CANCELLED})
    before = copy.deepcopy(store.collection("subscriptions").docs)

    with pytest.raises(DuplicateKeyError):
        bl.change_plan(store, TENANT, "plan-2", dt.date(2026, 3, 1))
    assert store.collection("subscriptions").docs == before


# --- transcripts are only evidence while a run vouches for them ------------------------


def record(scenario, value="1"):
    return {"scenario": scenario, "module": "rating", "business_fields": {"total": value},
            "probes": {}}


def test_an_interrupted_recording_leaves_nothing_to_grade(tmp_path):
    """mongo_record withdraws the manifest before it records; a run that dies after that
    leaves transcripts on disk, and they must not be graded as the current run."""
    tr.publish([record("RATING-001")], tmp_path, "run-1", {}, ["RATING-001"])
    tr.invalidate(tmp_path)  # what the recorder does before replaying
    with pytest.raises(SystemExit):
        tr.published(tmp_path)


def test_a_partial_recording_is_not_published_at_all(tmp_path):
    with pytest.raises(SystemExit):
        tr.publish([record("RATING-001")], tmp_path, "run-1", {}, ["RATING-001", "RATING-002"])
    assert not (tmp_path / tr.MANIFEST).exists()


def test_a_transcript_left_behind_by_an_earlier_run_is_refused(tmp_path):
    tr.publish([record("RATING-001"), record("RATING-002")], tmp_path, "run-1", {},
               ["RATING-001", "RATING-002"])
    tr.publish([record("RATING-001")], tmp_path, "run-2", {}, ["RATING-001"])
    with pytest.raises(SystemExit):
        tr.published(tmp_path)  # RATING-002 is still on disk, from the run before


def test_an_edited_transcript_is_refused(tmp_path):
    tr.publish([record("RATING-001")], tmp_path, "run-1", {}, ["RATING-001"])
    path = tmp_path / "rating" / "RATING-001.json"
    path.write_text(json.dumps(record("RATING-001", value="2")))
    with pytest.raises(SystemExit):
        tr.published(tmp_path)


def test_a_complete_run_is_graded(tmp_path):
    tr.publish([record("RATING-001")], tmp_path, "run-1", {"module": None}, ["RATING-001"])
    manifest, records = tr.published(tmp_path)
    assert manifest["run_id"] == "run-1"
    assert list(records) == ["RATING-001"]


def test_a_short_parse_of_the_estate_fails_instead_of_reporting_an_empty_pass():
    """The unit contract's empty-input rule: 17 known objects are expected, so a parse that
    finds none is a failed extraction."""
    empty = {"packages": [], "routines": [], "triggers": [], "jobs": [], "sequences": []}
    problems = inventory.check(empty, inventory.json.loads(inventory.DISPOSITIONS.read_text()))
    assert any("failed extraction" in p for p in problems)


def test_every_plsql_object_in_the_estate_has_a_disposition_that_resolves():
    found = inventory.scan()
    dispositions = inventory.json.loads(inventory.DISPOSITIONS.read_text())
    assert inventory.check(found, dispositions) == []
