from datetime import date
from decimal import Decimal

import pytest

PERIOD = {"period_start": "2026-02-01", "period_end": "2026-02-28"}
GROWTH_PLAN = "10000000-0000-0000-0000-000000000002"


def tenant(number):
    return f"00000000-0000-0000-0000-{number:012d}"


def entitlement_url(number):
    return f"/plans/{tenant(number)}/entitlement"


def invoice_url(number, action):
    return f"/api/invoices/{tenant(number)}/{action}"


def get_json(response):
    if response.status_code != 200 or not response.is_json:
        pytest.fail(f"Expected JSON with HTTP 200; got {response.status}")
    return response.get_json()


def invoice_record(db, number):
    return db.execute(
        """
        SELECT i.id, i.subtotal, i.tax, i.total, i.status
        FROM billing.invoices i
        JOIN billing.rating_periods p ON p.id = i.period_id
        WHERE i.tenant_id = %s AND p.period_start = %s
        """,
        (tenant(number), PERIOD["period_start"]),
    ).fetchone()


def test_catalog_and_homepage_list_only_active_plans(client, db):
    db.execute("UPDATE billing.plans SET active = false WHERE code = 'SCALE'")

    plans = get_json(client.get("/plans"))
    assert [(p["code"], p["monthly_fee"], p["included_units"]) for p in plans] == [
        ("STARTER", "49.00", 100),
        ("GROWTH", "149.00", 500),
    ]
    page = client.get("/")
    assert page.status_code == 200
    assert "STARTER — 49.00 / 100 units" in page.text
    assert "GROWTH — 149.00 / 500 units" in page.text
    assert "SCALE" not in page.text


def test_entitlement_before_subscription_start_is_empty(client):
    assert get_json(client.get(entitlement_url(1), query_string={"on": "2025-12-31"})) == []


def test_plan_change_switches_quota_on_effective_date_for_only_one_tenant(client):
    effective_on = "2026-03-01"
    changed = client.post(
        f"/plans/{tenant(1)}/change",
        data={"plan_id": GROWTH_PLAN, "effective_on": effective_on},
        follow_redirects=True,
    )

    assert [response.status_code for response in changed.history] == [302]
    assert get_json(changed) == [{
        "tenant_id": tenant(1),
        "plan_code": "GROWTH",
        "tier": "growth",
        "monthly_fee": "149.00",
        "included_units": 500,
        "subscription_status": "active",
        "effective_on": effective_on,
    }]
    [previous] = get_json(client.get(entitlement_url(1), query_string={"on": "2026-02-28"}))
    assert (previous["plan_code"], previous["included_units"]) == ("STARTER", 100)
    [neighbor] = get_json(client.get(entitlement_url(4), query_string={"on": effective_on}))
    assert (neighbor["plan_code"], neighbor["included_units"]) == ("STARTER", 100)


def test_plan_change_missing_date_rejects_request_without_changing_plan(client):
    response = client.post(f"/plans/{tenant(1)}/change", data={"plan_id": GROWTH_PLAN})

    assert response.status_code == 400
    [current] = get_json(client.get(entitlement_url(1)))
    assert (current["plan_code"], current["included_units"]) == ("STARTER", 100)


@pytest.mark.parametrize(
    ("number", "used", "quota", "rollover", "billable", "amount"),
    [
        pytest.param(1, 260, 100, 200, 0, "0.00", id="rollover-capped-at-twice-quota"),
        pytest.param(4, 50, 100, 0, 0, "0.00", id="below-quota"),
        pytest.param(2, 700, 500, 0, 100, "4.37", id="suspension-prorates-charge"),
    ],
)
def test_rating_respects_quota_rollover_and_suspension(
    client, number, used, quota, rollover, billable, amount
):
    [rating] = get_json(client.post("/api/rating/preview", json={"tenant_id": tenant(number), **PERIOD}))

    assert {key: rating[key] for key in ("tenant_id", *PERIOD)} == {"tenant_id": tenant(number), **PERIOD}
    assert (
        rating["used_units"], rating["quota_units"], rating["rollover_units"],
        rating["billable_units"], rating["overage_amount"],
    ) == (used, quota, rollover, billable, amount)


@pytest.mark.parametrize(
    ("number", "first", "second", "amount"),
    [
        pytest.param(6, 101, 0, "5.56", id="last-base-rate-unit"),
        pytest.param(8, 101, 1, "5.64", id="first-premium-rate-unit"),
    ],
)
def test_rating_includes_period_end_and_prices_tier_boundary(client, number, first, second, amount):
    [rating] = get_json(client.post("/api/rating/preview", json={"tenant_id": tenant(number), **PERIOD}))

    assert (rating["first_tier_units"], rating["second_tier_units"]) == (first, second)
    assert rating["billable_units"] == first + second
    assert rating["overage_amount"] == amount


def test_rating_finalize_retry_keeps_one_result_with_unused_quota(client, db):
    payload = {"tenant_id": tenant(4), **PERIOD}
    for _ in range(2):
        assert get_json(client.post("/api/rating/finalize", json=payload)) == {"status": "finalized"}

    assert db.execute(
        """
        SELECT r.used_units, r.quota_units, r.rollover_units, r.billable_units, r.overage_amount
        FROM billing.rating_results r
        JOIN billing.rating_periods p ON p.id = r.period_id
        WHERE p.tenant_id = %s AND p.period_start = %s AND p.period_end = %s
        """,
        (tenant(4), *PERIOD.values()),
    ).fetchall() == [(50, 100, 50, 0, Decimal("0.00"))]


def test_malformed_rating_request_is_rejected(client):
    response = client.post("/api/rating/preview", data="{", content_type="application/json")

    assert response.status_code == 400


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="Missing rating fields return HTTP 500 instead of 400")
def test_finalize_missing_period_end_is_a_client_error(client, db):
    response = client.post(
        "/api/rating/finalize", json={"tenant_id": tenant(4), "period_start": PERIOD["period_start"]}
    )

    if db.execute("SELECT 1 FROM billing.rating_periods WHERE tenant_id = %s", (tenant(4),)).fetchone():
        pytest.fail("Incomplete rating request created a billing period")
    assert response.status_code == 400


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="Suspended rating prorates billable units but not the tier breakdown")
def test_suspended_rating_tiers_add_up_to_billable_units(client):
    [rating] = get_json(client.post("/api/rating/preview", json={"tenant_id": tenant(2), **PERIOD}))

    assert rating["first_tier_units"] + rating["second_tier_units"] == rating["billable_units"]


def test_tax_exempt_invoice_preview_applies_credit_without_spending_it(client, db):
    lines = get_json(client.get(invoice_url(3, "preview"), query_string=PERIOD))

    assert [(line["line_type"], Decimal(line["total"])) for line in lines] == [
        ("plan", Decimal("499.00")),
        ("usage", Decimal("5.02")),
        ("tax", Decimal("0")),
        ("tax", Decimal("0")),
        ("credit", Decimal("-25.00")),
    ]
    assert invoice_record(db, 3) is None
    assert db.execute(
        "SELECT remaining_amount FROM billing.credit_notes WHERE tenant_id = %s", (tenant(3),)
    ).fetchall() == [(Decimal("25.00"),)]


def test_issued_invoice_preserves_line_order_and_spends_oldest_credit_first(client, db):
    assert get_json(client.post(invoice_url(9, "issue"), data=PERIOD)) == {"status": "issued"}

    invoice_id, subtotal, tax, total, status = invoice_record(db, 9)
    assert (subtotal, tax, total, status) == (Decimal("49.00"), Decimal("4.04"), Decimal("0.00"), "issued")
    lines = get_json(client.get(f"/api/invoices/{invoice_id}/lines"))
    assert [(line["line_no"], line["line_type"], line["amount"]) for line in lines] == [
        (1, "plan", "49.00"),
        (2, "usage", "0.00"),
        (3, "tax", "2.02"),
        (4, "tax", "2.02"),
        (5, "credit", "-53.04"),
    ]
    assert db.execute(
        "SELECT remaining_amount FROM billing.credit_notes WHERE tenant_id = %s ORDER BY issued_on",
        (tenant(9),),
    ).fetchall() == [(Decimal("0.00"),), (Decimal("6.96"),)]


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="Invoice retry recalculates an issued invoice from already-depleted credits")
def test_retrying_invoice_issue_does_not_change_amount_due(client, db):
    url = invoice_url(9, "issue")
    get_json(client.post(url, data=PERIOD))
    first = invoice_record(db, 9)
    get_json(client.post(url, data=PERIOD))
    second = invoice_record(db, 9)

    assert second == first


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="Preview sums unrounded tax but invoice issuance rounds each tax line")
def test_invoice_preview_matches_issued_total_at_rounding_boundary(client, db):
    preview = get_json(client.get(invoice_url(8, "preview"), query_string=PERIOD))
    quoted_total = round(sum(Decimal(line["total"]) for line in preview), 2)
    get_json(client.post(invoice_url(8, "issue"), data=PERIOD))
    _, _, _, issued_total, _ = invoice_record(db, 8)

    assert issued_total == quoted_total


def test_invoice_issue_missing_period_end_rejects_request_before_persisting(client, db):
    response = client.post(invoice_url(9, "issue"), data={"period_start": PERIOD["period_start"]})

    assert response.status_code == 400
    assert invoice_record(db, 9) is None


def test_overdue_accounts_filters_invoice_status_and_uses_as_of_date(client):
    overdue = get_json(client.get("/api/dunning/overdue", query_string={"as_of": "2026-02-13"}))
    assert [(row["tenant_id"], row["days_overdue"], row["total"]) for row in overdue] == [
        (tenant(2), 12, "161.29"),
    ]
    overdue = get_json(client.get("/api/dunning/overdue", query_string={"as_of": "2026-03-01"}))
    assert [(row["tenant_id"], row["days_overdue"]) for row in overdue] == [
        (tenant(2), 28),
        (tenant(5), 16),
    ]


@pytest.mark.parametrize("as_of", ["2026-02-28", "2026-03-01"], ids=["saturday", "sunday"])
def test_dunning_schedules_weekend_attempts_for_monday(client, db, as_of):
    assert get_json(client.post("/api/dunning/schedule", data={"as_of": as_of})) == {"status": "scheduled"}

    assert db.execute(
        "SELECT tenant_id::text, attempt_no, scheduled_for FROM billing.dunning_attempts"
        " WHERE status = 'scheduled' ORDER BY tenant_id"
    ).fetchall() == [(tenant(2), 1, date(2026, 3, 2)), (tenant(5), 2, date(2026, 3, 2))]


def test_dunning_suspends_at_fourteen_days_and_notifies_once(client, db):
    url = "/api/dunning/suspend"
    assert get_json(client.post(url, data={"as_of": "2026-02-26"})) == {"status": "suspended"}
    [before] = get_json(client.get(entitlement_url(5), query_string={"on": "2026-02-26"}))
    assert before["subscription_status"] == "active"

    for _ in range(2):
        assert get_json(client.post(url, data={"as_of": "2026-02-27"})) == {"status": "suspended"}
    [after] = get_json(client.get(entitlement_url(5), query_string={"on": "2026-02-27"}))
    assert after["subscription_status"] == "suspended"
    assert db.execute(
        "SELECT tenant_id::text, sent_at::date FROM billing.notifications WHERE kind = 'suspension'"
    ).fetchall() == [(tenant(5), date(2026, 2, 27))]


def test_health_checks_database_availability(client, monkeypatch):
    assert get_json(client.get("/health")) == {"status": "UP", "service": "legacy-billing"}

    monkeypatch.setenv("DB_NAME", "missing_test_database")
    response = client.get("/health")
    assert response.status_code >= 500
