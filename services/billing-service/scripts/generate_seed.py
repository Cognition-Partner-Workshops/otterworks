from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LEGACY = ROOT / "services" / "legacy-billing" / "db" / "seed.sql"
OUTPUT = ROOT / "services" / "billing-service" / "db" / "seed.sql"
DUNNING_OUTPUT = ROOT / "services" / "billing-service" / "db" / "seed_dunning.sql"
TABLES = ("tenants", "plans", "subscriptions")
DUNNING_TABLES = ("invoices", "dunning_attempts", "notifications")


def _generate(tables: tuple[str, ...]) -> str:
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
    return "\n".join(statements)


def generate() -> str:
    return _generate(TABLES)


def generate_dunning() -> str:
    return _generate(DUNNING_TABLES)


if __name__ == "__main__":
    OUTPUT.write_text(generate())
    DUNNING_OUTPUT.write_text(generate_dunning())
