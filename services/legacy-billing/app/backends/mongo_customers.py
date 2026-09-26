"""MongoDB read backend for the customerMaster collection (u-02-customers).

Returns the same legacy-shaped dicts the Oracle queries produced: snake_case
keys, JSON-safe values. Read-only; the collection is owned by the loader.
"""

import os
import re

from bson.decimal128 import Decimal128
from pymongo import MongoClient

from backends import oracle

TARGET_DB = "ow_billing_migration"
COLLECTION = "customerMaster"

_client = None

_CAMEL = re.compile(r"([A-Z])")
_DIGIT_SUFFIX = re.compile(r"([a-zA-Z])(\d+)$")

# Spec targets that drop the *_YN / *_CSV suffix the Oracle column names carry;
# everything else maps back with the regexes above (verified against the spec's
# source column names).
_LEGACY_KEY = {
    "taxExempt": "tax_exempt_yn",
    "creditHold": "credit_hold_yn",
    "dunningExempt": "dunning_exempt_yn",
    "vip": "vip_yn",
    "promoCodes": "promo_codes_csv",
}


def _mongo_client():
    global _client
    if _client is None:
        _client = MongoClient(os.environ["MONGO_LOCAL_URI"])
    return _client


def _snake(name):
    if name in _LEGACY_KEY:
        return _LEGACY_KEY[name]
    return _DIGIT_SUFFIX.sub(
        r"\1_\2", _CAMEL.sub(r"_\1", name).lower()
    )


def _legacy_value(value):
    if isinstance(value, Decimal128):
        return str(value.to_decimal())
    if isinstance(value, bool):
        return "Y" if value else "N"
    if isinstance(value, list):
        return [_legacy_value(item) for item in value]
    return oracle._json_value(value)


def _legacy_doc(doc):
    out = {}
    for key, value in doc.items():
        if key in ("_id", "_quarantine"):
            continue
        out[_snake(key)] = _legacy_value(value)
    return out


def customer_for_tenant(tenant_id):
    doc = _mongo_client()[TARGET_DB][COLLECTION].find_one(
        {"tenantId": tenant_id}, sort=[("custSeqNo", 1)]
    )
    if doc is None:
        return None
    body = _legacy_doc(doc)
    body["cust_id"] = doc["_id"]
    attributes = [_legacy_doc(el) for el in doc.get("attributes", [])]
    attributes.sort(key=lambda el: el.get("eav_id") or 0)
    body["attributes"] = attributes
    return body


def customer_summary_for_tenant(tenant_id):
    doc = _mongo_client()[TARGET_DB][COLLECTION].find_one(
        {"tenantId": tenant_id}, sort=[("custSeqNo", 1)]
    )
    if doc is None:
        return None
    body = _legacy_doc(doc)
    return {
        key: body.get(key)
        for key in (
            "cust_no",
            "cust_name",
            "cur_bal_amt",
            "past_due_amt",
            "credit_hold_yn",
        )
    }
