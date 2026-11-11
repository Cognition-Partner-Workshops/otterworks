"""Upload pipe-delimited landing files and invoke the COPY loaders."""
import argparse
import json
from pathlib import Path
import re

import yaml

from sfx_conn import ROOT, connect
from seed_contract import prepare_seed
from teradata_before import prepare_before

SPEC = yaml.safe_load((ROOT / "landing_columns.yml").read_text())


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
        with connect('load', 'copy_teradata_before') as conn, conn.cursor() as cur:
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
    with connect("load", "copy") as conn:
        with conn.cursor() as cur:
            for area in areas:
                for table in SPEC[area]:
                    files = sorted((landing / area / table).glob(
                        f"{args.date}.psv" if args.date else "*.psv"
                    ))
                    if not files:
                        raise FileNotFoundError(f"No landing files for {area}/{table}")
                    for path in files:
                        uri = path.resolve().as_uri().replace("'", "''")
                        cur.execute(
                            f"PUT '{uri}' @LANDING.LANDING_STAGE/{area}/{table}/ "
                            "AUTO_COMPRESS=FALSE OVERWRITE=FALSE"
                        )
                if args.truncate:
                    for table in SPEC[area]:
                        cur.execute(f'TRUNCATE TABLE RAW_{area.upper()}.{table}')
                cur.execute(f"CALL RAW_{area.upper()}.LOAD_{area.upper()}(%s)", (args.date,))
                result = json.loads(cur.fetchone()[0])
                if isinstance(result, dict) and "error" in result:
                    raise RuntimeError(result["error"])
                for row in result:
                    print(f"{area}.{row['table']}: {row['rows_loaded']} rows loaded")


def load_seed(cur, prepared, area='all', truncate=False, stage_prefix='seed'):
    for source_area, table, path, expected in prepared:
        if area != 'all' and source_area != area:
            continue
        relation = f'RAW_{source_area.upper()}.{table}'
        match = re.fullmatch(r'([0-9]{8})\.psv\.gz', path.name)
        if not match:
            raise ValueError(f'Invalid prepared seed filename: {path.name}')
        stage = f'@LANDING.LANDING_STAGE/{stage_prefix}/{source_area}/{table}/{match.group(1)}/'
        uri = path.resolve().as_uri().replace("'", "''")
        cur.execute(f"PUT '{uri}' {stage} AUTO_COMPRESS=FALSE OVERWRITE={'TRUE' if truncate else 'FALSE'}")
        if truncate:
            cur.execute(f'TRUNCATE TABLE {relation}')
        cur.execute(f'COPY INTO {relation} FROM {stage}'
                    f" FILES=('{path.name}')"
                    ' FILE_FORMAT=(FORMAT_NAME=LANDING.PSV_HEADER)'
                    ' MATCH_BY_COLUMN_NAME=CASE_INSENSITIVE'
                    ' INCLUDE_METADATA=(_SRC_FILE=METADATA$FILENAME,_LOADED_AT=METADATA$START_SCAN_TIME)'
                    ' ON_ERROR=ABORT_STATEMENT')
        columns = [c[0].lower() for c in cur.description]
        copied = [dict(zip(columns, row)) for row in cur.fetchall()]
        loaded = sum(int(row.get('rows_loaded', 0)) for row in copied)
        skipped = not copied or all(str(row.get('status', '')).upper() in {
            'LOAD_SKIPPED', 'SKIPPED', 'COPY EXECUTED WITH 0 FILES PROCESSED.'
        } for row in copied)
        cur.execute(f'SELECT COUNT(*) FROM {relation}')
        count = cur.fetchone()[0]
        print(f'{source_area} | {table} | {loaded} | {count}')
        if (loaded != expected and not (not truncate and loaded == 0 and skipped)) or (truncate and count != expected):
            raise RuntimeError(f'{relation}: expected {expected} rows, COPY loaded {loaded}, count={count}')


if __name__ == "__main__":
    main()
