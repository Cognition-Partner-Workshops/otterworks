"""Customer write path for the MongoDB `customers` collection.

Carries the behaviour that lived in the Oracle triggers on CUSTOMER_MASTER and
ENTITY_ATTR_VALUE:

* TRG_CUSTOMER_MASTER_SEQ  -> ``cust_seq_no`` allocated from ``counters`` when absent,
  ``cust_name_upper`` derived from ``cust_name``, ``row_version_no`` defaulted to 1.
* TRG_CUSTOMER_MASTER_HIST -> on update/delete the full prior document is appended to
  ``customers_history`` with ``hist_op`` UPD|DEL and an id from ``counters``.
* TRG_ENTITY_ATTR_VALUE_SEQ -> ``eav_id`` allocated from ``counters`` when an attribute
  is appended to ``attributes[]``.

Sequence documents are ``{_id: <sequence name lower>, seq: <last value>}``; allocation is a
single atomic ``$inc`` so concurrent writers never share a value.
"""

from datetime import datetime, timezone

from bson import Int64
from pymongo import ReturnDocument

NS_VALUE = "mongo_205236"
SEQ_CUSTOMER = "seq_customer_master"
SEQ_HISTORY = "seq_customer_master_hist"
SEQ_EAV = "seq_entity_attr_value"
HIST_DT_FORMAT = "%d-%b-%y %H:%M:%S"


def next_value(database, sequence):
    doc = database["counters"].find_one_and_update(
        {"_id": sequence},
        {"$inc": {"seq": Int64(1)}},
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        raise LookupError(f"counter {sequence!r} is not seeded")
    return Int64(doc["seq"])


def before_insert(database, customer):
    """TRG_CUSTOMER_MASTER_SEQ: fill sequence, upper-case name, default row version."""
    if customer.get("cust_seq_no") is None:
        customer["cust_seq_no"] = next_value(database, SEQ_CUSTOMER)
    name = customer.get("cust_name")
    customer["cust_name_upper"] = name.upper() if name is not None else None
    if customer.get("row_version_no") is None:
        customer["row_version_no"] = 1
    customer.setdefault("attributes", [])
    customer["ns"] = NS_VALUE
    return customer


def history_document(database, prior, op, now=None):
    """TRG_CUSTOMER_MASTER_HIST row image: HIST_ID, HIST_DT, HIST_OP then the old row."""
    now = now or datetime.now(timezone.utc)
    hist = {
        "_id": next_value(database, SEQ_HISTORY),
        "hist_dt": now.strftime(HIST_DT_FORMAT).upper(),
        "hist_op": op,
    }
    hist["hist_id"] = hist["_id"]
    for key, value in prior.items():
        if key == "_id":
            hist["cust_id"] = value
        elif key not in ("attributes", "ns"):
            hist[key] = value
    hist["ns"] = NS_VALUE
    return hist


def insert_customer(database, customer):
    before_insert(database, customer)
    database["customers"].insert_one(customer)
    return customer


def update_customer(database, cust_id, changes):
    prior = database["customers"].find_one({"_id": cust_id})
    if prior is None:
        return None
    changes = dict(changes)
    if "cust_name" in changes:
        name = changes["cust_name"]
        changes["cust_name_upper"] = name.upper() if name is not None else None
    changes["row_version_no"] = int(prior.get("row_version_no") or 0) + 1
    # Mutate first under the optimistic row_version_no guard; the history image is
    # appended only for the exact prior document the update actually replaced.
    replaced = database["customers"].find_one_and_update(
        {"_id": cust_id, "row_version_no": prior.get("row_version_no")},
        {"$set": changes},
        return_document=ReturnDocument.BEFORE,
    )
    if replaced is None:
        return None
    database["customers_history"].insert_one(history_document(database, replaced, "UPD"))
    return database["customers"].find_one({"_id": cust_id})


def delete_customer(database, cust_id):
    prior = database["customers"].find_one_and_delete({"_id": cust_id})
    if prior is None:
        return False
    database["customers_history"].insert_one(history_document(database, prior, "DEL"))
    return True


def add_attribute(database, cust_id, attr_name, attr_value, attr_type="STR", now=None):
    """TRG_ENTITY_ATTR_VALUE_SEQ: eav_id from counters; element appended to attributes[]."""
    now = now or datetime.now(timezone.utc)
    element = {
        "eav_id": next_value(database, SEQ_EAV),
        "entity_type": "CUSTOMER",
        "entity_id": cust_id,
        "attr_name": attr_name,
        "attr_value": attr_value,
        "attr_type": attr_type,
        "created_dt": now.strftime("%d-%b-%y").upper(),
    }
    result = database["customers"].update_one(
        {"_id": cust_id}, {"$push": {"attributes": element}}
    )
    return element if result.matched_count == 1 else None
