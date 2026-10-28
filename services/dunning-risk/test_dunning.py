"""Local safety tests and generation of read-only warehouse tests of the actual SQL."""

import copy
import json
import sys
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from prepare import snapshotSql, validateSnapshot
from verify import compare, historyExamples, tableHash


def fixture() -> dict[str, Any]:
    return {
        "captured_at": "2026-03-20T12:00:00.000000Z", "as_of": "2026-03-20",
        "source": "ow-tp-billing/mig-invoicing-w1/ow_tp_invoicing",
        "tenants": [{"id": "t", "name": "Tenant One", "status_cd": 10}],
        "subscriptions": [], "invoices": [], "dunning_attempts": [], "credit_notes": [],
    }


class SafetyTests(unittest.TestCase):
    def testStableSnapshotIdAndEscaping(self) -> None:
        snapshot = fixture()
        snapshot["tenants"][0]["name"] = "Tenant's quote; DROP TABLE never"
        rendered = snapshotSql(json.dumps(snapshot))
        self.assertEqual(rendered, snapshotSql(json.dumps(snapshot)))
        self.assertNotIn("DROP TABLE", rendered)
        self.assertIn("ow_tp.ow_tp_dunning_risk.ow_tp_snapshots", rendered)

    def testEmptyAndWrongSourceRejected(self) -> None:
        snapshot = fixture()
        snapshot["source"] = "production"
        with self.assertRaises(ValueError):
            validateSnapshot(snapshot)
        snapshot = fixture()
        snapshot["tenants"] = []
        with self.assertRaises(ValueError):
            validateSnapshot(snapshot)

    def testMissingAttributionAndNullMoneyRejected(self) -> None:
        snapshot = fixture()
        invoice = {"id": "i", "tenant_id": "other", "issued_at": "2026-03-01", "total": 100, "status_cd": 40}
        snapshot["invoices"] = [invoice]
        with self.assertRaises(ValueError):
            validateSnapshot(snapshot)
        invoice["tenant_id"] = "t"
        invoice["total"] = None
        with self.assertRaises(ValueError):
            validateSnapshot(snapshot)

    def testDuplicateIdsRejected(self) -> None:
        snapshot = fixture()
        snapshot["tenants"] *= 2
        with self.assertRaises(ValueError):
            validateSnapshot(snapshot)

    def testCrossTenantAttemptsRejected(self) -> None:
        snapshot = fixture()
        snapshot["dunning_attempts"] = [{
            "id": "d", "tenant_id": "t", "invoice_id": "missing", "attempt_no": 1,
            "scheduled_for": "2026-03-01", "status_cd": 20,
        }]
        with self.assertRaises(ValueError):
            validateSnapshot(snapshot)

    def testCompareIsOrderIndependentAndChecksEveryField(self) -> None:
        rows = [{"id": "a", "risk": 1, "money": Decimal("1.00"), "suspended": False}, {"id": "b", "risk": 2}]
        compare(rows, list(reversed(rows)))
        changed = copy.deepcopy(rows)
        changed[0]["risk"] = 99
        with self.assertRaises(ValueError):
            compare(rows, changed)

    def testCompareRejectsDuplicatesEmptyAndNullDifferences(self) -> None:
        with self.assertRaises(ValueError):
            compare([], [])
        with self.assertRaises(ValueError):
            compare([{"id": "a"}], [{"id": "a"}, {"id": "a"}])
        with self.assertRaises(ValueError):
            compare([{"id": None}], [{"id": "null"}])

    def testTableHashIgnoresRowOrderButRetainsDuplicates(self) -> None:
        rows = [{"id": "a"}, {"id": "b"}]
        self.assertEqual(tableHash(rows), tableHash(list(reversed(rows))))
        self.assertNotEqual(tableHash(rows), tableHash([*rows, rows[0]]))

    def testHistoryExamplesAreDistinctAndCoverFeatures(self) -> None:
        rows = [
            {"tenant_id": name, "subscription_id": "s", "risk_score": score,
             "paid_invoices": paid, "overdue_invoices": overdue, "credit_note_count": credits}
            for name, score, paid, overdue, credits in (("d", 85, 0, 1, 0), ("p", 0, 1, 0, 0), ("c", 0, 0, 0, 1))
        ]
        self.assertEqual([row["tenant_id"] for row in historyExamples(rows * 2)], ["d", "p", "c"])

    def testHistoryExamplesAllowTwoCategories(self) -> None:
        rows = [
            {"tenant_id": name, "subscription_id": "s", "risk_score": score,
             "paid_invoices": paid, "overdue_invoices": overdue, "credit_note_count": 0}
            for name, score, paid, overdue in (("d", 85, 0, 1), ("p", 0, 1, 0))
        ]
        self.assertEqual([row["tenant_id"] for row in historyExamples(rows)], ["d", "p"])


def warehouseTests() -> str:
    snapshot = fixture()
    for name in ("tenants", "subscriptions", "invoices", "dunning_attempts", "credit_notes"):
        snapshot[name] = []
    expectedRows: list[tuple[Any, ...]] = []

    def case(name: str, age: int | None, expected: tuple[Any, ...], *, paid: bool = False,
             sent: int = 0, ignored: bool = False, credit: int | None = None,
             futureCredit: bool = False, tenantStatus: int = 10, invoiceStatus: int = 40,
             total: int = 100, subscriptions: int = 1, futureStart: bool = False) -> None:
        snapshot["tenants"].append({"id": name, "name": name, "status_cd": tenantStatus})
        for index in range(subscriptions):
            snapshot["subscriptions"].append({
                "id": f"{name}-{index}", "tenant_id": name, "status_cd": 10,
                "starts_on": "2027-01-01" if futureStart else "2026-01-01", "ends_on": None,
            })
        if age is not None:
            snapshot["invoices"].append({
                "id": name + "-invoice", "tenant_id": name, "status_cd": invoiceStatus,
                "issued_at": str(date(2026, 3, 20) - timedelta(days=age)), "total": total,
            })
        if paid:
            snapshot["invoices"].append({
                "id": name + "-paid", "tenant_id": name, "status_cd": 30,
                "issued_at": "2026-02-01", "total": 100,
            })
        for index in range(sent):
            snapshot["dunning_attempts"].append({
                "id": f"{name}-attempt-{index}", "tenant_id": name, "invoice_id": name + "-invoice",
                "attempt_no": index + 1, "scheduled_for": "2026-03-10", "status_cd": 20,
            })
        if ignored:
            for index, (status, scheduled) in enumerate(((10, "2026-03-01"), (30, "2026-03-01"), (20, "2027-01-01"))):
                snapshot["dunning_attempts"].append({
                    "id": f"{name}-ignored-{index}", "tenant_id": name,
                    "invoice_id": name + "-invoice", "attempt_no": index + 1,
                    "scheduled_for": scheduled, "status_cd": status,
                })
        if credit is not None:
            snapshot["credit_notes"].append({
                "id": name + "-credit", "tenant_id": name, "amount": max(credit, 0),
                "remaining_amount": credit, "issued_on": "2027-01-01" if futureCredit else "2026-03-01",
            })
        outputIds = [f"{name}-{i}" for i in range(subscriptions)] if subscriptions and not futureStart else ["NO_SUBSCRIPTION"]
        expectedRows.extend((name, subId, *expected) for subId in outputIds)

    # score, band, age/payment/dunning/exposure points, paid/overdue counts, oldest days,
    # sent count, credit count, suspension eligibility.
    empty = (0, "insufficient_history", 0, 0, 0, 0, 0, 0, 0, 0, 0, False)
    overdue14 = (80, "high", 40, 25, 0, 15, 0, 1, 14, 0, 0, True)
    case("empty", None, empty)
    case("issued_today", 0, empty)
    case("future_invoice", -1, empty)
    case("issued_not_overdue", 30, empty, invoiceStatus=20)
    for age in (1, 6, 7, 13, 14):
        agePoints = 40 if age == 14 else 25 if age >= 7 else 10
        score = agePoints + 40
        case(f"age_{age}", age, (score, "high" if score >= 70 else "medium", agePoints, 25, 0, 15, 0, 1, age, 0, 0, age >= 14))
    case("suspended", 14, (*overdue14[:-1], False), tenantStatus=20)
    case("paid_history", 14, (68, "medium", 40, 13, 0, 15, 1, 1, 14, 0, 0, True), paid=True)
    case("dunning_cap", 14, (100, "high", 40, 25, 20, 15, 0, 1, 14, 6, 0, True), sent=6)
    case("ignored_attempts", 14, overdue14, ignored=True)
    case("full_credit", 14, (65, "medium", 40, 25, 0, 0, 0, 1, 14, 0, 1, True), credit=100)
    case("partial_credit", 14, (73, "high", 40, 25, 0, 8, 0, 1, 14, 0, 1, True), credit=50)
    case("excess_credit", 14, (65, "medium", 40, 25, 0, 0, 0, 1, 14, 0, 1, True), credit=200)
    case("negative_credit", 14, (80, "high", 40, 25, 0, 15, 0, 1, 14, 0, 1, True), credit=-50)
    case("negative_total", 14, (65, "medium", 40, 25, 0, 0, 0, 1, 14, 0, 0, True), total=-100)
    case("future_credit", 14, overdue14, credit=100, futureCredit=True)
    case("two_subscriptions", 14, overdue14, subscriptions=2)
    case("no_subscriptions", 14, overdue14, subscriptions=0)
    case("future_subscription", 14, overdue14, futureStart=True)
    case("paid_only", 15, (0, "low", 0, 0, 0, 0, 1, 0, 0, 0, 0, False), invoiceStatus=30)
    validateSnapshot(snapshot)
    payloadHex = json.dumps(snapshot).encode().hex()
    scoreSql = Path(__file__).with_name("score.sql").read_text()
    selectSql = "WITH snapshots AS (" + scoreSql.split("WITH snapshots AS (", 1)[1].rsplit(";", 2)[0]
    sourceSql = f"(SELECT 'test' AS snapshot_id, decode(unhex('{payloadHex}'), 'UTF-8') AS payload)"
    selectSql = selectSql.replace("ow_tp.ow_tp_dunning_risk.ow_tp_snapshots", sourceSql)
    columns = ("tenant_id, subscription_id, risk_score, risk_band, age_points, payment_points, "
               "dunning_points, exposure_points, paid_invoices, overdue_invoices, oldest_overdue_days, "
               "past_sent_attempts, credit_note_count, suspension_eligible")

    def literal(value: Any) -> str:
        if isinstance(value, str):
            return "'" + value.replace("'", "''") + "'"
        return str(value).lower()

    valuesSql = ",\n".join("(" + ", ".join(map(literal, row)) + ")" for row in expectedRows)
    return f"""WITH actual AS ({selectSql}), expected ({columns}) AS (VALUES {valuesSql}),
differences AS (
    (SELECT {columns} FROM actual EXCEPT ALL SELECT * FROM expected)
    UNION ALL
    (SELECT * FROM expected EXCEPT ALL SELECT {columns} FROM actual)
)
SELECT assert_true(count(*) = 0, 'Dunning scoring regression') AS all_cases_passed,
       {len(expectedRows)} AS tested_rows FROM differences;
"""


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--warehouse-sql":
        Path(sys.argv[2]).write_text(warehouseTests())
    else:
        unittest.main()
