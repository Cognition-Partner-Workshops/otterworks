"""Atomic header-mapped daily billing feed loader."""
import argparse
import csv
from datetime import date
from pathlib import Path
import re
import subprocess
import sys

from sf import connect, dbt_env

ROOT = Path(__file__).resolve().parent
GOOD_DATE = date(2026, 11, 9)
STAGE = "@LANDING.LANDING_STAGE/pipeline"
FORMAT = "LANDING.SFX_D1110_PIPELINE_CSV"
REQUIRED = ("USAGE_DAILY_ID", "CUSTOMER_ID", "USAGE_DATE", "QUANTITY", "UNIT_PRICE",
            "AMOUNT", "CURRENCY_CODE", "CREATED_AT", "IS_ACTIVE")


def build():
    project = ROOT.parent / "dbt"
    subprocess.run([str(Path(sys.executable).with_name("dbt")), "build",
                    "--project-dir", str(project), "--profiles-dir", str(project),
                    "--select", "source:billing.USAGE_DAILY+"], env=dbt_env(), check=True)


def source_file(day):
    return f"pipeline/{day.isoformat()}.csv"


def validate_target(schema, warehouse):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema) or not (
            schema == "RAW_BILLING" or "SFX_D1110" in schema):
        raise ValueError("schema must be RAW_BILLING or an identifier containing SFX_D1110")
    if not re.fullmatch(r"SFX_D1110_[A-Za-z0-9_]+", warehouse):
        raise ValueError("warehouse must start with SFX_D1110_")


def header_columns(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        header = next(csv.reader(handle), [])
    missing = [name for name in REQUIRED if name not in header]
    if missing:
        raise ValueError("missing required columns: " + ", ".join(missing))
    if len(header) != len(set(header)):
        raise ValueError("duplicate header columns")
    extras = [name for name in header if name not in REQUIRED]
    if extras:
        print("ignored extra columns: " + ", ".join(extras), flush=True)
    return {name: f"${header.index(name) + 1}" for name in REQUIRED}


def load(day, step="load", schema="RAW_BILLING", warehouse="SFX_D1110_LOAD_WH", no_build=False):
    validate_target(schema, warehouse)
    path = ROOT / "landing" / f"{day.isoformat()}.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    columns = header_columns(path)
    def number(name):
        return f"TRY_TO_NUMBER({columns[name]})"
    def money(name):
        return f"TRY_TO_DECIMAL(REGEXP_REPLACE({columns[name]}, '[^0-9.+-]', ''),12,2)"
    usage_date = f"TRY_TO_DATE({columns['USAGE_DATE']})"
    with connect(step, warehouse) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"""CREATE FILE FORMAT IF NOT EXISTS {FORMAT}
                TYPE=CSV SKIP_HEADER=1 FIELD_OPTIONALLY_ENCLOSED_BY='"'
                EMPTY_FIELD_AS_NULL=TRUE ERROR_ON_COLUMN_COUNT_MISMATCH=FALSE
                COMMENT='sfx-d1110 pipeline feed'""")
            cursor.execute(f"PUT 'file://{path}' {STAGE}/ AUTO_COMPRESS=FALSE OVERWRITE=TRUE")
            cursor.execute("BEGIN")
            try:
                cursor.execute(f"DELETE FROM {schema}.USAGE_DAILY WHERE _SRC_FILE=%s", (source_file(day),))
                cursor.execute(f"""COPY INTO {schema}.USAGE_DAILY
                (USAGE_DAILY_ID,CUSTOMER_ID,USAGE_DATE,QUANTITY,UNIT_PRICE,AMOUNT,
                 CURRENCY_CODE,CREATED_AT,IS_ACTIVE,_SRC_FILE,_LOADED_AT,
                 USAGE_ID,USAGE_DT,UNITS)
                FROM (SELECT {number('USAGE_DAILY_ID')},{number('CUSTOMER_ID')},{usage_date},
                      {number('QUANTITY')},{money('UNIT_PRICE')},{money('AMOUNT')},
                      {columns['CURRENCY_CODE']},TRY_TO_TIMESTAMP_NTZ({columns['CREATED_AT']}),
                      IFF({columns['IS_ACTIVE']} IN ('Y','N'),{columns['IS_ACTIVE']},NULL),
                      '{source_file(day)}',CURRENT_TIMESTAMP(),{number('USAGE_DAILY_ID')},
                      {usage_date},{number('QUANTITY')}
                      FROM {STAGE}/)
                FILES=('{day.isoformat()}.csv') FILE_FORMAT=(FORMAT_NAME='{FORMAT}')
                ON_ERROR=ABORT_STATEMENT FORCE=TRUE""")
                result_columns = [col[0].lower() for col in cursor.description]
                results = [dict(zip(result_columns, row)) for row in cursor.fetchall()]
                cursor.execute("COMMIT")
            except Exception:
                cursor.execute("ROLLBACK")
                raise
            for result in results:
                print({key: result.get(key) for key in
                       ("file", "status", "rows_parsed", "rows_loaded", "errors_seen", "first_error")}, flush=True)
    if not no_build:
        build()


def reset(day):
    with connect("reset", "SFX_D1110_LOAD_WH") as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM RAW_BILLING.USAGE_DAILY WHERE _SRC_FILE=%s", (source_file(day),))
            print("reset rows_deleted:", cursor.rowcount, flush=True)
            cursor.execute(f"REMOVE {STAGE}/{day.isoformat()}.csv")
    (ROOT / "landing" / f"{day.isoformat()}.csv").unlink(missing_ok=True)
    build()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    parser.add_argument("--step", choices=["load", "load_break", "backfill"], default="load")
    parser.add_argument("--schema", default="RAW_BILLING")
    parser.add_argument("--warehouse", default="SFX_D1110_LOAD_WH")
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    validate_target(args.schema, args.warehouse)
    if args.reset:
        if args.schema != "RAW_BILLING" or args.warehouse != "SFX_D1110_LOAD_WH" or args.no_build:
            parser.error("target overrides and --no-build are only supported for loads")
        if args.date == GOOD_DATE:
            parser.error("reset date must not be the committed good day")
        reset(args.date)
    else:
        load(args.date, args.step, args.schema, args.warehouse, args.no_build)


if __name__ == "__main__":
    main()
