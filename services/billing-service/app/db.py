from __future__ import annotations

from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app.config import settings

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = sorted((ROOT / "db" / "migrations").glob("*.sql"))
SEED = ROOT / "db" / "seed.sql"
DUNNING_SEED = ROOT / "db" / "seed_dunning.sql"


def connect() -> psycopg.Connection:
    return psycopg.connect(settings.database_url, row_factory=dict_row)


def migrate() -> None:
    with connect() as connection:
        for migration in MIGRATIONS:
            connection.execute(migration.read_text())


def reset() -> None:
    with connect() as connection:
        for migration in MIGRATIONS:
            connection.execute(migration.read_text())
        connection.execute(
            """
            TRUNCATE TABLE billing_svc.subscriptions,
                           billing_svc.plans,
                           billing_svc.tenants,
                           billing_svc.notifications,
                           billing_svc.dunning_attempts,
                           billing_svc.invoices
            """
        )
        connection.execute(SEED.read_text())
        connection.execute(DUNNING_SEED.read_text())
