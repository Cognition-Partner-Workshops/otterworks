import os
from datetime import date
from decimal import Decimal
from uuid import UUID

import psycopg
import pytest
from psycopg.rows import dict_row

from app.db import SEED
from app.rating_domain import finalize_rating
from app.repository import PostgresRatingRepository

TENANT = UUID(int=7)
START = date(2026, 2, 1)
END = date(2026, 2, 28)


@pytest.fixture
def repository():
    url = os.environ.get("BILLING_TEST_DATABASE_URL")
    if not url:
        pytest.skip("BILLING_TEST_DATABASE_URL must name a disposable migrated database")
    connection = psycopg.connect(url, row_factory=dict_row)
    try:
        connection.execute("""
            TRUNCATE billing_svc.rating_results, billing_svc.rating_periods,
                     billing_svc.usage_events, billing_svc.subscriptions,
                     billing_svc.plans, billing_svc.tenants
        """)
        connection.execute(SEED.read_text())
        yield PostgresRatingRepository(connection)
    finally:
        connection.rollback()
        connection.close()


def test_finalize_persists_and_conflict_preserves_insert_only_columns(repository):
    tz = repository.session_timezone()
    finalize_rating(repository, TENANT, START, END, session_timezone=tz)
    original = repository.rating_results(TENANT, START)[0]
    assert (
        original.used_units,
        original.quota_units,
        original.rollover_units,
        original.billable_units,
        original.overage_amount,
    ) == (260, 100, 0, 160, Decimal("10.42"))
    repository.connection.execute(
        "UPDATE billing_svc.subscriptions SET plan_id = %s WHERE tenant_id = %s",
        (UUID("10000000-0000-0000-0000-000000000002"), TENANT),
    )
    repository.connection.execute(
        "UPDATE billing_svc.usage_events SET units = 25 WHERE tenant_id = %s",
        (TENANT,),
    )
    finalize_rating(repository, TENANT, START, date(2026, 2, 27), session_timezone=tz)
    updated = repository.rating_results(TENANT, START)[0]
    assert (
        updated.id,
        updated.period_id,
        updated.quota_units,
        updated.subscription_id,
        updated.created_at,
    ) == (
        original.id,
        original.period_id,
        original.quota_units,
        original.subscription_id,
        original.created_at,
    )
    assert (
        updated.used_units,
        updated.rollover_units,
        updated.billable_units,
        updated.overage_amount,
    ) == (25, 475, 0, Decimal("0.00"))
    period = repository.connection.execute(
        "SELECT period_end FROM billing_svc.rating_periods WHERE id = %s",
        (original.period_id,),
    ).fetchone()
    assert period["period_end"] == date(2026, 2, 27)


def test_finalize_failure_rolls_back_period_with_transaction(repository, monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise psycopg.OperationalError("write failed")

    monkeypatch.setattr(repository, "upsert_rating_result", unavailable)
    with (
        pytest.raises(psycopg.OperationalError, match="write failed"),
        repository.connection.transaction(),
    ):
        finalize_rating(
            repository, TENANT, START, END, session_timezone=repository.session_timezone()
        )
    assert (
        repository.connection.execute(
            "SELECT id FROM billing_svc.rating_periods WHERE tenant_id = %s AND period_start = %s",
            (TENANT, START),
        ).fetchall()
        == []
    )
