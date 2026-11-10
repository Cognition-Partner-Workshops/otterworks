import argparse
import re
from pathlib import Path

from psycopg import sql

from .parser import commands, split
from .runner import Runner


DDL_ROOT = Path(__file__).resolve().parents[1] / 'ddl'


def extend_table(runner, statement, name):
    translated, after = runner.create_table(statement)
    existing = {row[0] for row in runner.conn.execute(
        'SELECT attname FROM pg_attribute WHERE attrelid=to_regclass(%s) AND attnum>0 AND NOT attisdropped',
        (name.lower(),))}
    definitions = translated[translated.index('(')+1:translated.rindex(')')]
    for definition in split(definitions, ','):
        column = definition.split()[0].lower()
        if column not in existing and column not in ('unique', 'constraint'):
            runner.conn.execute(sql.SQL('ALTER TABLE {} ADD COLUMN ' + definition).format(
                sql.Identifier(*name.lower().split('.'))))
    after()


def setup(runner, root=DDL_ROOT):
    paths = sorted(root.glob('*/00_*.sql')) + sorted(root.glob('*/10_*.sql'))
    paths += sorted((root.parent / 'macros').glob('*.sql'))
    paths += sorted((root.parent / 'procedures').glob('*.spl'))
    for path in paths:
        for statement in commands(path.read_text()):
            database = re.match(r'CREATE DATABASE\s+(\w+)', statement, re.I)
            relation = re.match(r'CREATE\s+(?:(?:SET|MULTISET)\s+TABLE|VIEW)\s+([\w.]+)', statement, re.I)
            if database and runner.conn.execute('SELECT 1 FROM pg_namespace WHERE nspname=%s', (database[1].lower(),)).fetchone():
                continue
            if relation and runner.conn.execute('SELECT to_regclass(%s)', (relation[1].lower(),)).fetchone()[0]:
                if re.match(r'CREATE\s+(?:SET|MULTISET)\s+TABLE', statement, re.I):
                    extend_table(runner, statement, relation[1])
                continue
            runner.execute(statement)
            if runner.errorcode:
                raise RuntimeError(f'{path}: Teradata error {runner.errorcode}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ddl', type=Path, default=DDL_ROOT)
    args = parser.parse_args()
    with Runner() as runner:
        setup(runner, args.ddl)


if __name__ == '__main__':
    main()
