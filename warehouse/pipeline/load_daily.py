"""Legacy positional daily billing feed loader."""
import argparse
from datetime import date
from pathlib import Path
import subprocess
import sys

from sf import connect, dbt_env

ROOT = Path(__file__).resolve().parent
GOOD_DATE = date(2026, 11, 9)
STAGE = "@LANDING.LANDING_STAGE/pipeline"
FORMAT = "LANDING.SFX_D1110_PIPELINE_CSV"


def build():
    project = ROOT.parent / "dbt"
    subprocess.run([str(Path(sys.executable).with_name("dbt")), "build",
                    "--project-dir", str(project), "--profiles-dir", str(project),
                    "--select", "stg_billing__usage_daily+"], env=dbt_env(), check=True)


def source_file(day):
    return f"pipeline/{day.isoformat()}.csv"


def load(day, step="load"):
    path = ROOT / "landing" / f"{day.isoformat()}.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    with connect(step, "SFX_D1110_LOAD_WH") as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"""CREATE FILE FORMAT IF NOT EXISTS {FORMAT}
                TYPE=CSV SKIP_HEADER=1 FIELD_OPTIONALLY_ENCLOSED_BY='"'
                EMPTY_FIELD_AS_NULL=TRUE ERROR_ON_COLUMN_COUNT_MISMATCH=FALSE
                COMMENT='sfx-d1110 positional pipeline feed'""")
            cursor.execute(f"PUT 'file://{path}' {STAGE}/ AUTO_COMPRESS=FALSE OVERWRITE=TRUE")
            cursor.execute("DELETE FROM RAW_BILLING.USAGE_DAILY WHERE _SRC_FILE=%s", (source_file(day),))
            cursor.execute(f"""COPY INTO RAW_BILLING.USAGE_DAILY
                (USAGE_DAILY_ID,CUSTOMER_ID,USAGE_DATE,QUANTITY,UNIT_PRICE,AMOUNT,
                 CURRENCY_CODE,CREATED_AT,IS_ACTIVE,_SRC_FILE,_LOADED_AT,
                 USAGE_ID,USAGE_DT,UNITS)
                FROM (SELECT TRY_TO_NUMBER($1),TRY_TO_NUMBER($2),TRY_TO_DATE($5),
                      TRY_TO_NUMBER($6),TRY_TO_DECIMAL($7,12,2),TRY_TO_DECIMAL($8,12,2),
                      $9,TRY_TO_TIMESTAMP_NTZ($10),IFF($11 IN ('Y','N'),$11,NULL),
                      '{source_file(day)}',CURRENT_TIMESTAMP(),TRY_TO_NUMBER($1),
                      TRY_TO_DATE($5),TRY_TO_NUMBER($6)
                      FROM {STAGE}/)
                FILES=('{day.isoformat()}.csv') FILE_FORMAT=(FORMAT_NAME='{FORMAT}')
                ON_ERROR=CONTINUE FORCE=TRUE""")
            columns = [col[0].lower() for col in cursor.description]
            for row in cursor.fetchall():
                result = dict(zip(columns, row))
                print({key: result.get(key) for key in
                       ("file", "status", "rows_parsed", "rows_loaded", "errors_seen", "first_error")}, flush=True)
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
    parser.add_argument("--step", choices=["load", "load_break"], default="load")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    if args.reset:
        if args.date == GOOD_DATE:
            parser.error("reset date must not be the committed good day")
        reset(args.date)
    else:
        load(args.date, args.step)


if __name__ == "__main__":
    main()
