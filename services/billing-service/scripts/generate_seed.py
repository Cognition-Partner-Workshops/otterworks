from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LEGACY = ROOT / "services" / "legacy-billing" / "db" / "seed.sql"
OUTPUT = ROOT / "services" / "billing-service" / "db" / "seed.sql"
TABLES = ("tenants", "plans", "subscriptions")

INVOICING_OUTPUT = ROOT / "services" / "billing-service" / "db" / "seed_invoicing.sql"
INVOICING_TABLES = (
    "usage_events",
    "rating_periods",
    "rating_results",
    "invoices",
    "credit_notes",
    "invoice_lines",
)


def _legacy_statements(tables: tuple[str, ...]) -> list[str]:
    source = LEGACY.read_text()
    statements = []
    for table in tables:
        match = re.search(
            rf"INSERT INTO billing\.{table} .*?;\n",
            source,
            flags=re.DOTALL,
        )
        if match is None:
            raise RuntimeError(f"missing legacy seed section: {table}")
        statements.append(match.group(0).replace(f"billing.{table}", f"billing_svc.{table}"))
    return statements


def generate() -> str:
    return "\n".join(_legacy_statements(TABLES))


def generate_invoicing() -> str:
    return "\n".join(
        statement.removesuffix(";\n") + "\nON CONFLICT DO NOTHING;\n"
        for statement in _legacy_statements(INVOICING_TABLES)
    )


if __name__ == "__main__":
    OUTPUT.write_text(generate())
    INVOICING_OUTPUT.write_text(generate_invoicing())
