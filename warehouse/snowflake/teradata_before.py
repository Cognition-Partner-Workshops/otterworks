"""Export processed emulator billing outputs without translating their logic."""
import argparse
import csv
import gzip
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
TABLES = ('INVOICE_HDR', 'INVOICE_LINE', 'GL_JOURNAL_LINE')
ALIASES = {'INVOICE_HDR_ID': 'INVOICE_ID', 'INVOICE_DATE': 'INVOICE_DT',
           'CURRENCY_CODE': 'CURRENCY_CD', 'GL_JOURNAL_LINE_ID': 'JOURNAL_LINE_ID',
           'JOURNAL_ID': 'INVOICE_ID', 'POSTING_DATE': 'POSTING_DT'}
TABLE_ALIASES = {'INVOICE_HDR': ('INVOICE_HDR_ID', 'INVOICE_DATE', 'CURRENCY_CODE'),
                 'INVOICE_LINE': ('INVOICE_HDR_ID',),
                 'GL_JOURNAL_LINE': ('GL_JOURNAL_LINE_ID', 'JOURNAL_ID', 'POSTING_DATE', 'CURRENCY_CODE')}


def export_tables(connection, destination, date):
    if not re.fullmatch(r'[0-9]{8}', date):
        raise ValueError('Export date must be yyyymmdd')
    result = []
    for table in TABLES:
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT * FROM SFX_BILLING.{table}')
            columns = [c[0].upper() for c in cursor.description]
            aliases = {key: ALIASES[key] for key in TABLE_ALIASES[table]
                       if key not in columns and ALIASES[key] in columns}
            path = Path(destination) / 'billing' / table / f'{date}.psv.gz'
            path.parent.mkdir(parents=True, exist_ok=True)
            count = 0
            with gzip.open(path, 'wt', newline='', encoding='utf-8') as stream:
                writer = csv.DictWriter(stream, fieldnames=[*columns, *aliases], delimiter='|', lineterminator='\n')
                writer.writeheader()
                for values in cursor:
                    row = dict(zip(columns, values))
                    row.update({key: row[value] for key, value in aliases.items()})
                    writer.writerow(row)
                    count += 1
            if not count:
                raise ValueError(f'Processed {table} is empty; run sfx-teradata-run first')
            result.append(('billing', table, str(path), count))
    return result


def prepare_before(destination, date, python):
    import yaml

    process = subprocess.run([str(python), str(Path(__file__).resolve()),
                              '--destination', str(destination), '--date', date],
                             env=os.environ.copy(), capture_output=True, text=True, check=True)
    prepared = [(area, table, Path(path), count) for area, table, path, count in json.loads(process.stdout)]
    if [table for area, table, path, count in prepared] != list(TABLES):
        raise ValueError('Incomplete processed billing export')
    contract = yaml.safe_load((ROOT / 'landing_columns.yml').read_text())
    for area, table, path, count in prepared:
        with gzip.open(path, 'rt', newline='', encoding='utf-8') as stream:
            columns = next(csv.reader(stream, delimiter='|'))
        if not count or not set(columns) <= contract[area][table].keys():
            raise ValueError(f'Invalid processed export contract: {table}')
    return prepared


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--date', required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT.parent / 'teradata'))
    from bteq import Runner
    with Runner() as runner:
        print(json.dumps(export_tables(runner.conn, args.destination, args.date)))


if __name__ == '__main__':
    main()
