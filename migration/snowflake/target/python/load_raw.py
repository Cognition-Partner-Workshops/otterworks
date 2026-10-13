"""Load generated CSV extracts into the run-specific RAW schema."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from ubw_snowflake import dbt_connection, object_prefix, validate_run

STG_TABLES = (
    "STG_BILLING_TENANTS",
    "STG_BILLING_PLANS",
    "STG_BILLING_SUBSCRIPTIONS",
    "STG_BILLING_USAGE_EVENTS",
    "STG_BILLING_INVOICES",
    "STG_AUTH_USERS",
    "STG_AUTH_WORKSPACE_MEMBERS",
    "STG_DOCUMENTS",
    "STG_DOCUMENT_VERSIONS",
    "STG_FILES",
    "STG_FILE_VERSIONS",
    "STG_COLLAB_EVENTS",
    "STG_AUDIT_EVENTS",
    "STG_ANALYTICS_EVENTS",
)
HERE = Path(__file__).resolve().parent
DEFAULT_EXTRACTS = HERE.parents[1] / "source" / "out" / "extracts"


def load(run: str, extracts: Path) -> None:
    validate_run(run)
    missing = [table for table in STG_TABLES if not (extracts / f"{table.lower()}.csv").is_file()]
    if missing:
        raise FileNotFoundError(
            f"extract directory {extracts} is missing CSV files for: {', '.join(missing)}"
        )

    prefix = object_prefix(run)
    qualified_stage = f"{prefix}.RAW.EXTRACTS"
    qualified_format = f"{prefix}.RAW.EXTRACT_CSV"
    log_table = f"{prefix}.OPS.ETL_RUN_LOG"
    with dbt_connection(run) as connection, connection.cursor() as cursor:
        cursor.execute(f"CREATE STAGE IF NOT EXISTS {qualified_stage} DIRECTORY = (ENABLE = TRUE)")
        cursor.execute(
            f"CREATE OR REPLACE FILE FORMAT {qualified_format} "
            "TYPE = CSV PARSE_HEADER = TRUE "
            "FIELD_OPTIONALLY_ENCLOSED_BY = '\"' SKIP_BLANK_LINES = TRUE"
        )
        cursor.execute(
            f"""CREATE TABLE IF NOT EXISTS {log_table} (
                RUN_TOKEN VARCHAR,
                BUSINESS_DATE DATE,
                JOB_NAME VARCHAR,
                STEP_NAME VARCHAR,
                STATUS VARCHAR,
                ROW_COUNT NUMBER,
                MESSAGE VARCHAR,
                STARTED_AT TIMESTAMP_NTZ,
                COMPLETED_AT TIMESTAMP_NTZ,
                CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )"""
        )
        for table in STG_TABLES:
            extract = (extracts / f"{table.lower()}.csv").resolve()
            started = datetime.now(UTC).replace(tzinfo=None)
            status = "SUCCESS"
            row_count = 0
            message = ""
            try:
                cursor.execute(
                    f"PUT file://{extract.as_posix()} "
                    f"@{qualified_stage}/{table.lower()} AUTO_COMPRESS = TRUE OVERWRITE = TRUE"
                )
                cursor.execute(
                    f"""CREATE OR REPLACE TABLE {prefix}.RAW.{table}
                    USING TEMPLATE (
                        SELECT ARRAY_AGG(OBJECT_CONSTRUCT(*))
                        FROM TABLE(INFER_SCHEMA(
                            LOCATION => '@{qualified_stage}/{table.lower()}',
                            FILE_FORMAT => '{qualified_format}'
                        ))
                    )"""
                )
                cursor.execute(
                    f"""COPY INTO {prefix}.RAW.{table}
                    FROM @{qualified_stage}/{table.lower()}
                    FILE_FORMAT = (FORMAT_NAME = '{qualified_format}')
                    MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE"""
                )
                result = cursor.fetchone()
                row_count = int(result[3]) if result and len(result) > 3 else 0
                print(f"{table}: {row_count} rows loaded")
            except Exception as error:
                status = "FAILED"
                message = str(error)[:2000]
                raise
            finally:
                completed = datetime.now(UTC).replace(tzinfo=None)
                cursor.execute(
                    f"""INSERT INTO {log_table} (
                        RUN_TOKEN, BUSINESS_DATE, JOB_NAME, STEP_NAME, STATUS,
                        ROW_COUNT, MESSAGE, STARTED_AT, COMPLETED_AT
                    ) VALUES (%s, NULL, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        run,
                        "UBW_LOAD_RAW",
                        table,
                        status,
                        row_count,
                        message,
                        started,
                        completed,
                    ),
                )
        cursor.execute(f"ALTER STAGE {qualified_stage} REFRESH")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--extracts", type=Path)
    args = parser.parse_args()
    try:
        validate_run(args.run)
        extracts = args.extracts or Path(os.environ.get("UBW_EXTRACTS_DIR", str(DEFAULT_EXTRACTS)))
        load(args.run, extracts)
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
