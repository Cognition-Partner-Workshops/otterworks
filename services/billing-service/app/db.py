from __future__ import annotations

from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app.config import settings

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = sorted((ROOT / "db" / "migrations").glob("*.sql"))
SEED = ROOT / "db" / "seed.sql"
INVOICING_SEED = ROOT / "db" / "seed_invoicing.sql"


def connect() -> psycopg.Connection:
    return psycopg.connect(settings.database_url, row_factory=dict_row)


def _apply_migrations(connection: psycopg.Connection) -> None:
    for migration in MIGRATIONS:
        connection.execute(migration.read_text())


def migrate() -> None:
    with connect() as connection:
        _apply_migrations(connection)


def reset() -> None:
    with connect() as connection:
        _apply_migrations(connection)
        connection.execute(
            """
            TRUNCATE TABLE billing_svc.subscriptions,
                           billing_svc.plans,
                           billing_svc.tenants
            CASCADE
            """
        )
        connection.execute(SEED.read_text())
        connection.execute(INVOICING_SEED.read_text())
