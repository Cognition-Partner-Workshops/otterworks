"""Remove only the incident responder's customer read indexes on t-odl."""

import json
import sys

PATTERNS = tuple(((field, 1), ('_id', 1)) for field in (
    'source_keys.db2_cust_no', 'source_keys.oracle_account_ids', 'source_keys.crm_contact_id'))


def reset_indexes(collection):
    before = list(collection.list_indexes())
    candidates = [index for index in before
                  if tuple(index['key'].items()) in PATTERNS
                  and 'partialFilterExpression' not in index
                  and not index.get('unique') and not index.get('sparse')
                  and 'collation' not in index]
    patterns = [tuple(index['key'].items()) for index in candidates]
    if len(patterns) != len(set(patterns)):
        raise ValueError('Ambiguous customer read indexes; nothing dropped')
    dropped = []
    for index in candidates:
        collection.drop_index(index['name'])
        dropped.append({'name': index['name'], 'key': dict(index['key'])})
    return {'before': before, 'dropped': dropped, 'after': list(collection.list_indexes())}


def main():
    from pymongo import MongoClient

    credentials = json.load(sys.stdin)
    with MongoClient('mongodb://operational-data-layer-mongo:27017',
                     username=credentials['username'], password=credentials['password'],
                     authSource='odl', serverSelectionTimeoutMS=10000) as client:
        print(json.dumps(reset_indexes(client.odl.customers)))


if __name__ == '__main__':
    main()
