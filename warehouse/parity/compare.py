"""Type-stable normalisation and duplicate-aware keyed row comparison."""
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json


def normal(value):
    if value is None:
        return ['null', None]
    if isinstance(value, bool):
        return ['bool', value]
    if isinstance(value, (int, float, Decimal)):
        n = Decimal(str(value))
        value = format(n, 'f')
        if '.' in value:
            value = value.rstrip('0').rstrip('.')
        return ['number', '0' if n == 0 else value]
    if isinstance(value, datetime):
        if value.tzinfo:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return ['timestamp', value.isoformat(timespec='microseconds')]
    if isinstance(value, date):
        return ['date', value.isoformat()]
    return ['string', str(value).strip()]


def digest(values):
    return hashlib.sha256(json.dumps([normal(v) for v in values],
                                    separators=(',', ':')).encode()).hexdigest()


def compare(before, after, columns, keys, sample=10):
    def group(rows):
        out = defaultdict(list)
        for row in rows:
            key = digest([row[k] for k in keys]) if keys else digest([row[c] for c in columns])
            out[key].append(row)
        return out
    b, a = group(before), group(after)
    missing, extra = set(b) - set(a), set(a) - set(b)
    changed = {k for k in b.keys() & a.keys() if
               Counter(digest([r[c] for c in columns]) for r in b[k]) !=
               Counter(digest([r[c] for c in columns]) for r in a[k])}
    diffs = []
    for k in sorted(missing | extra | changed)[:sample]:
        br, ar = b.get(k, []), a.get(k, [])
        diffs.append({'key': {c: normal((br or ar)[0][c]) for c in keys} or {'row_hash': k},
                      'before_count': len(br), 'after_count': len(ar),
                      'columns': {c: {'before': [normal(r[c]) for r in br],
                                      'after': [normal(r[c]) for r in ar]}
                                  for c in columns if [normal(r[c]) for r in br] !=
                                  [normal(r[c]) for r in ar]}})
    return dict(before_rows=len(before), after_rows=len(after),
                rowcount_match=len(before) == len(after),
                keyed_hash_match=not (missing or extra or changed),
                matched_keys=len(b.keys() & a.keys()) - len(changed),
                missing_keys=len(missing), extra_keys=len(extra), changed_keys=len(changed),
                sampled_diffs=diffs, comparison_mode='business-key' if keys else 'whole-row-hash-multiset')


def status(result, amber=None):
    if amber:
        if not amber.strip() or '\n' in amber:
            raise ValueError('AMBER requires a one-sentence reason')
        return 'AMBER'
    return ('VERIFIED' if result.get('rowcount_match') is True and
            result.get('keyed_hash_match') is True and result.get('rerun_duplicates') == 0
            and result.get('run1_rows') == result.get('run2_rows') == result.get('after_rows')
            else 'PENDING')
