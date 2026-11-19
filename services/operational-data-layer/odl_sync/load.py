import hashlib
from collections import Counter

from bson import json_util
from pymongo import ASCENDING, ReplaceOne


def content_hash(doc):
    return hashlib.sha256(json_util.dumps(doc, json_options=json_util.CANONICAL_JSON_OPTIONS,
                                         sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def indexes(db):
    for name in ('customers', 'mapping_exceptions'):
        if name not in db.list_collection_names():
            db.create_collection(name)
    customers = db.customers
    customers.create_index('match_key', unique=True)
    for key in ('db2_cust_no', 'crm_contact_id'):
        field = 'source_keys.' + key
        customers.create_index(field, unique=True, partialFilterExpression={field: {'$type': 'string'}})
    customers.create_index('source_keys.oracle_account_ids', unique=True,
                           partialFilterExpression={'source_keys.oracle_account_ids.0': {'$exists': True}})
    customers.create_index([('match.status', ASCENDING)])


def replace_changed(collection, documents, applied):
    previous = {r['_id']: r.get('content_hash') for r in collection.find({}, {'content_hash': 1})}
    produced = {doc['_id'] for doc in documents}
    stale = sorted(previous.keys() - produced)
    removed = 0
    for offset in range(0, len(stale), 1000):
        removed += collection.delete_many({'_id': {'$in': stale[offset:offset + 1000]}}).deleted_count
    operations = []
    written = []
    inserted = updated = 0

    def flush():
        nonlocal inserted, updated
        if not operations:
            return
        result = collection.bulk_write(operations, ordered=False)
        inserted += result.upserted_count
        updated += result.modified_count
        for doc in written:
            sources = doc.get('match', {}).get('sources', [])
            for source in sources:
                applied[source] += 1
        operations.clear()
        written.clear()

    for original in documents:
        doc = dict(original)
        doc['content_hash'] = content_hash(original)
        if previous.get(doc['_id']) != doc['content_hash']:
            operations.append(ReplaceOne({'_id': doc['_id']}, doc, upsert=True))
            written.append(doc)
            if len(operations) >= 1000:
                flush()
    flush()
    return dict(inserted=inserted, modified=updated, removed=removed, unchanged=len(documents) - inserted - updated)


def load(db, customers, exceptions):
    indexes(db)
    applied = Counter({s: 0 for s in ('db2', 'oracle', 'postgres')})
    result = dict(customers=replace_changed(db.customers, customers, applied),
                  exceptions=replace_changed(db.mapping_exceptions, exceptions, Counter()))
    result['applied'] = dict(applied)
    return result
