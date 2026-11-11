import argparse
import csv
import os
import re
from dataclasses import dataclass
from pathlib import Path

from psycopg import sql

from .runner import Runner


CONTROL_ROOT = Path(__file__).resolve().parents[1] / 'load'


@dataclass(frozen=True)
class Control:
    target: str
    columns: tuple
    path: Path
    delimiter: str


def parse_control(path, variables=None):
    values = {**os.environ, **(variables or {})}
    text = re.sub(r'\$\{(\w+)\}', lambda m: values.get(m[1], m[0]), Path(path).read_text())
    insert = re.search(r'INSERT\s+INTO\s+([\w.]+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)', text, re.I)
    if not insert:
        raise ValueError('Control file must contain an INSERT with named columns and values')
    target = insert[1].lower()
    if not re.fullmatch(r'sfx_(billing|documents|users|audit)\.stg_\w+', target):
        raise ValueError('Load target must be a staging table')
    columns = tuple(c.strip().lower() for c in insert[2].split(','))
    params = tuple(c.strip().lstrip(':').lower() for c in insert[3].split(','))
    if columns != params:
        raise ValueError('INSERT columns and input parameters must have the same order')
    if Path(path).suffix == '.fl':
        define = re.search(r'\bDEFINE\s+(.*?)\bFILE\s*=\s*([^;]+);', text, re.I | re.S)
        names = tuple(n.lower() for n in re.findall(r'(\w+)\s*\(\s*VARCHAR\s*\(\d+\)\s*\)', define[1], re.I)) if define else ()
        delimiter = re.search(r'SET\s+RECORD\s+VARTEXT\s+[\'"](.?)[\'"]', text, re.I)
        filename = define[2].strip().strip("'\"") if define else ''
        loading = re.search(r'BEGIN\s+LOADING\s+([\w.]+)', text, re.I)
        if not loading or loading[1].lower() != target or not re.search(r'END\s+LOADING', text, re.I):
            raise ValueError('Invalid BEGIN/END LOADING target')
    elif Path(path).suffix == '.tpt':
        schema = re.search(r'DEFINE\s+SCHEMA\s+\w+\s*\((.*?)\)\s*;', text, re.I | re.S)
        names = tuple(n.lower() for n in re.findall(r'(\w+)\s+VARCHAR\s*\(\d+\)', schema[1], re.I)) if schema else ()
        attributes = {k.lower(): v for k, v in re.findall(r"VARCHAR\s+(\w+)\s*=\s*'([^']*)'", text, re.I)}
        delimiter = re.search(r"TextDelimiter\s*=\s*'(.?)'", text, re.I)
        filename = str(Path(attributes.get('directorypath', '')) / attributes.get('filename', ''))
        if attributes.get('targettable', '').lower() != target:
            raise ValueError('LOAD operator target differs from INSERT')
    else:
        raise ValueError('Expected a .fl or .tpt control file')
    if names != columns or not delimiter or len(delimiter[1]) != 1 or not filename or '${' in filename:
        raise ValueError('Invalid schema, delimiter, or unresolved file path')
    return Control(target, columns, Path(filename), delimiter[1])


def load_control(runner, path, variables=None):
    control = parse_control(path, variables)
    metadata = runner.columns(control.target)
    actual = tuple(name for name, _ in metadata)
    if control.columns != actual:
        raise ValueError('Control file column order differs from the target DDL')
    target = sql.Identifier(*control.target.split('.'))
    count = 0
    with control.path.open(newline='', encoding='utf-8') as handle, runner.conn.transaction():
        runner.conn.execute(sql.SQL('TRUNCATE TABLE {}').format(target))
        statement = sql.SQL('COPY {} ({}) FROM STDIN').format(target, sql.SQL(',').join(map(sql.Identifier, control.columns)))
        with runner.conn.cursor().copy(statement) as copy:
            for row in csv.reader(handle, delimiter=control.delimiter):
                if len(row) != len(control.columns):
                    raise ValueError(f'{control.path}: row {count + 1} has {len(row)} fields; expected {len(control.columns)}')
                copy.write_row([None if value == '' and not kind.startswith(('character', 'text')) else value
                                for value, (_, kind) in zip(row, metadata)])
                count += 1
    return count


def load_all(runner, landing, business_date='20261109', root=CONTROL_ROOT):
    result = {}
    variables = {'LANDING_DIR': str(Path(landing).resolve()), 'BUSINESS_DATE': business_date}
    for path in sorted(root.glob('*/*')):
        if path.suffix in ('.fl', '.tpt'):
            count = load_control(runner, path, variables)
            result[parse_control(path, variables).target] = count
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--landing', type=Path, default=Path('warehouse/landing'))
    parser.add_argument('--business-date', default='20261109')
    parser.add_argument('--controls', type=Path, default=CONTROL_ROOT)
    args = parser.parse_args()
    with Runner() as runner:
        counts = load_all(runner, args.landing, args.business_date, args.controls)
    print(f'Loaded {sum(counts.values())} rows into {len(counts)} staging tables')


if __name__ == '__main__':
    main()
