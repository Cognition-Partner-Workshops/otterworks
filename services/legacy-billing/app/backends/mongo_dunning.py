import os
from datetime import date, datetime, time

NAME = "mongo"
DB_NAME = "ow_billing_migration"
DEFAULT_LIMIT = 200


def _mongo_uri():
    env_name = os.getenv("BILLING_MONGO_URI_SECRET", "MONGO_LOCAL_URI")
    return os.environ[env_name]


def _json_date(value):
    if isinstance(value, datetime):
        if value.time() == time.min:
            return value.date().isoformat()
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def render_row(doc):
    attempt_no = doc.get("attemptNo")
    return {
        "id": doc.get("_id"),
        "tenant_id": doc.get("tenantId"),
        "invoice_id": doc.get("invoiceId"),
        "attempt_no": str(attempt_no) if attempt_no is not None else None,
        "scheduled_for": _json_date(doc.get("scheduledFor")),
        "status": doc.get("status"),
    }


def admin_dunning(as_of, limit=DEFAULT_LIMIT):
    import pymongo

    cutoff = datetime.combine(as_of, time.min)
    client = pymongo.MongoClient(_mongo_uri())
    try:
        docs = client[DB_NAME]["dunningAttempts"].aggregate(
            [
                {"$match": {"scheduledFor": {"$lte": cutoff}}},
                {"$sort": {"scheduledFor": -1, "_id": -1}},
                {"$limit": limit},
                {
                    "$lookup": {
                        "from": "codes",
                        "let": {"status_cd": "$statusCd"},
                        "pipeline": [
                            {
                                "$match": {
                                    "$expr": {
                                        "$and": [
                                            {"$eq": ["$codeType", "DUN_STATUS"]},
                                            {"$eq": ["$codeVal", "$$status_cd"]},
                                        ]
                                    }
                                }
                            }
                        ],
                        "as": "status_code",
                    }
                },
                {
                    "$set": {
                        "status": {
                            "$ifNull": [{"$first": "$status_code.codeDesc"}, None]
                        }
                    }
                },
                {"$unset": "status_code"},
            ]
        )
        return [render_row(doc) for doc in docs]
    finally:
        client.close()
