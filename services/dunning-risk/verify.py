"""Compare complete Delta and Lakebase rows as multisets, then the Lakebase overdue features
against a SELECT-only replay of legacy pkg_dunning.fn_overdue_accounts on Oracle."""

import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg

from snapshot import oracleConnect


def cliJson(*args: str) -> Any:
    result = subprocess.run(
        ["databricks", *args, "--output", "json"],
        check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout)


def canonical(value: Any) -> str:
    if value is None:
        return "null:"
    if isinstance(value, bool):
        return "bool:" + str(value).lower()
    return "value:" + str(value)


def rowKey(row: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((name, canonical(value)) for name, value in row.items()))


def compare(deltaRows: list[dict[str, Any]], lakebaseRows: list[dict[str, Any]]) -> None:
    if not deltaRows:
        raise ValueError("Empty Delta result is not live proof")
    deltaCounts = Counter(map(rowKey, deltaRows))
    lakebaseCounts = Counter(map(rowKey, lakebaseRows))
    if deltaCounts != lakebaseCounts:
        raise ValueError(f"Row mismatch: {sum((deltaCounts - lakebaseCounts).values())} missing, "
                         f"{sum((lakebaseCounts - deltaCounts).values())} extra")


def tableHash(rows: list[dict[str, Any]]) -> str:
    return hashlib.sha256(json.dumps(sorted(map(rowKey, rows))).encode()).hexdigest()


def historyExamples(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    examples: dict[str, dict[str, Any]] = {}
    for feature in ("overdue_invoices", "paid_invoices", "credit_note_count"):
        candidates = sorted(rows, key=lambda row: (-row["risk_score"], row["tenant_id"], row["subscription_id"]))
        for row in candidates:
            if row[feature] > 0 and row["tenant_id"] not in examples:
                examples[row["tenant_id"]] = row
                break
    return list(examples.values())


def overdueFeatures(rows: list[dict[str, Any]]) -> dict[str, tuple[int, int, Decimal]]:
    """Tenant-level overdue features; rows repeat per subscription, so they must agree per tenant."""
    features: dict[str, tuple[int, int, Decimal]] = {}
    for row in rows:
        feature = (int(row["overdue_invoices"]), int(row["oldest_overdue_days"]), Decimal(str(row["overdue_total"])))
        if features.setdefault(row["tenant_id"], feature) != feature:
            raise ValueError(f"tenant {row['tenant_id']} carries conflicting overdue features across subscriptions")
    return features


def legacyOverdue(asOf: date) -> dict[str, tuple[int, int, Decimal]]:
    """fn_overdue_accounts body (status 40, issued before the as-of calendar day, calendar-day age)
    aggregated per tenant; SELECT-only under the read-only principal, no package execution."""
    with oracleConnect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("""
                SELECT i.tenant_id, COUNT(*),
                       MAX(TRUNC(:as_of) - TRUNC(CAST(i.issued_at AS DATE))),
                       SUM(GREATEST(i.total, 0))
                  FROM ow_billing.invoices i
                 WHERE i.status_cd = 40
                   AND TO_CHAR(i.issued_at, 'YYYYMMDD') < TO_CHAR(:as_of, 'YYYYMMDD')
                 GROUP BY i.tenant_id""", as_of=datetime(asOf.year, asOf.month, asOf.day))
            legacy = {row[0]: (int(row[1]), int(row[2]), Decimal(str(row[3])).quantize(Decimal("0.01")))
                      for row in cursor.fetchall()}
        connection.rollback()
    return legacy


def compareOverdue(lakebaseRows: list[dict[str, Any]], legacy: dict[str, tuple[int, int, Decimal]]) -> None:
    synced = overdueFeatures(lakebaseRows)
    zero = (0, 0, Decimal("0.00"))
    mismatches = {tenant: (synced[tenant], legacy.get(tenant, zero))
                  for tenant in synced if synced[tenant] != legacy.get(tenant, zero)}
    mismatches.update({tenant: (zero, legacy[tenant]) for tenant in legacy if tenant not in synced})
    if mismatches:
        raise ValueError(f"overdue features differ from fn_overdue_accounts for {sorted(mismatches)}")


def main() -> None:
    exported = json.loads(Path(sys.argv[1]).read_text())
    deltaRows = [json.loads(row["row_json"], parse_float=Decimal) for row in exported]
    endpointPath = "projects/ow-tp-billing/branches/mig-dunning-risk/endpoints/primary"
    identity = cliJson("current-user", "me")["userName"]
    endpoint = cliJson("postgres", "get-endpoint", endpointPath)
    credential = cliJson("postgres", "generate-database-credential", endpointPath)
    with psycopg.connect(
        host=endpoint["status"]["hosts"]["host"], dbname="databricks_postgres", user=identity,
        password=credential["token"], sslmode="require", connect_timeout=30, autocommit=True,
        options="-c default_transaction_read_only=on",
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT row_to_json(s)::text FROM ow_tp_dunning_risk.ow_tp_scores_synced s")
            lakebaseRows = [json.loads(row[0], parse_float=Decimal) for row in cursor.fetchall()]
    compare(deltaRows, lakebaseRows)
    asOf = {date.fromisoformat(str(row["as_of"])) for row in lakebaseRows}
    if len(asOf) != 1:
        raise ValueError(f"Lakebase rows carry {len(asOf)} distinct as_of dates")
    legacy = legacyOverdue(asOf.pop())
    compareOverdue(lakebaseRows, legacy)
    fixtureRows = [row for row in lakebaseRows if row["tenant_name"] == "Tenant One"]
    if not fixtureRows:
        raise ValueError("Tenant One is missing")
    examples = historyExamples(lakebaseRows)
    if len(examples) < 2:
        raise ValueError("Fewer than two distinct history-bearing tenants")
    print(json.dumps({
        "delta_table": "ow_tp.ow_tp_dunning_risk.ow_tp_scores",
        "lakebase_branch": "projects/ow-tp-billing/branches/mig-dunning-risk",
        "lakebase_database": "databricks_postgres",
        "lakebase_table": "ow_tp_dunning_risk.ow_tp_scores_synced",
        "matched_rows": len(deltaRows), "missing_rows": 0, "extra_rows": 0,
        "delta_sha256": tableHash(deltaRows), "lakebase_sha256": tableHash(lakebaseRows),
        "legacy_overdue_tenants": {tenant: list(map(str, feature)) for tenant, feature in sorted(legacy.items())},
        "overdue_semantics": "MATCH fn_overdue_accounts (status 40, issued before as-of day, calendar-day age)",
        "tenant_one": fixtureRows, "history_examples": examples,
    }, default=str, indent=2))


if __name__ == "__main__":
    main()
