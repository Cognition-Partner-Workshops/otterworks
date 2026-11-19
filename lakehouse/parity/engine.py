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
    aggregate = spec.get('candidate_aggregate')
    if aggregate:
        required |= set(aggregate['group_keys']) | {aggregate['value'], aggregate['count'], aggregate['total']}
    if not columns or required - (left_names & right_names):
        raise ValueError(f'No common columns or required columns missing: {sorted(required - (left_names & right_names))}')
    if set(keys) - set(columns):
        raise ValueError('Comparison columns must include every key')
    tolerance = {c: number(v) for c, v in spec.get('tolerance', {}).items()}
    if set(tolerance) - set(columns) or any(v < 0 for v in tolerance.values()):
        raise ValueError('Tolerances must be nonnegative and reference comparison columns')
    left = prepare(legacy_rows, sorted(required), spec)
    right = prepare(lakehouse_rows, sorted(required), spec)
    if spec.get('comparison') == 'candidates':
        return compare_candidates(left, right, columns, keys, aggregate, sample_limit)

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


def compare_candidates(left, right, columns, keys, aggregate, sample_limit):
    def index(rows, fields):
        groups = defaultdict(list)
        for row in rows:
            groups[tuple(row[field] for field in fields)].append(row)
        return groups

    candidates, selected = index(left, keys), index(right, keys)
    failures = set()
    tied = set()
    matched = {}
    for key in candidates.keys() | selected.keys():
        choices, winners = candidates.get(key, []), selected.get(key, [])
        if len(choices) > 1:
            tied.add(key)
        matches = [row for row in choices if len(winners) == 1 and
                   all(row[column] == winners[0][column] for column in columns)]
        if any(value is None for value in key) or not matches:
            failures.add(key)
        else:
            matched[key] = matches[0]

    bounds = []
    if aggregate:
        group_keys = aggregate['group_keys']
        if any(len(index(rows, group_keys)) != 1 for rows in candidates.values()):
            raise ValueError('Candidates for a key must share aggregate group keys')
        left_groups, right_groups = index(left, group_keys), index(right, group_keys)
        tied_groups, failed_groups = set(), set()

        def total(values):
            present = [number(value) for value in values if value is not None]
            return sum(present, Decimal(0)) if present else None

        for group in left_groups.keys() | right_groups.keys():
            choices, winners = left_groups.get(group, []), right_groups.get(group, [])
            contributions = index(choices, keys)
            group_ids = set(contributions) | set(index(winners, keys))
            if group_ids & tied:
                tied_groups.add(group)
            low, high, present, nullable = [], [], [], []
            for rows in contributions.values():
                values = [number(row[aggregate['value']]) for row in rows
                          if row[aggregate['value']] is not None]
                present.extend(values)
                nullable.append(any(row[aggregate['value']] is None for row in rows))
                options = values + ([Decimal(0)] if nullable[-1] else [])
                low.append(min(options))
                high.append(max(options))
            minimum, maximum = total(low), total(high)
            if all(nullable):
                minimum = min(present) if present and minimum == 0 and min(present) > 0 else minimum
                maximum = max(present) if present and maximum == 0 and max(present) < 0 else maximum
            if not present:
                minimum = maximum = None
            expected = total(matched[key][aggregate['value']] for key in group_ids if key in matched)
            observed = {(row[aggregate['count']], row[aggregate['total']]) for row in winners}
            legacy_observed = {(row[aggregate['count']], row[aggregate['total']]) for row in choices}
            valid = (bool(choices) and bool(winners) and not group_ids & failures and
                     observed == {(Decimal(len(contributions)), expected)} and
                     (expected is None and all(nullable) or
                      expected is not None and minimum is not None and maximum is not None and
                      minimum <= expected <= maximum))
            if group not in tied_groups:
                valid = valid and observed == legacy_observed
            if not valid:
                failed_groups.add(group)
            bounds.append({'key': group, 'minimum': minimum, 'maximum': maximum,
                           'recomputed': expected})
        all_keys = left_groups.keys() | right_groups.keys()
        failures, tied = failed_groups, tied_groups
    else:
        all_keys = candidates.keys() | selected.keys()
    result = {'passed': not failures,
              'comparison': 'candidates',
              'row_counts': {'legacy': len(left), 'lakehouse': len(right)},
              'exact_matched_rows': len(all_keys - tied - failures),
              'tie_resolved_rows': len(tied - failures),
              'mismatches': len(failures),
              'mismatch_samples': sorted(failures, key=encoded)[:sample_limit]}
    if aggregate:
        result['aggregate_bounds_checked'] = len(bounds)
        result['aggregate_bounds'] = sorted(bounds, key=lambda row: encoded(row['key']))[:sample_limit]
    return result
