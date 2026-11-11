"""Upload pipe-delimited landing files and invoke the COPY loaders."""
import argparse
import csv
from pathlib import Path
import re

import yaml

from sfx_conn import ROOT, connect
from seed_contract import prepare_seed
from teradata_before import prepare_before

SPEC = yaml.safe_load((ROOT / "landing_columns.yml").read_text())
FIXTURE_SPEC = yaml.safe_load((ROOT / 'fixture_columns.yml').read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--area", choices=["all", *SPEC], default="all")
    parser.add_argument("--landing-dir", type=Path)
    parser.add_argument("--date")
    parser.add_argument("--source", choices=["fixtures", "seed", "teradata-before"], default="fixtures")
    parser.add_argument('--teradata-python', type=Path, default=ROOT.parent / '.venv/bin/python')
    parser.add_argument("--truncate", action="store_true")
    args = parser.parse_args()
    if args.date is not None and not re.fullmatch(r"[0-9]{8}", args.date):
        parser.error("--date must be yyyymmdd")
    if args.source == 'teradata-before':
        if not args.date or args.area not in ('all', 'billing'):
            parser.error('--source teradata-before requires --date and --area billing or all')
        prepared = prepare_before(args.landing_dir or ROOT.parent / 'landing/.teradata-before',
                                  args.date, args.teradata_python)
        with connect('load', 'copy_teradata_before_txn') as conn, conn.cursor() as cur:
            load_seed(cur, prepared, 'billing', truncate=True, stage_prefix='teradata-before')
        return
    if args.source == 'seed':
        if not args.date:
            parser.error('--source seed requires --date yyyymmdd')
        prepared = prepare_seed(args.landing_dir or ROOT.parent / 'landing',
                                ROOT.parent / 'landing/.snowflake', args.date)
        with connect('load', 'copy_seed') as conn, conn.cursor() as cur:
            load_seed(cur, prepared, args.area, args.truncate)
        return
    landing = args.landing_dir or ROOT / "fixtures/landing"
    areas = SPEC if args.area == "all" else [args.area]
    if args.truncate:
        prepared = prepare_fixtures(landing, areas, args.date)
        with connect('load', 'copy_fixtures_txn') as conn, conn.cursor() as cur:
            load_seed(cur, prepared, truncate=True, stage_prefix='fixtures')
        return
    prepared = prepare_fixtures(landing, areas, args.date)
    with connect('load', 'copy') as conn, conn.cursor() as cur:
        load_seed(cur, prepared, stage_prefix=None)


def prepare_fixtures(landing, areas, date=None):
    prepared = []
    for area in areas:
        for table in FIXTURE_SPEC[area]:
            files = sorted((landing / area / table).glob(f'{date}.psv' if date else '*.psv'))
            if not files:
                raise FileNotFoundError(f'No landing files for {area}/{table}')
            for path in files:
                if not re.fullmatch(r'[0-9]{8}\.psv', path.name):
                    raise ValueError(f'Invalid fixture filename: {path.name}')
                with path.open(newline='', encoding='utf-8') as stream:
                    reader = csv.DictReader(stream, delimiter='|')
                    if reader.fieldnames != list(FIXTURE_SPEC[area][table]):
                        raise ValueError(f'Invalid fixture header: {area}/{table}')
                    count = sum(1 for _ in reader)
                prepared.append((area, table, path, count))
    return prepared


def load_seed(cur, prepared, area='all', truncate=False, stage_prefix='seed'):
    uploads, plans = [], []
    labels = {}
    if stage_prefix is not None and not re.fullmatch(r'[a-z0-9-]+', stage_prefix):
        raise ValueError('Invalid stage prefix')
    for source_area, table, path, expected in prepared:
        if area != 'all' and source_area != area:
            continue
        if source_area not in SPEC or table not in SPEC[source_area] or not isinstance(expected, int) or expected < 0:
            raise ValueError('Invalid prepared table or row count')
        relation = f'RAW_{source_area.upper()}.{table}'
        match = re.fullmatch(r'([0-9]{8})\.psv(?:\.gz)?', path.name)
        if not match:
            raise ValueError(f'Invalid prepared seed filename: {path.name}')
        stage = (f'@LANDING.LANDING_STAGE/{source_area}/{table}/' if stage_prefix is None else
                 f'@LANDING.LANDING_STAGE/{stage_prefix}/{source_area}/{table}/{match.group(1)}/')
        uri = path.resolve().as_uri().replace("'", "''")
        uploads.append(f"PUT '{uri}' {stage} AUTO_COMPRESS=FALSE OVERWRITE=TRUE")
        plans.append((relation, stage, path.name, expected))
        labels[relation] = f'{source_area}.{table}' if stage_prefix is None else f'{source_area} | {table}'
    for upload in uploads:
        cur.execute(upload)
    for row in copy_tables(cur, plans, replace=truncate):
        if stage_prefix is None:
            print(f"{labels[row['table']]}: {row['rows_loaded']} rows loaded")
        else:
            print(f"{labels[row['table']]} | {row['rows_loaded']} | {row['count']}")


def copy_tables(cur, plans, replace=False):
    plans = list(plans)
    totals = {}
    for relation, stage, filename, expected in plans:
        if (not re.fullmatch(r'[A-Za-z_][\w$]*(?:\.[A-Za-z_][\w$]*){1,2}', relation)
                or not re.fullmatch(r'@[A-Za-z_][\w./$-]*/', stage)
                or not re.fullmatch(r'[0-9]{8}\.psv(?:\.gz)?', filename)
                or not isinstance(expected, int) or expected < 0):
            raise ValueError('Invalid COPY plan')
        totals[relation] = totals.get(relation, 0) + expected
    if not plans:
        return []
    loaded_totals = dict.fromkeys(totals, 0)
    summary = []
    cur.execute('BEGIN')
    try:
        if replace:
            for relation in totals:
                cur.execute(f'DELETE FROM {relation}')
        for relation, stage, filename, expected in plans:
            if not replace:
                source_file = stage.split('/', 1)[1] + filename
                cur.execute('DELETE FROM IDENTIFIER(%s) WHERE _SRC_FILE=%s', (relation, source_file))
            cur.execute(f'COPY INTO {relation} FROM {stage}'
                        f" FILES=('{filename}')"
                        ' FILE_FORMAT=(FORMAT_NAME=LANDING.PSV_HEADER)'
                        ' MATCH_BY_COLUMN_NAME=CASE_INSENSITIVE'
                        ' INCLUDE_METADATA=(_SRC_FILE=METADATA$FILENAME,_LOADED_AT=METADATA$START_SCAN_TIME)'
                        ' ON_ERROR=ABORT_STATEMENT FORCE=TRUE')
            columns = [c[0].lower() for c in cur.description]
            copied = [dict(zip(columns, row)) for row in cur.fetchall()]
            statuses = [str(row.get('status', '')).upper() for row in copied]
            if any(status != 'LOADED' for status in statuses) or any(int(row.get('errors_seen') or 0) for row in copied):
                raise RuntimeError(f'{relation}: unsuccessful COPY status {statuses}')
            loaded = sum(int(row.get('rows_loaded') or 0) for row in copied)
            if not copied or loaded != expected:
                raise RuntimeError(f'{relation}: expected {expected} rows, COPY loaded {loaded}')
            loaded_totals[relation] += loaded
        for relation, expected in totals.items():
            cur.execute(f'SELECT COUNT(*) FROM {relation}')
            count = cur.fetchone()[0]
            if replace and count != expected:
                raise RuntimeError(f'{relation}: expected {expected} rows, count={count}')
            summary.append(dict(table=relation, rows_loaded=loaded_totals[relation], count=count))
        cur.execute('COMMIT')
    except Exception:
        cur.execute('ROLLBACK')
        raise
    return summary


if __name__ == "__main__":
    main()
