import os
from datetime import datetime
from decimal import Decimal

from bson.decimal128 import Decimal128
from bson.int64 import Int64
from pymongo import MongoClient

from . import oracle

NAME = "mongo"

_client = None


def _db():
    global _client
    if _client is None:
        secret_name = os.getenv("MONGO_URI_SECRET", "MONGO_LOCAL_URI")
        _client = MongoClient(os.environ[secret_name])
    return _client[os.getenv("MONGO_BILLING_DB", "ow_billing_migration")]


def _json_value(value):
    if isinstance(value, Decimal128):
        return format(value.to_decimal().normalize(), "f")
    if isinstance(value, Int64):
        return str(int(value))
    if isinstance(value, datetime):
        return oracle._json_value(value.replace(tzinfo=None))
    if isinstance(value, Decimal):
        return str(value)
    return oracle._json_value(value)


def _rows(documents):
    return [
        {name: _json_value(value) for name, value in doc.items()}
        for doc in documents
    ]


def invoices(tenant_id):
    pipeline = [
        {"$match": {"tenantId": tenant_id}},
        {
            "$lookup": {
                "from": "ratingPeriods",
                "localField": "periodId",
                "foreignField": "_id",
                "as": "rp",
            }
        },
        {"$unwind": "$rp"},
        {
            "$lookup": {
                "from": "codes",
                "let": {"status_cd": "$statusCd"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$eq": ["$codeType", "INV_STATUS"]},
                                    {"$eq": ["$codeVal", "$$status_cd"]},
                                ]
                            }
                        }
                    }
                ],
                "as": "st",
            }
        },
        {"$sort": {"issuedAt": -1, "_id": -1}},
        {
            "$project": {
                "_id": 0,
                "invoice_id": "$_id",
                "period_start": "$rp.periodStart",
                "period_end": "$rp.periodEnd",
                "subtotal": 1,
                "tax": 1,
                "total": 1,
                "status": {
                    "$cond": [
                        {"$gt": [{"$size": "$st"}, 0]},
                        {"$arrayElemAt": ["$st.codeDesc", 0]},
                        None,
                    ]
                },
            }
        },
    ]
    return _rows(_db()["invoices"].aggregate(pipeline))


def invoice_owned(invoice_id, tenant_id):
    doc = _db()["invoices"].find_one(
        {"_id": invoice_id, "tenantId": tenant_id}, {"_id": 1}
    )
    return doc is not None


def invoice_lines(invoice_id):
    doc = _db()["invoices"].find_one({"_id": invoice_id}, {"lines": 1})
    if not doc:
        return []
    lines = sorted(doc.get("lines", []), key=lambda line: line.get("lineNo") or 0)
    return _rows(
        {
            "line_no": line.get("lineNo"),
            "line_type": line.get("lineType"),
            "description": line.get("description"),
            "amount": line.get("amount"),
        }
        for line in lines
    )


def credit_notes(tenant_id):
    docs = _db()["creditNotes"].find({"tenantId": tenant_id}).sort(
        [("issuedOn", -1), ("_id", -1)]
    )
    return _rows(
        {
            "credit_note_id": doc["_id"],
            "issued_on": doc.get("issuedOn"),
            "amount": doc.get("amount"),
            "remaining_amount": doc.get("remainingAmount"),
        }
        for doc in docs
    )


def rating_periods(tenant_id):
    docs = _db()["ratingPeriods"].find({"tenantId": tenant_id}).sort("periodStart", 1)
    return _rows(
        {
            "period_id": doc["_id"],
            "period_start": doc.get("periodStart"),
            "period_end": doc.get("periodEnd"),
        }
        for doc in docs
    )


def rating_results(period_id):
    docs = _db()["ratingResults"].find({"periodId": period_id}).sort("_id", 1)
    return _rows(
        {
            "result_id": doc["_id"],
            "subscription_id": doc.get("subscriptionId"),
            "used_units": doc.get("usedUnits"),
            "quota_units": doc.get("quotaUnits"),
            "rollover_units": doc.get("rolloverUnits"),
            "billable_units": doc.get("billableUnits"),
            "overage_amount": doc.get("overageAmount"),
            "created_at": doc.get("createdAt"),
        }
        for doc in docs
    )
