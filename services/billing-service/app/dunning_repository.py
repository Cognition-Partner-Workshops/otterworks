from __future__ import annotations

from datetime import UTC
from typing import Any
from uuid import UUID

from pymongo.errors import DuplicateKeyError

from app.domain import DunningAttemptRow, InvoiceRow
from app.dunning import NotificationRow
from app.repository import MongoInvoicingRepository, _invoice_row


def _notification_row(document: dict[str, Any]) -> NotificationRow:
    return NotificationRow(
        notification_id=document["_id"],
        tenant_id=document["tenantId"],
        kind=document["kind"],
        sent_at=document["sentAt"].replace(tzinfo=UTC),
    )


class MongoDunningRepository(MongoInvoicingRepository):
    """Dunning owns notifications. It reads invoices and tenants, appends dunning attempts
    through the invoicing owner API (append_dunning_attempt) and suspends tenants through
    the plans owner API (suspend_tenant); it never writes those collections itself."""

    def list_overdue_invoices(self) -> list[InvoiceRow]:
        cursor = self.database.invoices.find({"status": "overdue"}, session=self.session)
        return [_invoice_row(document) for document in cursor]

    def list_dunning_attempts(self) -> list[tuple[UUID, DunningAttemptRow]]:
        """Every (invoiceId, attempt) across invoices, in (invoiceId, attemptNo) order."""
        cursor = self.database.invoices.find(
            {"dunningAttempts.0": {"$exists": True}}, session=self.session
        )
        attempts = [
            (invoice.invoice_id, attempt)
            for invoice in map(_invoice_row, cursor)
            for attempt in invoice.dunning_attempts
        ]
        return sorted(attempts, key=lambda item: (item[0].int, item[1].attempt_no))

    def list_notifications(self, kind: str, tenant_id: UUID | None = None) -> list[NotificationRow]:
        query: dict[str, Any] = {"kind": kind}
        if tenant_id is not None:
            query["tenantId"] = tenant_id
        rows = [
            _notification_row(document)
            for document in self.database.notifications.find(query, session=self.session)
        ]
        return sorted(rows, key=lambda row: (row.tenant_id.int, row.sent_at))

    def insert_notification(self, notification: NotificationRow) -> bool:
        """INSERT ... WHERE NOT EXISTS (tenant_id, kind, sent_at): the unique index on
        (tenantId, kind, sentAt) is the guard. Returns whether a document was inserted."""
        try:
            self.database.notifications.insert_one(
                {
                    "_id": notification.notification_id,
                    "tenantId": notification.tenant_id,
                    "kind": notification.kind,
                    "sentAt": notification.sent_at,
                },
                session=self.session,
            )
        except DuplicateKeyError:
            return False
        return True
