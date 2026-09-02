"""MongoDB billing storage references for the U5 migration."""

from __future__ import annotations

import os

from pymongo import MongoClient

NS_VALUE = "mongo_205236"
TARGET_DB = "ow_tp_mongodb_205236"
COLLECTIONS = {
    "subscriptions": "subscriptions",
    "subscriptions_history": "subscriptions_history",
    "usage_events": "usage_events",
    "rating_periods": "rating_periods",
    "billing_invoices": "billing_invoices",
    "credit_notes": "credit_notes",
    "dunning_attempts": "dunning_attempts",
    "notifications": "notifications",
    "billing_audit_log": "billing_audit_log",
    "codes": "codes",
    "tenants": "tenants",
    "plans": "plans",
}


def mongo_client(uri_secret: str = "MONGODB_ATLAS_URI") -> MongoClient:
    uri = os.environ.get(uri_secret)
    if not uri:
        raise RuntimeError(f"required secret environment variable is missing: {uri_secret}")
    return MongoClient(uri)


def billing_db(client=None):
    if client is None:
        client = mongo_client()
    return client[TARGET_DB]
