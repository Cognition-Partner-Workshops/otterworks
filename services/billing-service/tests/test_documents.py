from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from bson.decimal128 import Decimal128

from app.documents import rating_period_document, subscription_document, tenant_document
from app.load import build_documents
from app.repository import _day_bounds

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


def test_rating_period_without_a_result_has_no_rating_subdocument() -> None:
    row = {
        "id": UUID(int=7),
        "tenant_id": TENANT,
        "period_start": date(2026, 2, 1),
        "period_end": date(2026, 2, 28),
    }
    document = rating_period_document(row, None)
    assert "rating" not in document
    assert document["periodEnd"] == datetime(2026, 2, 28, tzinfo=UTC)


def test_day_bounds_cover_the_end_day_including_the_maximum_date() -> None:
    bounds = _day_bounds(date(2026, 2, 1), date(2026, 2, 28))
    assert bounds == {
        "$gte": datetime(2026, 2, 1, tzinfo=UTC),
        "$lt": datetime(2026, 3, 1, tzinfo=UTC),
    }
    last = _day_bounds(date(2026, 2, 1), date.max)
    assert last["$lte"].date() == date.max
