import argparse
import csv
from pathlib import Path
import re

from psycopg import sql

from bteq.parser import commands
from bteq.runner import Runner
from .generate import QUERY_COLUMNS, OBJECT_COLUMNS, TABLE_COLUMNS


ROOT = Path(__file__).parent
FEEDS = (('qrylog.csv', 'dbc_qrylog', QUERY_COLUMNS),
         ('objectusage.csv', 'dbc_qrylogobjects', OBJECT_COLUMNS),
         ('tablesv.csv', 'dbc_tablesv', TABLE_COLUMNS))


def load_history(runner, root=ROOT):
    for statement in commands((ROOT / 'schema.sql').read_text()):
        database = re.match(r'CREATE DATABASE\s+(\w+)', statement, re.I)
        relation = re.match(r'CREATE\s+(?:(?:SET|MULTISET)\s+TABLE|VIEW)\s+([\w.]+)', statement, re.I)
        if database and runner.conn.execute('SELECT 1 FROM pg_namespace WHERE nspname=%s', (database[1].lower(),)).fetchone():
            continue
        if relation and runner.conn.execute('SELECT to_regclass(%s)', (relation[1].lower(),)).fetchone()[0]:
            continue
        runner.execute(statement)
        if runner.errorcode:
            raise RuntimeError(f'DBC schema: Teradata error {runner.errorcode}')
    result = {}
    with runner.conn.transaction():
        for filename, target, columns in FEEDS:
            count = 0
            with (Path(root) / filename).open(newline='', encoding='utf-8') as handle:
                reader = csv.reader(handle)
                if next(reader, None) != list(columns):
                    raise ValueError(f'{filename}: unexpected CSV header')
                identifier = sql.Identifier('dbc', target)
                runner.conn.execute(sql.SQL('TRUNCATE TABLE {}').format(identifier))
                with runner.conn.cursor().copy(sql.SQL('COPY {} FROM STDIN').format(identifier)) as copy:
                    for row in reader:
                        if len(row) != len(columns):
                            raise ValueError(f'{filename}: wrong field count at row {count+1}')
                        copy.write_row(row)
                        count += 1
            result[target] = count
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    with Runner() as runner:
        counts = load_history(runner, args.root)
    print(f'Loaded {sum(counts.values())} DBQL rows: {counts}')


if __name__ == '__main__':
    main()
