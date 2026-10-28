"""Read one consistent snapshot of migrated billing state; never modify the source."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import psycopg

from prepare import validateSnapshot


def cliJson(*args: str) -> Any:
    result = subprocess.run(
        ["databricks", *args, "--output", "json"],
        check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout)


def main() -> None:
    outputPath = Path(sys.argv[1])
    endpointPath = "projects/ow-tp-billing/branches/mig-invoicing-w1/endpoints/primary"
    identity = cliJson("current-user", "me")["userName"]
    endpoint = cliJson("postgres", "get-endpoint", endpointPath)
    credential = cliJson("postgres", "generate-database-credential", endpointPath)
    with psycopg.connect(
        host=endpoint["status"]["hosts"]["host"], dbname="ow_tp", user=identity,
        password=credential["token"], sslmode="require", connect_timeout=30,
        autocommit=True, options="-c default_transaction_read_only=on",
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT json_build_object(
                    'captured_at', to_char(current_timestamp AT TIME ZONE 'UTC',
                                          'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
                    'as_of', (current_timestamp AT TIME ZONE 'UTC')::date,
                    'source', 'ow-tp-billing/mig-invoicing-w1/ow_tp_invoicing',
                    'tenants', (SELECT coalesce(json_agg(t ORDER BY t.id), '[]')
                        FROM (SELECT id, name, status_cd FROM ow_tp_invoicing.tenants) t),
                    'subscriptions', (SELECT coalesce(json_agg(s ORDER BY s.id), '[]')
                        FROM (SELECT id, tenant_id, status_cd,
                                     starts_on::date AS starts_on, ends_on::date AS ends_on
                              FROM ow_tp_invoicing.subscriptions) s),
                    'invoices', (SELECT coalesce(json_agg(i ORDER BY i.id), '[]')
                        FROM (SELECT id, tenant_id, issued_at, total, status_cd
                              FROM ow_tp_invoicing.invoices) i),
                    'dunning_attempts', (SELECT coalesce(json_agg(d ORDER BY d.id), '[]')
                        FROM (SELECT id, tenant_id, invoice_id, attempt_no,
                                     scheduled_for::date AS scheduled_for, status_cd
                              FROM ow_tp_invoicing.dunning_attempts) d),
                    'credit_notes', (SELECT coalesce(json_agg(c ORDER BY c.id), '[]')
                        FROM (SELECT id, tenant_id, issued_on::date AS issued_on,
                                     amount, remaining_amount
                              FROM ow_tp_invoicing.credit_notes) c)
                )::text
            """)
            row = cursor.fetchone()
    if row is None:
        raise RuntimeError("No source snapshot returned")
    payload = row[0]
    snapshot = json.loads(payload)
    validateSnapshot(snapshot)
    if not snapshot["tenants"] or not any(t["name"] == "Tenant One" for t in snapshot["tenants"]):
        raise ValueError("Expected billing fixture (including Tenant One) is missing")
    outputPath.write_text(payload + "\n")
    print(json.dumps({"captured_at": snapshot["captured_at"], "rows": {
        name: len(snapshot[name]) for name in (
            "tenants", "subscriptions", "invoices", "dunning_attempts", "credit_notes"
        )
    }}))


if __name__ == "__main__":
    main()
