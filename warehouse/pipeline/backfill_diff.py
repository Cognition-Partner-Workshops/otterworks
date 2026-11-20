"""Compare local load snapshots, retaining key multiplicity and ignoring load timestamps."""
import argparse
from collections import Counter, defaultdict
from pathlib import Path

import duckdb


def snapshot(path):
    days = defaultdict(list)
    with duckdb.connect(str(path), read_only=True) as connection:
        cursor = connection.execute('SELECT * EXCLUDE (_LOADED_AT) FROM RAW_BILLING.USAGE_DAILY')
        columns = [column[0] for column in cursor.description]
        for row in cursor.fetchall():
            days[row[columns.index('_SRC_FILE')]].append(row)
    return columns, days


def report(before, after):
    columns, old = snapshot(before)
    new_columns, new = snapshot(after)
    if columns != new_columns:
        raise ValueError('Snapshot columns differ')
    key = columns.index('USAGE_DAILY_ID')
    amount = columns.index('AMOUNT')
    lines = ['# Backfill diff', '',
             '| Source day | Snapshot | Rows | Distinct IDs | Duplicate keys | Amount sum | NULL counts |',
             '|---|---|---:|---:|---:|---:|---|']
    changes = []
    for day in sorted(old.keys() | new.keys()):
        for label, rows in [('before', old[day]), ('after', new[day])]:
            keys = Counter(row[key] for row in rows)
            nulls = ', '.join(f'{name}={sum(row[index] is None for row in rows)}'
                              for index, name in enumerate(columns))
            lines.append(f'| {day} | {label} | {len(rows)} | {len(keys)} | '
                         f'{sum(count > 1 for count in keys.values())} | '
                         f'{sum(row[amount] or 0 for row in rows)} | {nulls} |')
        def keyed(rows):
            groups = defaultdict(Counter)
            for row in rows:
                groups[row[key]][row] += 1
            return groups
        left, right = keyed(old[day]), keyed(new[day])
        changed = sum(left[k] != right[k] for k in left.keys() | right.keys())
        changes.extend(['', f'{day}: **{changed} changed keys**; '
                      f'identical excluding _LOADED_AT: **{Counter(old[day]) == Counter(new[day])}**.', ''])
    return '\n'.join(lines + changes)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = report(args.before, args.after)
    if args.output:
        args.output.write_text(result + '\n')
    print(result)
