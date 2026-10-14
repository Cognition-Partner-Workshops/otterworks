from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from bson.decimal128 import Decimal128

from app.documents import subscription_document, tenant_document
from app.load import build_documents

TENANT = UUID("00000000-0000-0000-0000-000000000004")


def test_subscription_document_omits_null_dates() -> None:
    document = subscription_document(
        {
            "id": UUID("20000000-0000-0000-0000-000000000001"),
            "tenant_id": TENANT,
            "plan_id": UUID("10000000-0000-0000-0000-000000000001"),
            "starts_on": date(2026, 1, 1),
            "ends_on": None,
            "status": "active",
            "suspended_on": None,
        }
    )
    assert document["startsOn"] == datetime(2026, 1, 1, tzinfo=UTC)
    assert "endsOn" not in document and "suspendedOn" not in document


def test_tenant_embeds_credit_notes_in_issued_order() -> None:
    notes = [
        {
            "id": UUID(int=2),
            "tenant_id": TENANT,
            "issued_on": date(2026, 2, 1),
            "amount": Decimal("30.00"),
            "remaining_amount": Decimal("30.00"),
        },
        {
            "id": UUID(int=1),
            "tenant_id": TENANT,
            "issued_on": date(2026, 2, 1),
            "amount": Decimal("30.00"),
            "remaining_amount": Decimal("30.00"),
        },
    ]
    tables = {
        "plans": [],
        "tenants": [{"id": TENANT, "name": "Delta", "tax_exempt": False, "status": "active"}],
        "credit_notes": notes,
        "subscriptions": [],
    }
    tenant = build_documents(tables)["tenants"][0]
    assert tenant == tenant_document(tables["tenants"][0], notes)
    assert [note["id"] for note in tenant["creditNotes"]] == [UUID(int=1), UUID(int=2)]
    assert tenant["creditNotes"][0]["amount"] == Decimal128("30.00")
