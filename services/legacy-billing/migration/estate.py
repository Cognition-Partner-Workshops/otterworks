"""Shared definitions for the OW_BILLING Oracle -> PostgreSQL takeout.

Used by migrate.py (the copy) and recon.py (the proof). Both sides are read
with the same column lists and the same value canonicalization, so a check
that compares Oracle with Postgres compares like with like.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal

import oracledb
import psycopg

oracledb.defaults.fetch_decimals = True

ORPHAN_TABLE = "invoice_line_orphan"
BASELINE_TABLE = "migration_baseline"
ORPHAN_REASON = "no INVOICE_HEADER row for invoice_id (Oracle had no FK); held for Finance review"
NULL_INVOICE_REASON = "invoice_id is NULL (Oracle had no FK); held for Finance review"


@dataclass(frozen=True)
class Table:
    name: str                 # same name in Oracle and Postgres
    key: tuple[str, ...]      # primary key (fixture_meta: natural key)
    split: bool = False       # invoice_line: rows without a header go to ORPHAN_TABLE


# Load order respects the Postgres foreign keys.
TABLES: tuple[Table, ...] = (
    Table("codes", ("code_type", "code_val")),
    Table("tenants", ("id",)),
    Table("plans", ("id",)),
    Table("subscriptions", ("id",)),
    Table("usage_events", ("id",)),
    Table("rating_periods", ("id",)),
    Table("rating_results", ("id",)),
    Table("invoices", ("id",)),
    Table("invoice_lines", ("id",)),
    Table("credit_notes", ("id",)),
    Table("dunning_attempts", ("id",)),
    Table("notifications", ("id",)),
    Table("billing_audit_log", ("log_id",)),
    Table("subscriptions_hist", ("hist_id",)),
    Table("fixture_meta", ("marker",)),
    Table("customer_master", ("cust_id",)),
    Table("customer_master_hist", ("hist_id",)),
    Table("entity_attr_value", ("eav_id",)),
    Table("invoice_header", ("invoice_id",)),
    Table("invoice_line", ("line_id",), split=True),
)

SEQUENCES = (
    "seq_billing_audit_log",
    "seq_subscriptions_hist",
    "seq_customer_master",
    "seq_customer_master_hist",
    "seq_entity_attr_value",
)

# References Oracle never enforced. Coverage is reported for each, on both
# sides; only invoice_line -> invoice_header became a real FK.
# (child_table, child_column, parent_table, parent_column, child_filter)
LOGICAL_REFS = (
    ("invoice_line", "invoice_id", "invoice_header", "invoice_id", None),
    ("invoice_line", "cust_id", "customer_master", "cust_id", None),
    ("invoice_header", "cust_id", "customer_master", "cust_id", None),
    ("entity_attr_value", "entity_id", "customer_master", "cust_id",
     "entity_type = 'CUSTOMER'"),
)


def oracle_connect():
    return oracledb.connect(
        user=os.getenv("ORACLE_USER", "ow_billing"),
        password=os.getenv("ORACLE_PASSWORD", "ow_billing"),
        host=os.getenv("ORACLE_HOST", "localhost"),
        port=int(os.getenv("ORACLE_PORT", "52521")),
        service_name=os.getenv("ORACLE_SERVICE", "FREEPDB1"),
    )


def pg_connect():
    return psycopg.connect(
        host=os.getenv("BILLING_PG_HOST", "localhost"),
        port=int(os.getenv("BILLING_PG_PORT", "55433")),
        dbname=os.getenv("BILLING_PG_DB", "ow_tp_billing"),
        user=os.getenv("BILLING_PG_USER", "ow_billing"),
        password=os.getenv("BILLING_PG_PASSWORD", "ow_billing"),
    )


@dataclass(frozen=True)
class Column:
    name: str
    data_type: str            # Postgres data_type
    scale: int | None


def pg_columns(pg, table: str) -> list[Column]:
    rows = pg.execute(
        """SELECT column_name, data_type, numeric_scale
             FROM information_schema.columns
            WHERE table_schema = 'ow_billing' AND table_name = %s
            ORDER BY ordinal_position""",
        (table,),
    ).fetchall()
    return [Column(*row) for row in rows if row[0] != "quarantine_reason"]


def oracle_columns(ora, table: str) -> list[str]:
    with ora.cursor() as cur:
        cur.execute(
            "SELECT LOWER(column_name) FROM user_tab_columns"
            " WHERE table_name = UPPER(:1) ORDER BY column_id",
            (table,),
        )
        return [row[0] for row in cur]


def sum_columns(columns: list[Column]) -> list[str]:
    """Columns whose totals are reconciled: every fractional numeric
    (money at scale 2, plus qty, unit_price and overage_rate)."""
    return [c.name for c in columns if c.data_type == "numeric" and (c.scale or 0) > 0]


def canon(value) -> str:
    """One text form per value, identical for Oracle and Postgres drivers."""
    if value is None:
        return "\\N"
    if isinstance(value, bool):
        return "t" if value else "f"
    if isinstance(value, Decimal):
        return canon_decimal(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, datetime):
        if value.time() == time.min:
            return value.date().isoformat()
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def canon_decimal(value: Decimal) -> str:
    if value == value.to_integral_value():
        return str(int(value))
    return format(value.normalize(), "f")


class SetChecksum:
    """Order-independent checksum: sum of per-row md5 digests mod 2**128
    (same construction as testdata/legacy/legacy_common.Checksum)."""

    _MOD = 1 << 128

    def __init__(self) -> None:
        self.total = 0
        self.count = 0

    def add_row(self, row) -> None:
        line = "\x1f".join(canon(v) for v in row)
        self.total = (self.total + int.from_bytes(hashlib.md5(line.encode()).digest(), "big")) % self._MOD
        self.count += 1

    def merge(self, other: "SetChecksum") -> "SetChecksum":
        merged = SetChecksum()
        merged.total = (self.total + other.total) % self._MOD
        merged.count = self.count + other.count
        return merged

    def hexdigest(self) -> str:
        return f"{self.total:032x}"
