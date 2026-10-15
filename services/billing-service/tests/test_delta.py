from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from bson.decimal128 import Decimal128

from app.delta import WATERMARK, diff_documents
from app.documents import COLLECTIONS


def _invoice(n: int, status: str = "issued", issued_at: datetime | None = None) -> dict:
    return {
        "_id": UUID(int=n),
        "tenantId": UUID(int=100 + n),
        "issuedAt": issued_at or datetime(2026, 2, 28, tzinfo=UTC),
        "total": Decimal128(Decimal("53.04")),
        "status": status,
        "invoiceLines": [{"id": UUID(int=1000 + n), "lineNo": 1}],
    }


def test_identical_documents_are_unchanged() -> None:
    both = [_invoice(1), _invoice(2)]
    upserts, deletes, unchanged = diff_documents(both, both)
    assert (upserts, deletes, unchanged) == ([], [], 2)


def test_new_changed_and_removed_keys() -> None:
    source = [_invoice(1), _invoice(2, status="overdue"), _invoice(3)]
    target = [_invoice(1), _invoice(2), _invoice(4)]
    upserts, deletes, unchanged = diff_documents(source, target)
    assert [doc["_id"] for doc in upserts] == [UUID(int=2), UUID(int=3)]
    assert deletes == [UUID(int=4)]
    assert unchanged == 1


def test_sub_millisecond_source_precision_does_not_churn() -> None:
    stored = _invoice(1, issued_at=datetime(2026, 2, 28, 9, 0, 0, 123000, tzinfo=UTC))
    fresh = _invoice(1, issued_at=datetime(2026, 2, 28, 9, 0, 0, 123456, tzinfo=UTC))
    assert diff_documents([fresh], [stored]) == ([], [], 1)


def test_embedded_change_is_an_upsert() -> None:
    changed = _invoice(1)
    changed["invoiceLines"].append({"id": UUID(int=2001), "lineNo": 2})
    upserts, deletes, unchanged = diff_documents([changed], [_invoice(1)])
    assert [doc["_id"] for doc in upserts] == [UUID(int=1)] and deletes == [] and unchanged == 0


def test_no_collection_has_a_watermark_column() -> None:
    assert set(WATERMARK) == set(COLLECTIONS)
    assert all(column is None for column in WATERMARK.values())


def test_allowed_databases_is_the_committed_write_fence() -> None:
    from app.delta import allowed_databases

    assert allowed_databases() == {"billing_migration"}
