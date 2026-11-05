from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import snowflake.connector
import psycopg2
from cryptography.hazmat.primitives import serialization
from dbt.cli.main import dbtRunner

from source import TABLES, export as source_export

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "attribution"))
import sf_attribution as sf  # noqa: E402

WORKLOADS = ("doc_usage_dashboard", "doc_search_api", "churn_model")
MODELS = dict(
    zip(WORKLOADS, ("account_storage_usage", "top_search_items", "weekly_churn_scores"))
)
SESSION_URL = "https://partner-workshops.devinenterprise.com/sessions/6b490330916b45c1a3532b15a809de89"
STAGE = "POSTGRES_EXPORTS"
ARTIFACTS = Path.home() / ".local" / "share" / "otterworks-pipeline"


def parameters(workload, phase="dev"):
    ep = sf.endpoint(sf.workload_csids(workload)[0])
    params = sf.connection_params(
        ep,
        phase=phase,
        account=os.environ["SNOWFLAKE_EXT_ACCOUNT"],
        private_key_file="in-memory-only",
        commit=sf.resolve_commit(repo=str(ROOT.parent.parent)),
        run_id=sf.make_run_id(workload, phase),
        session_url=os.environ.get("DEVIN_SESSION_URL", SESSION_URL)
        if phase == "dev"
        else None,
        role="DEVIN_EXT_ROLE",
    )
    params.pop("private_key_file")
    key = serialization.load_pem_private_key(
        os.environ["SNOWFLAKE_EXT_PRIVATE_KEY"].encode(), password=None
    )
    params["private_key"] = key.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    params["user"] = os.environ["SNOWFLAKE_EXT_USER"]
    params["session_parameters"]["TIMEZONE"] = "UTC"
    return params


def bootstrap_sql(workload):
    db = sf.database_name(workload)
    comment = sf.sql_string(
        sf.external_comment(workload=workload, purpose="Postgres hourly pipeline")
    )
    yield f"CREATE STAGE IF NOT EXISTS {db}.RAW.{STAGE} FILE_FORMAT=(TYPE=JSON) COMMENT={comment}"
    yield f"CREATE TABLE IF NOT EXISTS {db}.RAW.PIPELINE_EXPORTS (PAYLOAD VARIANT) COMMENT={comment}"
    for name, (_, _, columns) in TABLES.items():
        target = f"{db}.RAW.{name}"
        yield f"CREATE TABLE IF NOT EXISTS {target} ({', '.join(k + ' ' + v for k, v in columns.items())}) COMMENT={comment}"
        for column, datatype in {
            **columns,
            "_snapshot_date": "DATE",
            "_exported_at": "TIMESTAMP_NTZ",
            "_row_hash": "VARCHAR(64)",
        }.items():
            yield f"ALTER TABLE {target} ADD COLUMN IF NOT EXISTS {column} {datatype}"
        yield f"COMMENT ON TABLE {target} IS {comment}"


def copy_sql(workload, force=False):
    db = sf.database_name(workload)
    return f"COPY INTO {db}.RAW.PIPELINE_EXPORTS FROM @{db}.RAW.{STAGE} FILE_FORMAT=(TYPE=JSON) ON_ERROR=ABORT_STATEMENT FORCE={str(force).upper()}"


def raw_merge_sql(workload):
    db = sf.database_name(workload)
    for name, (_, key, columns) in TABLES.items():
        target = f"{db}.RAW.{name}"
        values = [f"r.value:{c}::{t} as {c}" for c, t in columns.items()]
        values += [
            "p.payload:snapshot_date::date as _snapshot_date",
            "p.payload:exported_at::timestamp_ntz as _exported_at",
            "sha2(to_json(r.value),256) as _row_hash",
        ]
        names = [*columns, "_snapshot_date", "_exported_at", "_row_hash"]
        source = f"""SELECT {", ".join(values)} FROM {db}.RAW.PIPELINE_EXPORTS p,
LATERAL FLATTEN(input=>p.payload:tables:{name}) r
QUALIFY ROW_NUMBER() OVER(PARTITION BY _snapshot_date,{key} ORDER BY _exported_at DESC,_row_hash DESC)=1"""
        yield f"""MERGE INTO {target} t USING ({source}) s
ON t._snapshot_date=s._snapshot_date AND t.{key}=s.{key}
WHEN MATCHED AND (s._exported_at>t._exported_at OR (s._exported_at=t._exported_at AND s._row_hash>t._row_hash))
THEN UPDATE SET {", ".join(c + "=s." + c for c in names)}
WHEN NOT MATCHED THEN INSERT ({", ".join(names)}) VALUES ({", ".join("s." + c for c in names)})"""


def dbt(workload, command, select=None):
    os.environ.setdefault("PIPELINE_DBT_TARGET", str(ARTIFACTS / "dbt-target"))
    params = parameters(workload)
    os.environ["PIPELINE_DATABASE"] = sf.database_name(workload)
    os.environ["PIPELINE_QUERY_TAG"] = params["session_parameters"]["QUERY_TAG"]
    original = snowflake.connector.connect

    def attributed_connect(**kwargs):
        for key in (
            "password",
            "private_key_file",
            "private_key_file_pwd",
            "authenticator",
        ):
            kwargs.pop(key, None)
        # dbt's default application='dbt' must not replace Devin_Demo (unregistered).
        kwargs.update(params)
        return original(**kwargs)

    arguments = [
        command,
        "--project-dir",
        str(ROOT),
        "--profiles-dir",
        str(ROOT),
        "--log-path",
        os.environ.get("PIPELINE_DBT_LOG", str(ARTIFACTS / "dbt-logs")),
        "--target-path",
        os.environ["PIPELINE_DBT_TARGET"],
    ]
    if select:
        arguments += ["--select", select]
    with patch("snowflake.connector.connect", attributed_connect):
        result = dbtRunner().invoke(arguments)
    if not result.success:
        raise RuntimeError(
            f"dbt {command} failed: {result.exception or 'see dbt output'}"
        )
    return result


def validate_bundle(bundle):
    content = bundle.read_text().strip()
    payload = json.loads(content)
    digest = hashlib.sha256(content.encode()).hexdigest()
    if bundle.name != f"snapshot_{digest}.json":
        raise ValueError("snapshot filename must match its SHA256")
    if set(payload["tables"]) != set(TABLES):
        raise ValueError("incomplete source snapshot")
    date.fromisoformat(payload["snapshot_date"])
    if datetime.fromisoformat(payload["exported_at"]).utcoffset() is None:
        raise ValueError("exported_at must include its UTC offset")
    for table, (_, _, columns) in TABLES.items():
        if not isinstance(payload["tables"][table], list):
            raise ValueError(f"{table} must contain an array of records")
        for row in payload["tables"][table]:
            if set(row) != set(columns):
                raise ValueError(f"{table} has unexpected or missing columns")
    return payload


def publish(bundle, phase="dev"):
    payload = validate_bundle(bundle)
    for workload in WORKLOADS:
        with (
            closing(snowflake.connector.connect(**parameters(workload, phase))) as conn,
            conn.cursor() as cur,
        ):
            for statement in bootstrap_sql(workload):
                cur.execute(statement)
            cur.execute(
                f"PUT {sf.sql_string('file://' + str(bundle.resolve()))} @{sf.database_name(workload)}.RAW.{STAGE} AUTO_COMPRESS=TRUE OVERWRITE=FALSE"
            )
            print(f"{workload}: published complete snapshot {payload['snapshot_date']}")


def export_source():
    now = datetime.now(timezone.utc)
    with closing(psycopg2.connect(os.environ["POSTGRES_DSN"])) as conn:
        bundle = source_export(conn, ARTIFACTS / "exports", now.date(), now)
    publish(bundle, phase="runtime")


def next_export_at(now):
    return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)


def hourly_export():
    while datetime.now(timezone.utc).date() <= date.fromisoformat(sf.EXPIRES):
        try:
            export_source()
            print("Hourly source snapshot published", flush=True)
        except Exception as exc:
            print(f"Hourly source export failed: {type(exc).__name__}", flush=True)
        due = next_export_at(datetime.now(timezone.utc))
        print(f"Next source export: {due.isoformat()}", flush=True)
        time.sleep(max(1, (due - datetime.now(timezone.utc)).total_seconds()))


def load(force=False):
    for workload in WORKLOADS:
        with (
            closing(snowflake.connector.connect(**parameters(workload))) as conn,
            conn.cursor() as cur,
        ):
            cur.execute(copy_sql(workload, force))
            for statement in raw_merge_sql(workload):
                cur.execute(statement)
            print(f"{workload}: raw tables reconciled")


def procedure_name(workload):
    return f"{sf.database_name(workload)}.APP.REFRESH_{MODELS[workload].upper()}"


def report_dml(workload, node, model_sql):
    db = sf.database_name(workload)
    relation = f"{db}.APP.{MODELS[workload].upper()}"
    period = node["config"]["period"]
    periods = {
        "snapshot_date": "payload:snapshot_date::date",
        "window_end_date": "dateadd(day,-1,payload:snapshot_date::date)",
        "week_start_date": "dateadd(day,-7,dateadd(day,1-dayofweekiso(payload:snapshot_date::date),payload:snapshot_date::date))",
    }[period]
    return [
        f"DELETE FROM {relation} WHERE {period} IN (SELECT DISTINCT {periods} FROM {db}.RAW.PIPELINE_EXPORTS)",
        f"INSERT INTO {relation} ({', '.join(node['config']['columns_order'])}) {model_sql}",
    ]


def deploy_procedure(workload, node, model_sql):
    db = sf.database_name(workload)
    relation = f"{db}.APP.{MODELS[workload].upper()}"
    analyst = f"{sf.RUN_TOKEN}_ANALYST"
    comment = sf.sql_string(
        sf.external_comment(workload=workload, purpose="fixed owner-rights refresh")
    )
    user = '"' + os.environ["SNOWFLAKE_EXT_USER"].replace('"', '""') + '"'
    statements = [
        copy_sql(workload),
        *raw_merge_sql(workload),
        *report_dml(workload, node, model_sql),
    ]
    statements.append(
        f"INSERT INTO {db}.APP.PIPELINE_REFRESH_RUNS SELECT CURRENT_ROLE(), CURRENT_TIMESTAMP(), LAST_QUERY_ID()"
    )
    body = (
        "BEGIN\nBEGIN TRANSACTION;\n"
        + ";\n".join(statements)
        + ";\nCOMMIT;\nRETURN CURRENT_ROLE();\nEXCEPTION WHEN OTHER THEN\nROLLBACK;\nRAISE;\nEND"
    )
    with (
        closing(snowflake.connector.connect(**parameters(workload))) as conn,
        conn.cursor() as cur,
    ):
        cur.execute(
            f"CREATE TABLE IF NOT EXISTS {relation} ({node['config']['column_ddl']}) COMMENT={comment}"
        )
        if workload == "doc_usage_dashboard":
            cur.execute(
                f"ALTER TABLE {relation} MODIFY COLUMN ACCOUNT_EMAIL SET MASKING POLICY {db}.APP.EMAIL_MASK FORCE"
            )
        cur.execute(
            f"CREATE TABLE IF NOT EXISTS {db}.APP.PIPELINE_REFRESH_RUNS (EXECUTION_ROLE VARCHAR, REFRESHED_AT TIMESTAMP_LTZ, REPORT_QUERY_ID VARCHAR) COMMENT={comment}"
        )
        for schema in ("RAW", "APP"):
            cur.execute(f"GRANT USAGE ON SCHEMA {db}.{schema} TO ROLE {analyst}")
        cur.execute(f"GRANT USAGE ON DATABASE {db} TO ROLE {analyst}")
        cur.execute(
            f"GRANT USAGE ON WAREHOUSE {sf.warehouse_name(workload)} TO ROLE {analyst}"
        )
        cur.execute(f"GRANT READ ON STAGE {db}.RAW.{STAGE} TO ROLE {analyst}")
        cur.execute(
            f"GRANT SELECT, INSERT ON TABLE {db}.RAW.PIPELINE_EXPORTS TO ROLE {analyst}"
        )
        for table in TABLES:
            cur.execute(
                f"GRANT SELECT, INSERT, UPDATE ON TABLE {db}.RAW.{table} TO ROLE {analyst}"
            )
        cur.execute(
            f"GRANT SELECT, INSERT, DELETE ON TABLE {relation} TO ROLE {analyst}"
        )
        cur.execute(
            f"GRANT SELECT, INSERT ON TABLE {db}.APP.PIPELINE_REFRESH_RUNS TO ROLE {analyst}"
        )
        cur.execute(f"GRANT SELECT ON TABLE {relation} TO ROLE {sf.RUN_TOKEN}_READER")
        cur.execute(f"SHOW GRANTS TO USER {user}")
        had_analyst = any(row[1] == analyst for row in cur.fetchall())
        cur.execute(f"SHOW GRANTS TO ROLE {analyst}")
        had_create = any(
            row[1] == "CREATE PROCEDURE" and row[3] == f"{db}.APP"
            for row in cur.fetchall()
        )
        try:
            if not had_analyst:
                cur.execute(f"GRANT ROLE {analyst} TO USER {user}")
            if not had_create:
                cur.execute(
                    f"GRANT CREATE PROCEDURE ON SCHEMA {db}.APP TO ROLE {analyst}"
                )
            cur.execute("USE SECONDARY ROLES NONE")
            cur.execute(f"USE ROLE {analyst}")
            cur.execute(
                f"CREATE OR REPLACE PROCEDURE {procedure_name(workload)}() RETURNS VARCHAR LANGUAGE SQL COMMENT={comment} EXECUTE AS OWNER AS $$\n{body}\n$$"
            )
            cur.execute(
                f"GRANT USAGE ON PROCEDURE {procedure_name(workload)}() TO ROLE DEVIN_EXT_ROLE"
            )
        finally:
            cur.execute("USE ROLE DEVIN_EXT_ROLE")
            if not had_create:
                cur.execute(
                    f"REVOKE CREATE PROCEDURE ON SCHEMA {db}.APP FROM ROLE {analyst}"
                )
            if not had_analyst:
                cur.execute(f"REVOKE ROLE {analyst} FROM USER {user}")


def deploy():
    for workload in WORKLOADS:
        dbt(workload, "compile", MODELS[workload])
    target = Path(os.environ["PIPELINE_DBT_TARGET"])
    manifest = json.loads((target / "manifest.json").read_text())
    for workload, name in MODELS.items():
        node = manifest["nodes"][f"model.otterworks_pipeline.{name}"]
        model_sql = (
            target / "compiled" / "otterworks_pipeline" / "models" / f"{name}.sql"
        ).read_text()
        deploy_procedure(workload, node, model_sql)
    for workload in WORKLOADS:
        ep = sf.endpoint(sf.workload_csids(workload)[0])
        with (
            closing(snowflake.connector.connect(**parameters(workload))) as conn,
            conn.cursor() as cur,
        ):
            for statement in sf.task_deploy_sql(
                ep,
                schedule="USING CRON 10 * * * * UTC",
                body=f"CALL {procedure_name(workload)}()",
                commit=sf.resolve_commit(repo=str(ROOT.parent.parent)),
                run_id=sf.make_run_id(workload, "runtime"),
            ):
                cur.execute(statement)
            print(f"Scheduled {sf.task_name(workload)} hourly at minute 10 UTC")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=[
            "publish",
            "export",
            "hourly-export",
            "load",
            "dbt",
            "deploy",
            "execute",
        ],
    )
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--workload", choices=WORKLOADS, default="doc_usage_dashboard")
    parser.add_argument(
        "--dbt-command", default="test", choices=["parse", "compile", "run", "test"]
    )
    parser.add_argument("--select")
    parser.add_argument("--phase", default="dev", choices=["dev", "runtime"])
    args = parser.parse_args()
    if args.command == "publish":
        if not args.bundle:
            parser.error("publish requires --bundle")
        publish(args.bundle, args.phase)
    elif args.command == "export":
        export_source()
    elif args.command == "hourly-export":
        hourly_export()
    elif args.command == "load":
        load(args.force)
    elif args.command == "dbt":
        dbt(args.workload, args.dbt_command, args.select)
    elif args.command == "deploy":
        deploy()
    else:
        with (
            closing(snowflake.connector.connect(**parameters(args.workload))) as conn,
            conn.cursor() as cur,
        ):
            cur.execute(f"EXECUTE TASK {sf.task_name(args.workload)}")
            print(
                json.dumps(
                    {
                        "query_id": cur.sfqid,
                        "requested_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
            )


if __name__ == "__main__":
    main()
