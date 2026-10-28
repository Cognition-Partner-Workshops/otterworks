"""Compare complete Delta and Lakebase rows as multisets, then the Lakebase overdue features
against a replay of legacy pkg_dunning.fn_overdue_accounts over the exact stored snapshot
(bound by snapshot_id). A SELECT-only replay on live Oracle is reported separately as a
freshness check; it never fails verification, because Oracle may have moved on since capture."""

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


def snapshotOverdue(snapshot: dict[str, Any]) -> dict[str, tuple[int, int, Decimal]]:
    """fn_overdue_accounts body over the stored snapshot: status 40, issued before the as-of
    calendar day, age in calendar days since issue; aggregated per tenant."""
    asOf = date.fromisoformat(snapshot["as_of"])
    features: dict[str, tuple[int, int, Decimal]] = {}
    for invoice in snapshot["invoices"]:
        issued = datetime.fromisoformat(invoice["issued_at"]).date()
        if invoice["status_cd"] != 40 or issued >= asOf:
            continue
        count, oldest, total = features.get(invoice["tenant_id"], (0, 0, Decimal("0.00")))
        features[invoice["tenant_id"]] = (
            count + 1, max(oldest, (asOf - issued).days),
            (total + max(Decimal(str(invoice["total"])), Decimal(0))).quantize(Decimal("0.01")))
    return features


def legacyOverdue(asOf: date) -> dict[str, tuple[int, int, Decimal]]:
    """Same predicate on live Oracle (SELECT-only, read-only transaction, no package execution).
    Freshness evidence only: live rows may legitimately differ from the captured snapshot."""
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


def overdueMismatches(synced: dict[str, tuple[int, int, Decimal]],
                      expected: dict[str, tuple[int, int, Decimal]]) -> list[str]:
    zero = (0, 0, Decimal("0.00"))
    return sorted({tenant for tenant in synced if synced[tenant] != expected.get(tenant, zero)}
                  | {tenant for tenant in expected if tenant not in synced})


def compareOverdue(lakebaseRows: list[dict[str, Any]], snapshot: dict[str, Any]) -> None:
    snapshotId = {str(row["snapshot_id"]) for row in lakebaseRows}
    if snapshotId != {snapshot["snapshot_id"]}:
        raise ValueError(f"Lakebase rows carry snapshot_id {sorted(snapshotId)}, not the stored snapshot {snapshot['snapshot_id']}")
    mismatches = overdueMismatches(overdueFeatures(lakebaseRows), snapshotOverdue(snapshot))
    if mismatches:
        raise ValueError(f"overdue features differ from fn_overdue_accounts over the stored snapshot for {mismatches}")


def loadSnapshot(path: Path) -> dict[str, Any]:
    """The staged snapshot file; its SHA-256 is the snapshot_id prepare.py stored in Delta."""
    payload = path.read_text()
    snapshot = json.loads(payload, parse_float=Decimal)
    snapshot["snapshot_id"] = hashlib.sha256(payload.encode()).hexdigest()
    return snapshot


def main() -> None:
    exported = json.loads(Path(sys.argv[1]).read_text())
    snapshot = loadSnapshot(Path(sys.argv[2]))
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
    if {str(row["as_of"]) for row in lakebaseRows} != {snapshot["as_of"]}:
        raise ValueError("Lakebase as_of dates do not match the stored snapshot")
    compareOverdue(lakebaseRows, snapshot)
    legacy = legacyOverdue(date.fromisoformat(snapshot["as_of"]))
    drift = overdueMismatches(overdueFeatures(lakebaseRows), legacy)
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
        "snapshot_id": snapshot["snapshot_id"], "as_of": snapshot["as_of"],
        "overdue_semantics": "MATCH fn_overdue_accounts replayed over the stored snapshot "
                             "(status 40, issued before as-of day, calendar-day age)",
        "legacy_freshness": "MATCH live Oracle" if not drift else f"DRIFT since capture for tenants {drift}",
        "legacy_overdue_tenants": {tenant: list(map(str, feature)) for tenant, feature in sorted(legacy.items())},
        "tenant_one": fixtureRows, "history_examples": examples,
    }, default=str, indent=2))


if __name__ == "__main__":
    main()
