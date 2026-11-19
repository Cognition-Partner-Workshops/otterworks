import re
from collections import defaultdict

from .extract import rejected
from .normalize import exception_id, golden_id, match_key


def merge(extracts):
    groups = defaultdict(list)
    exceptions = [e for extract in extracts for e in extract.unplaced]
    for extract in extracts:
        local = defaultdict(list)
        for record in extract.records:
            local[match_key(record.name, record.address)].append(record)
        for key, records in local.items():
            if len(records) > 1:
                for record in records:
                    exceptions.append(rejected(record.source, 'duplicate_match_key', record.key, record.raw))
            else:
                groups[key].extend(records)
    customers = []
    singles = defaultdict(lambda: defaultdict(list))
    for key, records in sorted(groups.items()):
        by_source = {r.source: r for r in records}
        anchor = next(by_source[s] for s in ('db2', 'oracle', 'postgres') if s in by_source)
        sources = sorted(by_source)
        doc = dict(_id=golden_id(f'{anchor.source}:{anchor.key}'), schema_version=1,
                   match_key=key, name=anchor.name, address=anchor.address, customer_since=None,
                   source_keys=dict(db2_cust_no=None, oracle_account_ids=[], crm_contact_id=None),
                   source_records={}, accounts=[], account_history=[], crm=None,
                   match=dict(rule='exact-name-address', sources=sources, status='matched' if len(sources) > 1 else 'single-source'),
                   exception_ids=[], provenance=dict(name=sources, address=sources, customer_since=None))
        if 'db2' in by_source:
            r = by_source['db2']
            doc['source_keys']['db2_cust_no'] = r.key
            doc['source_records']['db2'] = r.data['source_record']
            doc['customer_since'] = r.data['customer_since']
            doc['provenance']['customer_since'] = 'db2'
            doc['account_history'] = r.data['history']
        if 'postgres' in by_source:
            r = by_source['postgres']
            doc['source_keys']['crm_contact_id'] = r.key
            doc['crm'] = r.data
        if 'oracle' in by_source:
            r = by_source['oracle']
            doc['source_keys']['oracle_account_ids'] = [r.data['account']['account_id']]
            doc['accounts'] = [r.data['account']]
            if r.data['ambiguous']:
                keys = [f'oracle:{r.key}']
                eid = exception_id('ambiguous_local_time', keys)
                exceptions.append(dict(_id=eid, reason='ambiguous_local_time', customer_ids=[doc['_id']],
                                       source_keys=keys, detail=r.raw, status='open'))
                doc['exception_ids'].append(eid)
        if len(records) == 1 and anchor.source in ('db2', 'oracle'):
            suffix = re.search(r'(\d{6})\s*$', anchor.name)
            if suffix:
                singles[suffix[1]][anchor.source].append((anchor, doc))
        customers.append(doc)
    for cohort in singles.values():
        for db2, left in cohort['db2']:
            for oracle, right in cohort['oracle']:
                keys = [f'db2:{db2.key}', f'oracle:{oracle.key}']
                eid = exception_id('candidate_match_unconfirmed', keys)
                exceptions.append(dict(_id=eid, reason='candidate_match_unconfirmed', customer_ids=sorted([left['_id'], right['_id']]),
                                       source_keys=keys, detail=dict(db2_name=db2.name, oracle_name=oracle.name,
                                       db2_address=db2.address, oracle_address=oracle.address), status='open'))
                left['exception_ids'].append(eid)
                right['exception_ids'].append(eid)
    for doc in customers:
        doc['exception_ids'].sort()
    return customers, exceptions
