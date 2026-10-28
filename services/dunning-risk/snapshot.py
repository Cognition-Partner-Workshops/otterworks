"""Read one consistent, read-only snapshot of legacy OW_BILLING state from Oracle."""

import json
import os
import re
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import oracledb

from prepare import SOURCE, validateSnapshot

_DSN_RE = re.compile(
    r"^(?:oracle://)?(?P<user>[^:/@\s]+)[:/](?P<password>[^@\s]*)@(?P<host>[^:/@\s]+)"
    r":(?P<port>\d+)/(?P<service>[^\s/]+)\s*$")


def oracleConnect(secretName: str = "OW_BILLING_RO_DSN") -> oracledb.Connection:
    """Connect with the read-only principal named by the secret; the value is never printed."""
    raw = os.environ.get(secretName)
    if not raw:
        raise SystemExit(f"secret {secretName} is not set in the environment")
    if raw.lstrip().startswith("{"):
        obj = json.loads(raw)
        dsn = obj.get("dsn") or f"{obj['host']}:{obj['port']}/{obj.get('service') or obj['service_name']}"
        return oracledb.connect(user=obj["user"], password=obj["password"], dsn=dsn)
    match = _DSN_RE.match(raw)
    if not match:
        raise SystemExit(f"secret {secretName} is not a user/pass@host:port/service DSN")
    return oracledb.connect(user=match["user"], password=match["password"],
                            dsn=f"{match['host']}:{match['port']}/{match['service']}")


def jsonValue(value: Any) -> Any:
    if isinstance(value, Decimal):
        rendered = float(value)
        if Decimal(repr(rendered)) != value:
            raise ValueError(f"amount {value} is not exactly representable")
        return rendered
    if isinstance(value, datetime):
        return value.isoformat(sep="T", timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return value


def rows(cursor: oracledb.Cursor, columns: tuple[str, ...]) -> list[dict[str, Any]]:
    return [dict(zip(columns, map(jsonValue, row))) for row in cursor.fetchall()]


def main() -> None:
    outputPath = Path(sys.argv[1])
    with oracleConnect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SELECT SYS_EXTRACT_UTC(SYSTIMESTAMP) FROM dual")
            capturedAt = cursor.fetchone()[0]
            cursor.execute("SELECT id, name, status_cd FROM ow_billing.tenants ORDER BY id")
            tenants = rows(cursor, ("id", "name", "status_cd"))
            cursor.execute("SELECT id, tenant_id, status_cd, starts_on, ends_on "
                           "FROM ow_billing.subscriptions ORDER BY id")
            subscriptions = rows(cursor, ("id", "tenant_id", "status_cd", "starts_on", "ends_on"))
            cursor.execute("SELECT id, tenant_id, issued_at, total, status_cd "
                           "FROM ow_billing.invoices ORDER BY id")
            invoices = rows(cursor, ("id", "tenant_id", "issued_at", "total", "status_cd"))
            cursor.execute("SELECT id, tenant_id, invoice_id, attempt_no, scheduled_for, status_cd "
                           "FROM ow_billing.dunning_attempts ORDER BY id")
            attempts = rows(cursor, ("id", "tenant_id", "invoice_id", "attempt_no", "scheduled_for", "status_cd"))
            cursor.execute("SELECT id, tenant_id, issued_on, amount, remaining_amount "
                           "FROM ow_billing.credit_notes ORDER BY id")
            credits = rows(cursor, ("id", "tenant_id", "issued_on", "amount", "remaining_amount"))
        connection.rollback()
    for row in subscriptions:
        row["starts_on"] = row["starts_on"][:10]
        row["ends_on"] = row["ends_on"][:10] if row["ends_on"] else None
    for row in attempts:
        row["scheduled_for"] = row["scheduled_for"][:10]
    for row in credits:
        row["issued_on"] = row["issued_on"][:10]
    snapshot = {
        "captured_at": capturedAt.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "as_of": capturedAt.date().isoformat(),
        "source": SOURCE,
        "tenants": tenants, "subscriptions": subscriptions, "invoices": invoices,
        "dunning_attempts": attempts, "credit_notes": credits,
    }
    validateSnapshot(snapshot)
    if not any(t["name"] == "Tenant One" for t in snapshot["tenants"]):
        raise ValueError("Expected billing fixture (including Tenant One) is missing")
    payload = json.dumps(snapshot, separators=(",", ":"))
    outputPath.write_text(payload + "\n")
    print(json.dumps({"captured_at": snapshot["captured_at"], "as_of": snapshot["as_of"], "rows": {
        name: len(snapshot[name]) for name in (
            "tenants", "subscriptions", "invoices", "dunning_attempts", "credit_notes"
        )
    }}))


if __name__ == "__main__":
    main()
