"""Atomic header-mapped daily billing feed loader."""

import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[2]))
from warehouse.run_config import render as _run_render

import argparse
import csv
from datetime import date
from pathlib import Path
import re
import subprocess
import sys

from sf import connect, dbt_env, operation
from telemetry import SafeLoadError

ROOT = Path(__file__).resolve().parent
GOOD_DATE = date(2026, 11, 9)
STAGE = "@LANDING.LANDING_STAGE/pipeline"
FORMAT = _run_render("LANDING.__RUN_DATABASE___PIPELINE_CSV")
REQUIRED = ("USAGE_DAILY_ID", "CUSTOMER_ID", "USAGE_DATE", "QUANTITY", "UNIT_PRICE",
            "AMOUNT", "CURRENCY_CODE", "CREATED_AT", "IS_ACTIVE")
DUCKDB_PATH = ROOT.parents[1] / "migration/dw-exit/.runs/nightly.duckdb"


def cast_expressions(columns, target):
    def number(raw):
        return f"TRY_CAST({raw} AS DECIMAL(38,0))" if target == "duckdb" else f"TRY_TO_NUMBER({raw})"

    customer = columns['CUSTOMER_ID']
    match = (f"regexp_full_match({customer}, 'CUST-[0-9]+')" if target == "duckdb" else
             f"REGEXP_LIKE({customer}, '^CUST-[0-9]+$')")
    expressions = {name: columns[name] for name in REQUIRED}
    for name in ('USAGE_DAILY_ID', 'CUSTOMER_ID', 'QUANTITY'):
        raw = columns[name]
        if name == 'CUSTOMER_ID':
            raw = f"CASE WHEN {match} THEN SUBSTR({customer},6) ELSE {customer} END"
        expressions[name] = number(raw)
    for name in ('UNIT_PRICE', 'AMOUNT'):
        raw = f"REGEXP_REPLACE({columns[name]}, '[^0-9.+-]', ''"
        raw += ", 'g')" if target == "duckdb" else ")"
        expressions[name] = (f"TRY_CAST({raw} AS DECIMAL(12,2))" if target == "duckdb" else
                             f"TRY_TO_DECIMAL({raw},12,2)")
    for name, dtype, function in [('USAGE_DATE', 'DATE', 'TRY_TO_DATE'),
                                  ('CREATED_AT', 'TIMESTAMP', 'TRY_TO_TIMESTAMP_NTZ')]:
        expressions[name] = (f"TRY_CAST({columns[name]} AS {dtype})" if target == 'duckdb' else
                             f"{function}({columns[name]})")
    raw = columns['IS_ACTIVE']
    expressions['IS_ACTIVE'] = f"CASE WHEN {raw} IN ('Y','N') THEN {raw} END"
    return expressions


def validate_casts(cursor, columns, expressions, source, parameters=None):
    queries = []
    for name in REQUIRED:
        raw = columns[name]
        queries.append(f"SELECT '{name}', COUNT(*), MIN({raw}) FROM {source} "
                       f"WHERE {raw} IS NOT NULL AND {raw} <> '' AND ({expressions[name]}) IS NULL "
                       "HAVING COUNT(*) > 0")
    query = ' UNION ALL '.join(queries)
    if parameters is None:
        cursor.execute(query)
    else:
        cursor.execute(query, parameters * len(queries))
    failures = cursor.fetchall()
    if failures:
        details = '; '.join(f"{name}: count={count}, sample={str(sample)[:80]!r}"
                            for name, count, sample in failures)
        raise SafeLoadError("Invalid source casts: " + details)


def load_duckdb(path, day, schema, db_path):
    import duckdb

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    relation = f"{schema}.USAGE_DAILY"
    with duckdb.connect(str(db_path)) as connection:
        connection.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        connection.execute(f"""CREATE TABLE IF NOT EXISTS {relation} (
            USAGE_DAILY_ID BIGINT, CUSTOMER_ID BIGINT, USAGE_DATE DATE,
            QUANTITY INTEGER, UNIT_PRICE DECIMAL(12,2), AMOUNT DECIMAL(12,2),
            CURRENCY_CODE CHAR(3), CREATED_AT TIMESTAMP, IS_ACTIVE CHAR(1),
            _SRC_FILE VARCHAR, _LOADED_AT TIMESTAMP, USAGE_ID BIGINT,
            USAGE_DT DATE, UNITS BIGINT, SUBSCRIPTION_ID BIGINT, USAGE_TYPE VARCHAR(12))""")
        connection.execute("BEGIN")
        try:
            connection.execute(f"DELETE FROM {relation} WHERE _SRC_FILE=?", [source_file(day)])
            columns = {name: name for name in REQUIRED}
            expressions = cast_expressions(columns, 'duckdb')
            projected = ','.join(expressions[name] for name in REQUIRED)
            connection.execute(f"""INSERT INTO {relation}
                (USAGE_DAILY_ID,CUSTOMER_ID,USAGE_DATE,QUANTITY,UNIT_PRICE,AMOUNT,
                 CURRENCY_CODE,CREATED_AT,IS_ACTIVE,_SRC_FILE,_LOADED_AT,
                 USAGE_ID,USAGE_DT,UNITS)
                SELECT {projected},?,CURRENT_TIMESTAMP,
                    {expressions['USAGE_DAILY_ID']},{expressions['USAGE_DATE']},
                    {expressions['QUANTITY']}
                FROM read_csv(?, header=true, all_varchar=true)""",
                [source_file(day), str(path)])
            validate_casts(connection, columns, expressions,
                           'read_csv(?, header=true, all_varchar=true)', [str(path)])
            count = connection.execute(f"SELECT COUNT(*) FROM {relation} WHERE _SRC_FILE=?",
                                       [source_file(day)]).fetchone()[0]
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
    print({"file": source_file(day), "status": "LOADED", "rows_loaded": count}, flush=True)


def build():
    project = ROOT.parent / "dbt"
    subprocess.run([str(Path(sys.executable).with_name("dbt")), "build",
                    "--project-dir", str(project), "--profiles-dir", str(project),
                    "--select", "source:billing.USAGE_DAILY+"], env=dbt_env(), check=True)


def source_file(day):
    return f"pipeline/{day.isoformat()}.csv"


def validate_target(schema, warehouse):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema) or not (
            schema == "RAW_BILLING" or _run_render("__RUN_DATABASE__") in schema):
        raise ValueError(_run_render("schema must be RAW_BILLING or an identifier containing __RUN_DATABASE__"))
    if not re.fullmatch(_run_render(r"__RUN_DATABASE___[A-Za-z0-9_]+"), warehouse):
        raise ValueError(_run_render("warehouse must start with __RUN_DATABASE___"))


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


@operation
def load(day, step="load", schema="RAW_BILLING", warehouse=_run_render("__RUN_DATABASE___LOAD_WH"), no_build=False,
         target="snowflake", db_path=DUCKDB_PATH):
    validate_target(schema, warehouse)
    if target not in ("snowflake", "duckdb"):
        raise ValueError("unknown target")
    if target == "duckdb" and not no_build:
        raise ValueError("DuckDB requires --no-build; dbt sources target Snowflake")
    path = ROOT / "landing" / f"{day.isoformat()}.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    columns = header_columns(path)
    if target == "duckdb":
        return load_duckdb(path, day, schema, db_path)
    expressions = cast_expressions(columns, 'snowflake')
    projected = ','.join(expressions[name] for name in REQUIRED)
    usage_date = expressions['USAGE_DATE']
    with connect(step, warehouse) as connection:
        with connection.cursor() as cursor:
            cursor.execute(_run_render(f"""CREATE FILE FORMAT IF NOT EXISTS {FORMAT}
                TYPE=CSV SKIP_HEADER=1 FIELD_OPTIONALLY_ENCLOSED_BY='"'
                EMPTY_FIELD_AS_NULL=TRUE ERROR_ON_COLUMN_COUNT_MISMATCH=FALSE
                COMMENT='__RUN_TOKEN__ pipeline feed'"""))
            cursor.execute(f"PUT 'file://{path}' {STAGE}/ AUTO_COMPRESS=FALSE OVERWRITE=TRUE")
            cursor.execute("BEGIN")
            try:
                cursor.execute(f"DELETE FROM {schema}.USAGE_DAILY WHERE _SRC_FILE=%s", (source_file(day),))
                cursor.execute(f"""COPY INTO {schema}.USAGE_DAILY
                (USAGE_DAILY_ID,CUSTOMER_ID,USAGE_DATE,QUANTITY,UNIT_PRICE,AMOUNT,
                 CURRENCY_CODE,CREATED_AT,IS_ACTIVE,_SRC_FILE,_LOADED_AT,
                 USAGE_ID,USAGE_DT,UNITS)
                FROM (SELECT {projected},
                      '{source_file(day)}',CURRENT_TIMESTAMP(),{expressions['USAGE_DAILY_ID']},
                      {usage_date},{expressions['QUANTITY']}
                      FROM {STAGE}/)
                FILES=('{day.isoformat()}.csv') FILE_FORMAT=(FORMAT_NAME='{FORMAT}')
                ON_ERROR=ABORT_STATEMENT FORCE=TRUE""")
                result_columns = [col[0].lower() for col in cursor.description]
                results = [dict(zip(result_columns, row)) for row in cursor.fetchall()]
                validate_casts(cursor, columns, expressions,
                               f"{STAGE}/{day.isoformat()}.csv (FILE_FORMAT => '{FORMAT}')")
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
    with connect("reset", _run_render("__RUN_DATABASE___LOAD_WH")) as connection:
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
    parser.add_argument("--warehouse", default=_run_render("__RUN_DATABASE___LOAD_WH"))
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--target", choices=["snowflake", "duckdb"], default="snowflake")
    parser.add_argument("--db-path", type=Path, default=DUCKDB_PATH)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    validate_target(args.schema, args.warehouse)
    if args.reset:
        if args.target == "duckdb":
            parser.error("reset is only supported for Snowflake")
        if args.schema != "RAW_BILLING" or args.warehouse != _run_render("__RUN_DATABASE___LOAD_WH") or args.no_build:
            parser.error("target overrides and --no-build are only supported for loads")
        if args.date == GOOD_DATE:
            parser.error("reset date must not be the committed good day")
        reset(args.date)
    else:
        if args.target == "duckdb":
            load(args.date, args.step, args.schema, args.warehouse, args.no_build,
                 target=args.target, db_path=args.db_path)
        else:
            load(args.date, args.step, args.schema, args.warehouse, args.no_build)


if __name__ == "__main__":
    main()
