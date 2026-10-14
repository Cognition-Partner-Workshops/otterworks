"""billing_migration document shapes, indexes and validators (mapping spec v2)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from bson.decimal128 import Decimal128
from pymongo import ASCENDING, IndexModel

COLLECTIONS = ("plans", "tenants", "subscriptions")


def bson_date(value: date | None) -> datetime | None:
    if value is None:
        return None
    return datetime(value.year, value.month, value.day, tzinfo=UTC)


def bson_decimal(value: Decimal) -> Decimal128:
    return Decimal128(value)


def _compact(document: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if value is not None}


def plan_document(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "_id": row["id"],
        "code": row["code"],
        "tier": row["tier"],
        "monthlyFee": bson_decimal(row["monthly_fee"]),
        "includedUnits": row["included_units"],
        "overageRate": bson_decimal(row["overage_rate"]),
        "active": row["active"],
    }


def credit_note_document(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "issuedOn": bson_date(row["issued_on"]),
        "amount": bson_decimal(row["amount"]),
        "remainingAmount": bson_decimal(row["remaining_amount"]),
    }


def tenant_document(row: dict[str, Any], credit_notes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "_id": row["id"],
        "name": row["name"],
        "taxExempt": row["tax_exempt"],
        "status": row["status"],
        "creditNotes": [
            credit_note_document(note)
            for note in sorted(credit_notes, key=lambda note: (note["issued_on"], note["id"]))
        ],
    }


def subscription_document(row: dict[str, Any]) -> dict[str, Any]:
    return _compact(
        {
            "_id": row["id"],
            "tenantId": row["tenant_id"],
            "planId": row["plan_id"],
            "startsOn": bson_date(row["starts_on"]),
            "endsOn": bson_date(row["ends_on"]),
            "status": row["status"],
            "suspendedOn": bson_date(row["suspended_on"]),
        }
    )


INDEXES: dict[str, list[IndexModel]] = {
    "plans": [
        IndexModel([("monthlyFee", ASCENDING), ("code", ASCENDING)]),
        IndexModel([("code", ASCENDING)], unique=True),
    ],
    "tenants": [
        IndexModel([("creditNotes.remainingAmount", ASCENDING)]),
        IndexModel(
            [
                ("creditNotes.issuedOn", ASCENDING),
                ("creditNotes.id", ASCENDING),
                ("creditNotes.remainingAmount", ASCENDING),
            ]
        ),
        IndexModel([("name", ASCENDING)], unique=True),
    ],
    "subscriptions": [
        IndexModel([("tenantId", ASCENDING), ("endsOn", ASCENDING), ("startsOn", ASCENDING)]),
        IndexModel([("endsOn", ASCENDING), ("startsOn", ASCENDING)]),
        IndexModel([("planId", ASCENDING)]),
    ],
}

_UUID = {"bsonType": "binData"}
_DECIMAL = {"bsonType": "decimal"}
_DATE = {"bsonType": "date"}

VALIDATORS: dict[str, dict[str, Any]] = {
    "plans": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "_id",
                "code",
                "tier",
                "monthlyFee",
                "includedUnits",
                "overageRate",
                "active",
            ],
            "properties": {
                "_id": _UUID,
                "code": {"bsonType": "string"},
                "tier": {"enum": ["starter", "growth", "scale"]},
                "monthlyFee": _DECIMAL,
                "includedUnits": {"bsonType": "int"},
                "overageRate": _DECIMAL,
                "active": {"bsonType": "bool"},
            },
        }
    },
    "tenants": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["_id", "name", "taxExempt", "status", "creditNotes"],
            "properties": {
                "_id": _UUID,
                "name": {"bsonType": "string"},
                "taxExempt": {"bsonType": "bool"},
                "status": {"enum": ["active", "suspended"]},
                "creditNotes": {
                    "bsonType": "array",
                    "items": {
                        "bsonType": "object",
                        "required": ["id", "issuedOn", "amount", "remainingAmount"],
                        "properties": {
                            "id": _UUID,
                            "issuedOn": _DATE,
                            "amount": _DECIMAL,
                            "remainingAmount": _DECIMAL,
                        },
                    },
                },
            },
        }
    },
    "subscriptions": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["_id", "tenantId", "planId", "startsOn", "status"],
            "properties": {
                "_id": _UUID,
                "tenantId": _UUID,
                "planId": _UUID,
                "startsOn": _DATE,
                "endsOn": _DATE,
                "status": {"enum": ["active", "suspended", "cancelled"]},
                "suspendedOn": _DATE,
            },
        }
    },
}
