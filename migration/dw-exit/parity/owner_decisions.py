"""Explicit owner-approved comparison contracts, retaining raw legacy measurements."""
from pathlib import Path
import json

import duckdb
from . import ladder

ROOT = Path(__file__).resolve().parents[3]


def pending_confirmations():
    return [decision for path in sorted((ROOT/'migration/dw-exit').glob('*/decisions.json'))
            for decision in json.loads(path.read_text())
            if decision.get('status') == 'approved-pending-confirmation']


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
    original = dict(after.execute('SELECT USER_ID,DISPLAY_NAME FROM '+inputs).fetchall())
    expected = original
    if table.startswith('STG_'):
        expected = {key:None if value is None else value.strip(' ')[:200] for key,value in expected.items()}
    definitions = before.execute('DESCRIBE '+source).fetchall()
    names = [c[0] for c in definitions]
    uid, display = names.index('USER_ID'), names.index('DISPLAY_NAME')
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
