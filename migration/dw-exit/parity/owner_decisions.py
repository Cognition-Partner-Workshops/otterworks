"""Narrow owner approvals retain raw parity failures and validate every row."""
from collections import Counter
import hashlib
import json
from pathlib import Path

from .ladder import canonical

ROOT = Path(__file__).resolve().parents[3]


def decision():
    return json.loads((ROOT/'migration/dw-exit/users/decisions.json').read_text())[0]


def display_names(before, after, source, target):
    def read(db, relation):
        quoted = '.'.join('"'+part.replace('"', '""')+'"' for part in relation.split('.'))
        cursor = db.execute('SELECT * FROM '+quoted)
        return [c[0] for c in cursor.description], cursor.fetchall()
    columns, old = read(before, source)
    new_columns, new = read(after, target)
    proof = dict(decision_id=decision()['decision_id'], scope_valid=False,
                 before_count=len(old), after_count=len(new), differing_rows=0,
                 other_columns_hash_equal=False, legacy_prefix_valid=False)
    if columns != new_columns or 'DISPLAY_NAME' not in columns or 'USER_ID' not in columns:
        return proof
    key, display = columns.index('USER_ID'), columns.index('DISPLAY_NAME')
    if any(count != 1 for count in Counter(row[key] for row in old).values()) or any(
            count != 1 for count in Counter(row[key] for row in new).values()):
        return proof
    old, new = {row[key]:row for row in old}, {row[key]:row for row in new}
    if old.keys() != new.keys():
        return proof
    def digest(row):
        return hashlib.sha256(canonical(tuple(v for i,v in enumerate(row) if i != display)).encode()).hexdigest()
    other_equal, prefix_valid, changed = True, True, 0
    for key, row in old.items():
        target_row = new[key]
        other_equal &= digest(row) == digest(target_row)
        a, b = row[display], target_row[display]
        prefix_valid &= b is None or isinstance(b, str) and len(b) <= 200
        if a != b:
            changed += 1
            prefix_valid &= isinstance(a, str) and isinstance(b, str) and a == b[:60]
    proof.update(scope_valid=bool(other_equal and prefix_valid), differing_rows=changed,
                 other_columns_hash_equal=bool(other_equal), legacy_prefix_valid=bool(prefix_valid))
    return proof


def apply(row, proofs):
    approval = decision()
    if row['name'] not in approval['board_objects'] or approval['status'] != 'approved':
        return
    row['owner_decision_evidence'] = proofs
    if not proofs or not all(p['scope_valid'] for p in proofs):
        return
    row.update(measurement_status=row['status'], status='approved_deviation',
               decision_state='approved', reason=approval['new_behaviour'])
