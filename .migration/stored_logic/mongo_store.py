"""The persistence half of the converted estate: the collections the routines read and write.

Everything the PL/SQL did with SQL against OW_BILLING happens here, against the migrated
`ow_tp_mongodb_orc1` collections. Three Oracle mechanisms are absorbed into this layer
rather than into the business routines:

* `TRG_SUB_NO_UNCANCEL` -- a cancelled subscription can never leave the cancelled state.
  `update_subscription` is the only writer of `status_cd`, so the rule holds for every
  caller, the way a BEFORE UPDATE trigger did.
* `TRG_SUBSCRIPTIONS_HIST` -- the full-row version snapshot, now appended to the
  subscription's own `history` array instead of a side table keyed by a sequence.
* The denormalized `status`/`kind` labels the migration writes beside each numeric code:
  every write path refreshes them, so a document never carries a label that disagrees with
  its code.

Sequences are retired: `_id` is the natural key everywhere, and audit-log entries key on
their own content and timestamp instead of `SEQ_BILLING_AUDIT_LOG.NEXTVAL`.
"""
from __future__ import annotations

import contextlib
import datetime as dt
from decimal import Decimal

from bson.decimal128 import Decimal128
from bson.int64 import Int64
from pymongo.errors import DuplicateKeyError

AUDIT_RETENTION_DAYS = 90


def to_dt(value):
    """Dates are stored as BSON dates at UTC midnight, per the migration's tolerances."""
    if value is None or isinstance(value, dt.datetime):
        return value
    return dt.datetime(value.year, value.month, value.day, tzinfo=dt.UTC)


def to_dec(value):
    return None if value is None else Decimal128(Decimal(str(value)))


class MongoStore:
    """Collection-name indirection keeps the routines pointed at whichever copy of the estate
    is being exercised -- the migrated collections, or the replay copies the parity recorder
    builds -- without the routines knowing which."""

    MAX_UPDATE_ATTEMPTS = 5

    def __init__(self, db, prefix=""):
        self.db = db
        self.prefix = prefix
        self._session = None
        self._codes = {
            (c["code_type"], int(c["code_val"])): c["code_desc"] for c in db["codes"].find()
        }

    def collection(self, name):
        return self.db[f"{self.prefix}{name}"]

    @property
    def _in(self):
        """The session keyword every read and write inside a unit of work carries."""
        return {} if self._session is None else {"session": self._session}

    @contextlib.contextmanager
    def unit_of_work(self):
        """A PL/SQL procedure's transaction: every write it makes commits together or not at
        all. Without this a converted procedure that fails partway leaves the earlier writes
        behind -- for `sp_issue_invoice` that means an invoice whose credit notes were already
        burnt down, and a retry that bills a different total.

        Nested calls join the outermost unit, the way a nested PL/SQL call joined its
        caller's transaction rather than starting one of its own. The audit log deliberately
        stays outside it: `PKG_OW_UTIL.log_msg` was an autonomous transaction whose entries
        survived a rollback of the work that logged them.
        """
        client = getattr(self.db, "client", None)
        if self._session is not None or client is None:
            yield
            return
        with client.start_session() as session, session.start_transaction():
            self._session = session
            try:
                yield
            finally:
                self._session = None

    # --- PKG_OW_UTIL ------------------------------------------------------------------

    def code_desc(self, code_type, code_val):
        if code_val is None:
            return "UNKNOWN(-1)"
        return self._codes.get((code_type, int(code_val)), f"UNKNOWN({int(code_val)})")

    def log(self, module, message):
        """`PKG_OW_UTIL.log_msg`. The autonomous transaction that committed on its own and
        swallowed every error becomes an ordinary insert; a logging failure is no longer
        invisible, and JOB_PURGE_AUDIT_LOG's hardcoded 90-day DELETE is now the TTL index
        `ensure_indexes` creates."""
        # No session: an autonomous transaction's entries outlive the caller's rollback.
        self.collection("billing_audit_log").insert_one(
            {
                "module": module[:30],
                "message": message[:4000],
                "logged_at": dt.datetime.now(dt.UTC),
            }
        )

    def ensure_indexes(self):
        """The uniqueness the estate relied on, plus the retention JOB_PURGE_AUDIT_LOG ran."""
        self.collection("dunning_attempts").create_index(
            [("invoice_id", 1), ("attempt_no", 1)], unique=True
        )
        self.collection("notifications").create_index(
            [("tenant_id", 1), ("kind_cd", 1), ("sent_at", 1)], unique=True
        )
        self.collection("billing_audit_log").create_index(
            "logged_at", expireAfterSeconds=AUDIT_RETENTION_DAYS * 24 * 3600
        )

    # --- reads ------------------------------------------------------------------------

    def plans(self):
        return list(self.collection("plans").find(**self._in))

    def plan(self, plan_id):
        if plan_id is None:
            return None
        return self.collection("plans").find_one({"_id": plan_id}, **self._in)

    def tenant(self, tenant_id):
        return self.collection("tenants").find_one({"_id": tenant_id}, **self._in)

    def subscriptions(self, tenant_id):
        return list(self.collection("subscriptions").find({"tenant_id": tenant_id}, **self._in))

    def usage_events(self, tenant_id):
        return list(self.collection("usage_events").find({"tenant_id": tenant_id}, **self._in))

    def rating_periods(self, tenant_id):
        return list(self.collection("rating_periods").find({"tenant_id": tenant_id}, **self._in))

    def credit_notes(self, tenant_id):
        return list(self.collection("credit_notes").find({"tenant_id": tenant_id}, **self._in))

    def invoice(self, invoice_id):
        return self.collection("subscription_invoices").find_one({"_id": invoice_id}, **self._in)

    def invoices_by_status(self, status_cd):
        return list(self.collection("subscription_invoices").find({"status_cd": status_cd},
                                                                  **self._in))

    def dunning_attempts(self, invoice_id):
        return list(self.collection("dunning_attempts").find({"invoice_id": invoice_id},
                                                             **self._in))

    def notifications(self, tenant_id=None):
        query = {} if tenant_id is None else {"tenant_id": tenant_id}
        return list(self.collection("notifications").find(query, **self._in))

    # --- writes -----------------------------------------------------------------------

    def update_subscription(self, subscription_id, changes):
        """The only writer of `status_cd`, so TRG_SUB_NO_UNCANCEL's rule lives here.

        Read-then-write is not enough: between reading the row and writing it another caller
        can cancel the subscription, and an unconditional write would then reactivate it and
        give two snapshots the same `hist_id`. The write is guarded by the state it was
        decided on -- the status and the history length it read -- so a row that moved under
        it fails to match and the decision is taken again against what is there now.
        """
        subscriptions = self.collection("subscriptions")
        for _ in range(self.MAX_UPDATE_ATTEMPTS):
            current = subscriptions.find_one({"_id": subscription_id}, **self._in)
            if current is None:
                return
            history_length = len(current.get("history", []))

            wanted = dict(changes)
            if current["status_cd"] == 30:  # TRG_SUB_NO_UNCANCEL
                wanted["status_cd"] = 30
            update = {k: to_dt(v) if isinstance(v, dt.date) else v
                      for k, v in wanted.items() if k != "status_cd"}
            if "status_cd" in wanted:
                update["status_cd"] = Int64(wanted["status_cd"])
                update["status"] = self.code_desc("SUB_STATUS", wanted["status_cd"])

            history = {k: v for k, v in current.items() if k not in ("_id", "history", "status")}
            history["hist_id"] = Int64(history_length + 1)
            history["hist_op"] = "UPD"
            history["legacy"] = {
                "hist_dt": dt.datetime.now(dt.UTC).strftime("%d-%b-%y %H:%M:%S").upper()
            }

            # `$size: 0` matches an empty array but not a missing one, and a subscription that
            # has never been updated has no history field at all.
            unchanged_history = ({"$size": history_length} if history_length
                                 else {"$in": [None, []]})
            result = subscriptions.update_one(
                {"_id": subscription_id, "status_cd": current["status_cd"],
                 "history": unchanged_history},
                {"$set": update, "$push": {"history": history}},
                **self._in,
            )
            if result.matched_count:
                return
        raise RuntimeError(
            f"subscription {subscription_id} changed under every one of "
            f"{self.MAX_UPDATE_ATTEMPTS} attempts to update it"
        )

    def insert_subscription(self, doc):
        """An insert, never an upsert. `sp_change_plan` derives the new subscription's id from
        the tenant, plan and effective date, so a repeat of the same plan change collides with
        the row the first one created; in the estate that is ORA-00001 and the procedure fails.
        Overwriting instead would let a retry resurrect a cancelled subscription and drop its
        history -- exactly what `update_subscription` refuses to do.
        """
        doc = dict(doc)
        doc["starts_on"] = to_dt(doc["starts_on"])
        doc["status_cd"] = Int64(doc["status_cd"])
        doc["status"] = self.code_desc("SUB_STATUS", doc["status_cd"])
        self.collection("subscriptions").insert_one(doc, **self._in)

    def update_tenant_status(self, tenant_id, status_cd):
        self.collection("tenants").update_one(
            {"_id": tenant_id},
            {
                "$set": {
                    "status_cd": Int64(status_cd),
                    "status": self.code_desc("TENANT_STATUS", status_cd),
                }
            },
            **self._in,
        )

    def upsert_rating_period(self, period_id, tenant_id, period_start, period_end):
        self.collection("rating_periods").update_one(
            {"_id": period_id},
            {
                "$set": {
                    "tenant_id": tenant_id,
                    "period_start": to_dt(period_start),
                    "period_end": to_dt(period_end),
                },
                "$setOnInsert": {"results": []},
            },
            upsert=True,
            **self._in,
        )

    def upsert_rating_result(self, period_id, result):
        result = dict(result)
        result["created_at"] = to_dt(result["created_at"])
        result["overage_amount"] = to_dec(result["overage_amount"])
        for key in ("used_units", "quota_units", "rollover_units", "billable_units"):
            if result[key] is not None:
                result[key] = Int64(result[key])
        period = self.collection("rating_periods").find_one({"_id": period_id}, **self._in)
        results = [r for r in (period or {}).get("results", []) if r["result_id"] != result["result_id"]]
        self.collection("rating_periods").update_one(
            {"_id": period_id}, {"$set": {"results": [*results, result]}}, **self._in
        )

    def upsert_invoice(self, invoice_id, tenant_id, period_id, issued_at, status_cd):
        self.collection("subscription_invoices").update_one(
            {"_id": invoice_id},
            {
                "$set": {
                    "tenant_id": tenant_id,
                    "period_id": period_id,
                    "issued_at": to_dt(issued_at),
                    "status_cd": Int64(status_cd),
                    "status": self.code_desc("INV_STATUS", status_cd),
                },
                "$setOnInsert": {
                    "subtotal": to_dec(0),
                    "tax": to_dec(0),
                    "total": to_dec(0),
                    "lines": [],
                },
            },
            upsert=True,
            **self._in,
        )

    def set_invoice_lines(self, invoice_id, lines):
        stored = [{**line, "amount": to_dec(line["amount"])} for line in lines]
        self.collection("subscription_invoices").update_one(
            {"_id": invoice_id}, {"$set": {"lines": stored}}, **self._in
        )

    def update_invoice_totals(self, invoice_id, subtotal, tax, total):
        self.collection("subscription_invoices").update_one(
            {"_id": invoice_id},
            {"$set": {"subtotal": to_dec(subtotal), "tax": to_dec(tax), "total": to_dec(total)}},
            **self._in,
        )

    def update_credit_note(self, credit_note_id, remaining_amount):
        self.collection("credit_notes").update_one(
            {"_id": credit_note_id}, {"$set": {"remaining_amount": to_dec(remaining_amount)}},
            **self._in,
        )

    def insert_dunning_attempt(self, doc):
        """Returns whether the attempt was new. The original swallowed every exception here;
        only the duplicate that ON CONFLICT DO NOTHING meant is ignored now."""
        doc = dict(doc)
        doc["scheduled_for"] = to_dt(doc["scheduled_for"])
        doc["attempt_no"] = Int64(doc["attempt_no"])
        doc["status_cd"] = Int64(doc["status_cd"])
        doc["status"] = self.code_desc("DUN_STATUS", doc["status_cd"])
        try:
            self.collection("dunning_attempts").insert_one(doc, **self._in)
        except DuplicateKeyError:
            return False
        return True

    def insert_notification_once(self, doc):
        doc = dict(doc)
        doc["sent_at"] = to_dt(doc["sent_at"])
        doc["kind_cd"] = Int64(doc["kind_cd"])
        doc["kind"] = self.code_desc("NOTIF_KIND", doc["kind_cd"])
        try:
            self.collection("notifications").insert_one(doc, **self._in)
        except DuplicateKeyError:
            return False
        return True
