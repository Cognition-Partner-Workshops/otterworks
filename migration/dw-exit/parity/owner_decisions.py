"""Explicit owner-approved comparison contracts, retaining raw legacy measurements."""
from pathlib import Path
from collections import Counter
import json

import duckdb
from . import ladder

ROOT = Path(__file__).resolve().parents[3]


def approved_retirements():
    return [decision for path in sorted((ROOT/'migration/dw-exit').glob('*/decisions.json'))
            for decision in json.loads(path.read_text())
            if decision.get('status') == 'approved' and decision.get('action') == 'retire']


def apply_retirement(row, obj, decisions):
    for decision in decisions:
        if obj.get('target_type') == 'retire' and row['name'] in decision.get('board_objects', []):
            row.update(status='retired', decision_state='approved', reason=decision['new_behaviour'],
                       retirement_evidence={'decision_id':decision['decision_id'],
                                            'owner_approved':True, 'manifest_target':'retire'})
    return row


def missing_fields(db, source, target, raw, decision):
    def relation(name):
        quoted = '.'.join(ladder.identifier(part) for part in name.split('.'))
        # Validated, quoted local relation identifiers; row values never become SQL.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        cursor = db.execute('SELECT * FROM '+quoted)
        return [column[0] for column in cursor.description], cursor.fetchall()
    columns, before = relation(source)
    target_columns, after = relation(target)
    excluded = set(decision['missing_fields']) & set(columns)
    kept = [index for index,column in enumerate(columns) if column not in excluded]
    project = lambda rows: Counter(tuple(ladder.canonical(row[index]) for index in kept) for row in rows)
    old, new = project(before), project(after) if columns == target_columns else Counter()
    unavailable = columns == target_columns and all(
        row[index] is None for row in after for index,column in enumerate(columns) if column in excluded)
    passed = columns == target_columns and old == new and unavailable
    return {**raw, 'owner_decision':{
        'decision_id':decision['decision_id'], 'scope_valid':passed,
        'missing_fields':sorted(excluded), 'unavailable_fields_are_null':unavailable,
        'approved_comparison':{'passed':passed, 'row_count':{'before':len(before),'after':len(after)},
                               'removed_rows':sum((old-new).values()), 'added_rows':sum((new-old).values()),
                               'compared_columns':[columns[index] for index in kept]},
    }}


def pending_confirmations():
    return [decision for path in sorted((ROOT/'migration/dw-exit').glob('*/decisions.json'))
            for decision in json.loads(path.read_text())
            if decision.get('status') == 'approved-pending-confirmation']


def apply_deviation(row, measurements, decisions):
    failed = [value for value in measurements.values() if not value['passed']]
    if row['status'] != 'red' or not failed:
        return row
    registered = {d.get('decision_id'):d for d in decisions if d.get('decision_id')}
    proofs = [value.get('owner_decision',{}) for value in failed]
    approvals = [registered.get(proof.get('decision_id'),{}) for proof in proofs]
    if not all(proof.get('scope_valid') is True and
               proof.get('approved_comparison',{}).get('passed') is True and
               decision.get('status') in ('approved','approved-pending-confirmation')
               for proof,decision in zip(proofs,approvals)):
        return row
    pending = [d for d in approvals if d['status']=='approved-pending-confirmation']
    state = 'amber' if pending else 'approved_deviation'
    row.update(measurement_status='red',status=state,local_duckdb=state,
               decision_state='approved-pending-confirmation' if pending else 'approved',
               reason='; '.join(dict.fromkeys(d['confirmation'] if pending and d in pending
                   else d['new_behaviour'] for d in approvals)),
               owner_decision_evidence=proofs)
    return row


def apply_confirmation(row, decisions):
    for decision in decisions:
        if row['name'] in decision.get('board_objects', []):
            row.setdefault('measurement_status', row['status'])
            row.update(status='amber', local_duckdb='amber',
                       decision_state=decision['status'], reason=decision['confirmation'])
    return row


def display_names(before, after, source, target, raw, sample_size=5, keys=None):
    table = source.split('.')[-1]
    if source not in ('SFX_USERS.APP_USER', 'SFX_USERS.STG_APP_USER'):
        return raw
    candidates = (['PC_SRC.APP_USER', 'INPUT.APP_USER'] if table.startswith('STG_') else
                  [target.split('.')[0]+'.STG_APP_USER', 'INPUT.STG_APP_USER'])
    available = {s.upper()+'.'+t.upper() for s,t in after.execute(
        'SELECT table_schema,table_name FROM information_schema.tables').fetchall()}
    inputs = next((name for name in candidates if name in available), None)
    if inputs is None:
        return raw
    # Relation choices are fixed owner-decision inputs; column definitions come from local DuckDB metadata.
    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
    original = dict(after.execute('SELECT USER_ID,DISPLAY_NAME FROM '+inputs).fetchall())
    expected = original
    if table.startswith('STG_'):
        expected = {key:None if value is None else value.strip(' ')[:200] for key,value in expected.items()}
    # Relation choices are fixed owner-decision inputs; column definitions come from local DuckDB metadata.
    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
    definitions = before.execute('DESCRIBE '+source).fetchall()
    names = [c[0] for c in definitions]
    uid, display = names.index('USER_ID'), names.index('DISPLAY_NAME')
    # Relation choices are fixed owner-decision inputs; column definitions come from local DuckDB metadata.
    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
    rows = before.execute('SELECT * FROM '+source).fetchall()
    adjusted, valid, changed = [], True, 0
    for row in rows:
        row = list(row)
        if row[uid] in expected:
            value = expected[row[uid]]
            legacy = None if value is None else value[:60]
            if table.startswith('STG_') and original[row[uid]] is not None:
                legacy = original[row[uid]][:60].strip(' ')
            valid &= row[display] in (legacy, value)
            changed += row[display] != value
            row[display] = value
        adjusted.append(row)
    with duckdb.connect() as approved:
        approved.execute('CREATE SCHEMA SFX_USERS')
        # Relation choices are fixed owner-decision inputs; column definitions come from local DuckDB metadata.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        approved.execute('CREATE TABLE '+source+' ('+', '.join(c[0]+' '+c[1] for c in definitions)+')')
        if adjusted:
            approved.executemany('INSERT INTO '+source+' VALUES ('+','.join('?' for _ in names)+')',adjusted)
        result = ladder.local_compare(approved,after,source,target,sample_size,keys,approved_decisions=False)
    result['raw_legacy'] = raw
    result['comparison_rules']['owner_approved'] = 'DISPLAY_NAME widened to 200; full value checked against independent input; legacy prefix checked at 60'
    result['comparison_rules']['legacy_truncated_rows'] = changed
    result['comparison_rules']['legacy_prefix_valid'] = valid
    result['passed'] &= valid
    return result
