import argparse
import json
import re
from pathlib import Path

from .connection import connect


def identifier(value):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', value):
        raise ValueError(f'Invalid identifier: {value!r}')
    return '"' + value.upper() + '"'


def relation(value):
    parts = value.split('.')
    if len(parts) != 3:
        raise ValueError('Relations must be fully qualified')
    return '.'.join(map(identifier, parts))


def assert_parity(results):
    if not results:
        raise AssertionError('No relations compared')
    failed = [r['name'] for r in results if not r['passed']]
    if failed:
        raise AssertionError('Parity mismatch: ' + ', '.join(failed))


class Ladder:
    def __init__(self, connection, sample_size=5):
        self.connection = connection
        self.sample_size = sample_size
        self.queries = []

    def query(self, sql, parameters=None):
        with self.connection.cursor() as cursor:
            cursor.execute(sql, parameters)
            rows = cursor.fetchall()
            self.queries.append({'query_id': cursor.sfqid, 'sql': sql})
            return rows

    def compare(self, name, before, after, keys):
        start = len(self.queries)
        before, after = relation(before), relation(after)
        columns_b = self.query(f'DESC TABLE {before}')
        columns_a = self.query(f'DESC TABLE {after}')
        columns = [c[0] for c in columns_b]
        if columns != [c[0] for c in columns_a]:
            raise ValueError(f'{name}: column names/order differ')
        if not keys or not set(keys) <= set(columns):
            raise ValueError(f'{name}: keys must name existing columns')
        quoted = list(map(identifier, columns))
        k = ', '.join(map(identifier, keys))
        counts = [self.query(f'SELECT COUNT(*) FROM {t}')[0][0] for t in (before, after)]
        profiles = ', '.join(expr for c in quoted for expr in (
            f'COUNT(*) - COUNT({c})', f'MIN({c})', f'MAX({c})', f'COUNT(DISTINCT {c})'))
        profiles_b, profiles_a = [self.query(f'SELECT {profiles} FROM {t}')[0]
                                  for t in (before, after)]
        profile_diffs = {}
        for index, column in enumerate(columns):
            b = profiles_b[index*4:index*4+4]
            a = profiles_a[index*4:index*4+4]
            if b != a:
                profile_diffs[column] = {'before': b, 'after': a}
        # Group by key AND digest: duplicate multiplicity remains part of parity.
        values = [f"TO_VARCHAR({c}, 'TM9')" if columns_b[i][1].startswith('NUMBER(')
                  else f'TO_VARCHAR({c})' for i, c in enumerate(quoted)]
        digest = 'SHA2(TO_JSON(ARRAY_CONSTRUCT(' + ', '.join(values) + ')), 256)'
        join_keys = ' AND '.join(f'EQUAL_NULL(b.{identifier(c)}, a.{identifier(c)})' for c in keys)
        ctes = f'''WITH b AS (SELECT {k}, {digest} AS _hash, COUNT(*) AS _n
            FROM {before} GROUP BY {k}, _hash),
            a AS (SELECT {k}, {digest} AS _hash, COUNT(*) AS _n
            FROM {after} GROUP BY {k}, _hash),
            mismatches AS (SELECT {', '.join(f'COALESCE(b.{identifier(c)}, a.{identifier(c)}) AS {identifier(c)}' for c in keys)},
            ABS(COALESCE(b._n,0)-COALESCE(a._n,0)) AS _difference
            FROM b FULL OUTER JOIN a ON {join_keys} AND b._hash=a._hash
            WHERE COALESCE(b._n,0) <> COALESCE(a._n,0))'''
        hash_difference = self.query(ctes + ' SELECT COALESCE(SUM(_difference),0) FROM mismatches')[0][0]
        sample_keys = self.query(ctes + f' SELECT DISTINCT {k} FROM mismatches ORDER BY {k} LIMIT {self.sample_size}')
        if not sample_keys:
            sample_keys = self.query(f'SELECT DISTINCT {k} FROM {before} ORDER BY {k} LIMIT {self.sample_size}')
        samples = []
        # Values are fetched independently; tests never trim, fold case or coerce them.
        for key in sample_keys:
            where = ' AND '.join(f'EQUAL_NULL({identifier(column)}, ?)' for column in keys)
            b, a = [self.query(f'SELECT * FROM {t} WHERE {where} ORDER BY {digest}', key) for t in (before, after)]
            if b != a:
                samples.append({'key': key, 'before': b, 'after': a})
        return {'name': name, 'before_count': counts[0], 'after_count': counts[1],
                'count_passed': counts[0] == counts[1],
                'profile_mismatched_columns': len(profile_diffs), 'profiles': profile_diffs,
                'hash_difference': int(hash_difference), 'sample_diffs': samples,
                'sampled_keys': len(sample_keys),
                'passed': counts[0] == counts[1] and not profile_diffs and not hash_difference and not samples,
                'queries': self.queries[start:]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--step', default='parity')
    args = parser.parse_args()
    with connect(args.step) as connection:
        ladder = Ladder(connection)
        results = []
        args.output.parent.mkdir(parents=True, exist_ok=True)
        for entry in json.loads(args.manifest.read_text()):
            r = ladder.compare(**entry)
            results.append(r)
            args.output.write_text(json.dumps(results, indent=2, default=str) + '\n')
            print(f"{r['name']} | {r['before_count']} | {r['after_count']} | {'GREEN' if r['passed'] else 'RED'}", flush=True)
    assert_parity(results)


if __name__ == '__main__':
    main()
