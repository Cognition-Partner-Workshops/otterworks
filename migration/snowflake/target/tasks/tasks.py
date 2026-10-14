"""Create and manage the Snowflake task graph for a migration run."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from string import Template
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "python"))

snowflake_helpers = importlib.import_module("ubw_snowflake")
dbt_connection = snowflake_helpers.dbt_connection
object_prefix = snowflake_helpers.object_prefix
validate_run = snowflake_helpers.validate_run

FALLBACK_NIGHTLY_SCHEDULE = "USING CRON 0 2 * * * America/New_York"
DIM_MODELS = (
    "dim_date",
    "dim_tenant",
    "dim_plan",
    "dim_user",
    "dim_workspace",
    "dim_document",
    "dim_file",
)
MODEL_NAMES = (
    *DIM_MODELS,
    "rollup_storage_daily",
    "rollup_usage_events",
    "rollup_seats",
    "rollup_collab_daily",
    "rollup_audit",
    "rollup_document_status",
    "rollup_retention",
    "build_invoice_lines",
    "rate_overage",
    "apply_plan_limits",
    "build_capacity_forecast_input",
    "build_mart_tenant_usage",
    "build_mart_plan_seat_summary",
    "build_mart_overage",
    "build_mart_retention",
    "build_mart_audit",
    "log_run",
    "purge_expired",
)
TASK_FILES = (
    ("nightly.sql", "UBW_NIGHTLY_LOAD"),
    ("load_raw.sql", "UBW_LOAD_RAW"),
    ("build_dims.sql", "UBW_BUILD_DIMS"),
    ("rollup_storage_daily.sql", "UBW_ROLLUP_STORAGE_DAILY"),
    ("build_facts.sql", "UBW_BUILD_FACTS"),
    ("build_marts.sql", "UBW_BUILD_MARTS"),
    ("log_run.sql", "UBW_LOG_RUN"),
    ("hourly_audit.sql", "UBW_HOURLY_AUDIT"),
    ("weekly_retention.sql", "UBW_WEEKLY_RETENTION"),
    ("monthly_overage.sql", "UBW_MONTHLY_OVERAGE"),
    ("weekly_capacity_forecast.sql", "UBW_WEEKLY_CAPACITY_FORECAST"),
)
STANDALONE_TASKS = (
    "UBW_HOURLY_AUDIT",
    "UBW_WEEKLY_RETENTION",
    "UBW_MONTHLY_OVERAGE",
    "UBW_WEEKLY_CAPACITY_FORECAST",
)
STANDALONE_SCHEDULES = {
    "UBW_HOURLY_AUDIT": "USING CRON 5 * * * * America/New_York",
    "UBW_WEEKLY_RETENTION": "USING CRON 0 3 * * SUN America/New_York",
    "UBW_MONTHLY_OVERAGE": "USING CRON 0 4 1 * * America/New_York",
    "UBW_WEEKLY_CAPACITY_FORECAST": "USING CRON 15 6 * * MON America/New_York",
}


def agent_schedule(value: dict[str, Any]) -> str | None:
    """Translate a SQL Agent daily schedule (freq + active_start_time HHMMSS) to CRON."""
    if str(value.get("freq", "")).lower() != "daily" or "active_start_time" not in value:
        return None
    start = f"{int(value['active_start_time']):06d}"
    return f"USING CRON {int(start[2:4])} {int(start[0:2])} * * * America/New_York"


def schedule_value(value: Any) -> str | None:
    if isinstance(value, dict):
        translated = agent_schedule(value)
        if translated:
            return translated
        for key in ("cron", "cron_expression", "expression", "schedule"):
            if key in value:
                result = schedule_value(value[key])
                if result:
                    return result
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    schedule = value.strip()
    if schedule.upper().startswith("USING CRON "):
        return schedule
    if schedule.upper().startswith("CRON "):
        return "USING " + schedule
    if len(schedule.split()) == 5:
        return f"USING CRON {schedule} America/New_York"
    return None


def find_nightly_schedule(value: Any) -> str | None:
    if isinstance(value, dict):
        names = [
            str(value.get(key, "")).strip().lower().replace("_", " ")
            for key in ("name", "job", "job_name")
        ]
        if any(name in {"ubw nightly load", "nightly load"} for name in names):
            for key in ("schedule", "cron", "cron_expression"):
                found = schedule_value(value.get(key))
                if found:
                    return found
        for nested in value.values():
            found = find_nightly_schedule(nested)
            if found:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = find_nightly_schedule(nested)
            if found:
                return found
    return None


def nightly_schedule() -> str:
    jobs_path = ROOT / "migration" / "snowflake" / "source" / "agent" / "jobs.yaml"
    if jobs_path.is_file():
        schedule = find_nightly_schedule(yaml.safe_load(jobs_path.read_text(encoding="utf-8")))
        if schedule:
            return schedule
    # This schedule is used only until the source job catalog is available.
    return FALLBACK_NIGHTLY_SCHEDULE


def runner_sql(prefix: str, run: str) -> str:
    branches: list[str] = []
    for model in MODEL_NAMES:
        branches.extend(
            [
                f"            WHEN '{model}' THEN",
                "                IF (EXISTS (",
                f"                    SELECT 1 FROM DIRECTORY(@{prefix}.OPS.DBT_MODELS)",
                f"                    WHERE RELATIVE_PATH = '{model}.sql'",
                "                )) THEN",
                f"                    EXECUTE IMMEDIATE FROM @{prefix}.OPS.DBT_MODELS/{model}.sql;",
                "                    INSERT INTO "
                f"{prefix}.OPS.ETL_RUN_LOG (RUN_TOKEN, BUSINESS_DATE, JOB_NAME, "
                "STEP_NAME, STATUS, ROW_COUNT, MESSAGE, STARTED_AT, COMPLETED_AT)",
                f"                    VALUES ('{run}', CURRENT_DATE(), 'UBW_TASK', "
                f"'{model}', 'SUCCESS', 0, '', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP());",
                "                ELSE",
                "                    INSERT INTO "
                f"{prefix}.OPS.ETL_RUN_LOG (RUN_TOKEN, BUSINESS_DATE, JOB_NAME, "
                "STEP_NAME, STATUS, ROW_COUNT, MESSAGE, STARTED_AT, COMPLETED_AT)",
                f"                    VALUES ('{run}', CURRENT_DATE(), 'UBW_TASK', "
                f"'{model}', 'SKIPPED', 0, 'No published SQL file is available', "
                "CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP());",
                "                END IF;",
            ]
        )
    path = HERE / "model_runner.sql"
    return Template(path.read_text(encoding="utf-8")).substitute(
        PREFIX=prefix, RUN=run, MODEL_BRANCHES="\n".join(branches)
    )


def create(run: str) -> None:
    prefix = object_prefix(run)
    values = {"PREFIX": prefix, "RUN": run}
    with dbt_connection(run) as connection, connection.cursor() as cursor:
        cursor.execute(  # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
            f"CREATE STAGE IF NOT EXISTS {prefix}.OPS.DBT_MODELS DIRECTORY = (ENABLE = TRUE)"
        )
        print(f"STAGE             {prefix}.OPS.DBT_MODELS (created or already present)")
        sql = Template((HERE / "etl_run_log.sql").read_text(encoding="utf-8")).substitute(values)
        cursor.execute(sql)
        print(f"TABLE             {prefix}.OPS.ETL_RUN_LOG")
        cursor.execute(runner_sql(prefix, run))
        print(f"PROCEDURE         {prefix}.OPS.UBW_RUN_MODELS")
        try:
            sql = Template((HERE / "task_history.sql").read_text(encoding="utf-8")).substitute(
                values
            )
            cursor.execute(sql)
            print(f"VIEW              {prefix}.OPS.TASK_HISTORY")
        except Exception as error:
            print(f"TASK_HISTORY view was not created: {error}", file=sys.stderr)
        for filename, name in TASK_FILES:
            task_values = values.copy()
            if name == "UBW_NIGHTLY_LOAD":
                task_values["SCHEDULE"] = nightly_schedule()
            elif name in STANDALONE_SCHEDULES:
                task_values["SCHEDULE"] = STANDALONE_SCHEDULES[name]
            sql = Template((HERE / filename).read_text(encoding="utf-8")).substitute(task_values)
            cursor.execute(sql)
            print(f"TASK              {prefix}.OPS.{name} (suspended)")


def manage(run: str, operation: str) -> None:
    prefix = object_prefix(run)
    with dbt_connection(run) as connection, connection.cursor() as cursor:
        if operation == "resume":
            cursor.execute(f"LIST @{prefix}.OPS.DBT_MODELS PATTERN = '.*PINNED_BUSINESS_DATE.*'")
            if cursor.fetchall():
                raise RuntimeError(
                    "models are pinned to a business date; "
                    "run publish without --business-date before resume"
                )
            cursor.execute(f"SHOW TASKS IN SCHEMA {prefix}.OPS")
            task_columns = {
                (column.name if hasattr(column, "name") else column[0]).lower(): index
                for index, column in enumerate(cursor.description)
            }
            task_names = {str(row[task_columns["name"]]).upper() for row in cursor.fetchall()}
            for name in STANDALONE_TASKS:
                if name not in task_names:
                    print(f"ABSENT            {prefix}.OPS.{name}")
                    continue
                cursor.execute(
                    f"ALTER TASK {prefix}.OPS.{name} RESUME"
                )  # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
                print(f"RESUMED           {prefix}.OPS.{name}")
            root_name = f"{prefix}.OPS.UBW_NIGHTLY_LOAD"
            cursor.execute("SELECT SYSTEM$TASK_DEPENDENTS_ENABLE(%s)", (root_name,))
            print(f"RESUMED GRAPH     {root_name}")
        else:
            for _, name in reversed(TASK_FILES):
                cursor.execute(
                    f"ALTER TASK {prefix}.OPS.{name} SUSPEND"
                )  # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
                print(f"SUSPENDED         {prefix}.OPS.{name}")


def model_materializations(manifest_path: Path) -> dict[str, str]:
    if not manifest_path.is_file():
        return {}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        node["name"]: node.get("config", {}).get("materialized", "table")
        for node in manifest.get("nodes", {}).values()
        if node.get("resource_type") == "model"
    }


def model_statement(
    prefix: str, model: str, compiled: str, materialized: str, business_date_sql: str
) -> str:
    """Build the SQL a task executes for one model.

    Incremental models replace only the business dates the compiled query produces, the way the
    legacy procedures DELETE then INSERT one @business_date.
    """
    target = f"{prefix}.MARTS.{model.upper()}"
    if materialized != "incremental":
        return f"CREATE OR REPLACE TABLE {target} AS\n{compiled}\n"
    batch = f"{prefix}.MARTS.{model.upper()}__TASK_BATCH"
    return (
        f"CREATE OR REPLACE TEMPORARY TABLE {batch} AS\n{compiled};\n"
        f"DELETE FROM {target} WHERE business_date = {business_date_sql} "
        f"OR business_date IN (SELECT business_date FROM {batch});\n"
        f"INSERT INTO {target} SELECT * FROM {batch};\n"
    )


def business_date_sql(business_date: str | None) -> str:
    # Mirrors target/dbt/macros/business_date.sql.
    if business_date:
        return f"'{date.fromisoformat(business_date).isoformat()}'::date"
    return "dateadd(day, -1, current_date())"


def business_date_vars(business_date: str | None) -> list[str]:
    """Pin the published models to one business date; by default they build yesterday."""
    if not business_date:
        return []
    return ["--vars", f"{{business_date: {date.fromisoformat(business_date).isoformat()}}}"]


def publish(run: str, business_date: str | None = None) -> None:
    prefix = object_prefix(run)
    environment = os.environ.copy()
    environment["UBW_RUN"] = run
    wrapper = HERE.parent / "python" / "dbt_env.py"
    subprocess.run(
        [sys.executable, str(wrapper), "--", "compile", *business_date_vars(business_date)],
        check=True,
        cwd=ROOT,
        env=environment,
    )
    dbt_target = HERE.parent / "dbt" / "target"
    compiled_dir = dbt_target / "compiled" / "ubw" / "models" / "marts"
    upload_dir = dbt_target / "task_models"
    upload_dir.mkdir(parents=True, exist_ok=True)
    materializations = model_materializations(dbt_target / "manifest.json")
    published = [model for model in MODEL_NAMES if (compiled_dir / f"{model}.sql").is_file()]
    missing = [model for model in DIM_MODELS if model not in published]
    if missing:
        raise FileNotFoundError(f"dbt did not compile models: {', '.join(missing)}")
    with dbt_connection(run) as connection, connection.cursor() as cursor:
        cursor.execute(  # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
            f"CREATE STAGE IF NOT EXISTS {prefix}.OPS.DBT_MODELS DIRECTORY = (ENABLE = TRUE)"
        )
        for model in published:
            compiled = (compiled_dir / f"{model}.sql").read_text(encoding="utf-8").rstrip()
            destination = upload_dir / f"{model}.sql"
            destination.write_text(
                model_statement(
                    prefix,
                    model,
                    compiled,
                    materializations.get(model, "table"),
                    business_date_sql(business_date),
                ),
                encoding="utf-8",
            )
            cursor.execute(
                f"PUT file://{destination.resolve().as_posix()} "
                f"@{prefix}.OPS.DBT_MODELS AUTO_COMPRESS = FALSE OVERWRITE = TRUE"
            )
            print(f"PUBLISHED         {model} -> {prefix}.OPS.DBT_MODELS/{model}.sql")
        if business_date:
            marker_path = upload_dir / "PINNED_BUSINESS_DATE"
            marker_path.write_text(business_date, encoding="utf-8")
            cursor.execute(
                f"PUT file://{marker_path.resolve().as_posix()} "
                f"@{prefix}.OPS.DBT_MODELS AUTO_COMPRESS = FALSE OVERWRITE = TRUE"
            )
            print(
                "WARNING           Models are pinned to a business date; republish without "
                "--business-date before resuming"
            )
        else:
            cursor.execute(f"REMOVE @{prefix}.OPS.DBT_MODELS/PINNED_BUSINESS_DATE")
        cursor.execute(
            f"ALTER STAGE {prefix}.OPS.DBT_MODELS REFRESH"
        )  # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("operation", choices=("create", "resume", "suspend", "publish"))
    parser.add_argument("--business-date", help="publish: pin models to YYYY-MM-DD")
    args = parser.parse_args()
    try:
        validate_run(args.run)
        if args.operation == "create":
            create(args.run)
        elif args.operation == "publish":
            publish(args.run, args.business_date)
        else:
            manage(args.run, args.operation)
    except (FileNotFoundError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
