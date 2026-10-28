"""Render a bounded snapshot as SQL for the existing warehouse, without executing it."""

import hashlib
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SOURCE = "oracle/OW_BILLING"


def validateSnapshot(snapshot: dict[str, Any]) -> None:
    if snapshot["source"] != SOURCE:
        raise ValueError("Unexpected source")
    datetime.fromisoformat(snapshot["as_of"])
    datetime.fromisoformat(snapshot["captured_at"].replace("Z", "+00:00"))
    requiredFields = {
        "tenants": ("id", "name", "status_cd"),
        "subscriptions": ("id", "tenant_id", "status_cd", "starts_on"),
        "invoices": ("id", "tenant_id", "issued_at", "total", "status_cd"),
        "dunning_attempts": ("id", "tenant_id", "invoice_id", "attempt_no", "scheduled_for", "status_cd"),
        "credit_notes": ("id", "tenant_id", "issued_on", "amount", "remaining_amount"),
    }
    if not snapshot["tenants"]:
        raise ValueError("Empty tenant snapshot")
    tenantIds = {row["id"] for row in snapshot["tenants"]}
    for tableName, fields in requiredFields.items():
        rows = snapshot[tableName]
        if len({row["id"] for row in rows}) != len(rows):
            raise ValueError(f"Duplicate IDs in {tableName}")
        for row in rows:
            if any(row.get(field) is None for field in fields):
                raise ValueError(f"Missing required field in {tableName}")
            if tableName != "tenants" and row["tenant_id"] not in tenantIds:
                raise ValueError(f"Unattributed {tableName} row")
            if row["id"] == "NO_SUBSCRIPTION":
                raise ValueError("Reserved subscription placeholder used as ID")
            for dateField in ("issued_at", "starts_on", "scheduled_for", "issued_on"):
                if dateField in row:
                    datetime.fromisoformat(row[dateField])
            for amountField in ("total", "amount", "remaining_amount"):
                if amountField in row and not math.isfinite(float(row[amountField])):
                    raise ValueError("Non-finite financial value")
    invoiceOwners = {row["id"]: row["tenant_id"] for row in snapshot["invoices"]}
    for row in snapshot["dunning_attempts"]:
        if invoiceOwners.get(row["invoice_id"]) != row["tenant_id"]:
            raise ValueError("Dunning attempt has missing or cross-tenant invoice")


def snapshotSql(payload: str) -> str:
    snapshot = json.loads(payload)
    validateSnapshot(snapshot)
    if len(payload.encode()) > 8_000_000:
        raise ValueError("Snapshot exceeds this demo's 8 MB inline SQL limit")
    snapshotId = hashlib.sha256(payload.encode()).hexdigest()
    payloadHex = payload.encode().hex()
    return f"""BEGIN
CREATE SCHEMA IF NOT EXISTS ow_tp.ow_tp_dunning_risk;
CREATE TABLE IF NOT EXISTS ow_tp.ow_tp_dunning_risk.ow_tp_snapshots (
    snapshot_id STRING NOT NULL, payload STRING NOT NULL
) USING DELTA;
MERGE INTO ow_tp.ow_tp_dunning_risk.ow_tp_snapshots AS target
USING (SELECT '{snapshotId}' AS snapshot_id,
              decode(unhex('{payloadHex}'), 'UTF-8') AS payload) AS source
ON target.snapshot_id = source.snapshot_id
WHEN NOT MATCHED THEN INSERT *;
END;
"""


if __name__ == "__main__":
    Path(sys.argv[2]).write_text(snapshotSql(Path(sys.argv[1]).read_text()))
