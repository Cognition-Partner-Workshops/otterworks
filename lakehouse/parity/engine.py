"""Deterministic in-memory comparison for demo-sized datasets."""

import hashlib
import json
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP


def encoded(value):
    def typed(item):
        if isinstance(item, Decimal):
            return {'$number': str(item.normalize() if item else Decimal(0))}
        if isinstance(item, (list, tuple)):
            return [typed(v) for v in item]
        return item

    return json.dumps(typed(value), sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def number(value):
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError('Non-finite numeric values are not supported')
    return result


def normalize_value(value, options):
    if value is None:
        return None
    if isinstance(value, str):
        if options.get('trim'):
            value = value.strip()
        elif options.get('rstrip'):
            value = value.rstrip(' ')
        if options.get('case_fold'):
            value = value.casefold()
        if options.get('empty_as_null') and value == '':
            return None
    if options.get('date_format'):
        if not isinstance(value, (date, datetime)):
            value = datetime.strptime(value, options['date_format'])
        return value.isoformat() if isinstance(value, date) and not isinstance(value, datetime) else value.date().isoformat()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if 'numeric_scale' in options:
        value = number(value).quantize(Decimal(1).scaleb(-options['numeric_scale']),
                                       rounding=ROUND_HALF_UP)
    elif isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        value = number(value)
    if isinstance(value, Decimal):
        return value.normalize() if value else Decimal(0)
    return value


def prepare(rows, columns, spec):
    normalization = spec.get('normalize', {})
    result = []
    for row in rows:
        row = {k.lower(): v for k, v in row.items()}
        if set(columns) - row.keys():
            raise ValueError(f'Missing row columns: {sorted(set(columns) - row.keys())}')
        normalized = {}
        for column in columns:
            options = {**normalization.get('*', {}), **normalization.get(column, {})}
            normalized[column] = normalize_value(row[column], options)
        keep = True
        for column, allowed in spec.get('filters', {}).items():
            options = {**normalization.get('*', {}), **normalization.get(column, {})}
            values = allowed if isinstance(allowed, list) else [allowed]
            if normalized[column] not in [normalize_value(v, options) for v in values]:
                keep = False
        if keep:
            result.append(normalized)
    return result


def fingerprints(rows, columns):
    result = {}
    for column in columns:
        values = [row[column] for row in rows]
        present = [value for value in values if value is not None]
        digest = hashlib.sha256()
        for value in sorted(encoded(v) for v in values):
            data = value.encode('utf-8')
            digest.update(len(data).to_bytes(8, 'big'))
            digest.update(data)
        result[column] = {'count': len(values), 'null_count': len(values) - len(present),
                          'sum': str(sum(present, Decimal(0))) if present and all(
                              isinstance(v, Decimal) for v in present) else None,
                          'hash': digest.hexdigest()}
    return result


def compare(legacy_rows, lakehouse_rows, spec, legacy_columns=None, lakehouse_columns=None,
            sample_limit=10):
    if sample_limit < 0:
        raise ValueError('sample_limit must be nonnegative')
    left_names = {c.lower() for c in (legacy_columns if legacy_columns is not None else
                                    legacy_rows[0].keys() if legacy_rows else [])}
    right_names = {c.lower() for c in (lakehouse_columns if lakehouse_columns is not None else
                                     lakehouse_rows[0].keys() if lakehouse_rows else [])}
    columns = spec.get('columns') or sorted(left_names & right_names)
    keys = spec['keys']
    required = set(columns) | set(keys) | set(spec.get('filters', {}))
    if not columns or required - (left_names & right_names):
        raise ValueError(f'No common columns or required columns missing: {sorted(required - (left_names & right_names))}')
    if set(keys) - set(columns):
        raise ValueError('Comparison columns must include every key')
    tolerance = {c: number(v) for c, v in spec.get('tolerance', {}).items()}
    if set(tolerance) - set(columns) or any(v < 0 for v in tolerance.values()):
        raise ValueError('Tolerances must be nonnegative and reference comparison columns')
    left = prepare(legacy_rows, sorted(required), spec)
    right = prepare(lakehouse_rows, sorted(required), spec)

    def index(rows):
        groups = defaultdict(list)
        for row in rows:
            groups[tuple(row[k] for k in keys)].append(row)
        duplicates = [(key, len(values)) for key, values in groups.items() if len(values) > 1]
        duplicates.sort(key=lambda pair: encoded(pair[0]))
        return groups, {'key_count': len(duplicates),
                        'row_count': sum(n for _, n in duplicates),
                        'samples': [{'key': key, 'count': n} for key, n in duplicates[:sample_limit]]}

    left_index, left_duplicates = index(left)
    right_index, right_duplicates = index(right)
    only_left = sorted(left_index.keys() - right_index.keys(), key=encoded)
    only_right = sorted(right_index.keys() - left_index.keys(), key=encoded)
    mismatches = {column: {'count': 0, 'samples': []} for column in columns}
    for key in sorted(left_index.keys() & right_index.keys(), key=encoded):
        if len(left_index[key]) != 1 or len(right_index[key]) != 1:
            continue
        a, b = left_index[key][0], right_index[key][0]
        for column in columns:
            x, y = a[column], b[column]
            equal = x == y
            if column in tolerance and x is not None and y is not None:
                equal = abs(number(x) - number(y)) <= tolerance[column]
            if not equal:
                entry = mismatches[column]
                entry['count'] += 1
                if len(entry['samples']) < sample_limit:
                    entry['samples'].append({'key': key, 'legacy': x, 'lakehouse': y})
    null_keys = {'legacy': sum(any(row[k] is None for k in keys) for row in left),
                 'lakehouse': sum(any(row[k] is None for k in keys) for row in right)}
    passed = (len(left) == len(right) and not only_left and not only_right
              and not left_duplicates['key_count'] and not right_duplicates['key_count']
              and not any(null_keys.values()) and not any(v['count'] for v in mismatches.values()))
    return {'passed': passed, 'columns': columns,
            'row_counts': {'legacy': len(left), 'lakehouse': len(right)},
            'duplicate_keys': {'legacy': left_duplicates, 'lakehouse': right_duplicates},
            'null_key_rows': null_keys,
            'only_in_legacy': {'count': len(only_left), 'samples': only_left[:sample_limit]},
            'only_in_lakehouse': {'count': len(only_right), 'samples': only_right[:sample_limit]},
            'mismatches': mismatches,
            'fingerprints': {'legacy': fingerprints(left, columns),
                             'lakehouse': fingerprints(right, columns)}}
