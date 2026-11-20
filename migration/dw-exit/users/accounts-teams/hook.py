"""Run the conversions from landing files and measure independent legacy outputs."""

from io import StringIO
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import zlib

import duckdb
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
import sqlglot
from sqlglot import exp

from bteq import Runner
from etl.informatica.runner.db import Connection
from etl.informatica.runner.engine import MappingRun, SessionFailed
from etl.informatica.runner.params import resolve
from etl.informatica.runner.repo import Repository
from etl.informatica.runner.sesslog import Log
from etl.informatica.runner.workflow import process_variables
from warehouse.run_config import RunConfig


GROUP = Path(__file__).resolve().parent
ROOT = GROUP.parents[3]
INFORMATICA = ROOT / "etl/informatica"
LANDING = ROOT / "warehouse/landing"
TABLES = ("APP_USER", "USER_PROFILE", "TEAM", "TEAM_MEMBER", "ROLE_GRANT")
PC_TABLES = ("STG_APP_USER", "APP_USER", "ROLE_GRANT", "TEAM_MEMBER")
CORE_OUTPUTS = {*TABLES, *("STG_" + table for table in TABLES), "V_TEAM_MEMBERS"}
MACRO_OUTPUT = "V_M_TEAM_COUNTS_RESULT"


class SourceConnection(Connection):
    """Bind the legacy writer and lookup to the board's source connection settings."""

    def __init__(self, dsn):
        super().__init__("TD_SFX_EDW", {"default_database": "SFX_BILLING"})
        self.settings = conninfo_to_dict(dsn)

    def dsn(self):
        return self.settings


def conversion(filename, business_date):
    text = RunConfig.from_env().render((GROUP / filename).read_text())
    return sqlglot.parse(text.replace("__BUSINESS_DATE__", business_date), read="snowflake")


def local_sql(statement):
    for table in statement.find_all(exp.Table):
        table.set("catalog", None)
    return statement.sql(dialect="duckdb", comments=False)


def load_fastloads(after, business_date):
    for statement in conversion("05_fastload.sql", business_date):
        if isinstance(statement, (exp.Transaction, exp.Commit, exp.Delete)):
            after.execute(local_sql(statement))
        if not isinstance(statement, exp.Copy):
            continue

        query = statement.args["files"][0].this
        file_path = query.args.pop("from_").this.name.partition("/")[2]
        if not re.fullmatch(r"users/(APP_USER|USER_PROFILE|TEAM|TEAM_MEMBER|ROLE_GRANT)/[0-9]{8}\.psv", file_path):
            raise ValueError("Unexpected accounts-teams stage path")
        names = [f"FIELD_{index}" for index in range(1, len(statement.this.expressions) + 1)]
        for reference in list(query.find_all(exp.Parameter)):
            reference.replace(exp.column(names[int(reference.name) - 1]))
        after.execute(
            f"INSERT INTO {local_sql(statement.this)} {local_sql(query)} "
            "FROM read_csv(?, columns=?, delim='|', header=false, auto_detect=false, "
            "quote='\"', escape='\"', force_not_null=?)",
            [str(LANDING / file_path), dict.fromkeys(names, "VARCHAR"), names],
        )


def core_target(after, business_date):
    # The board's preliminary pass uses copied STG rows and source-derived column types.
    # Rebuild from the converted DDL and original landing files for the actual comparison.
    after.execute("DROP SCHEMA USERS CASCADE")
    for statement in conversion("00_tables.sql", business_date):
        # CREATE SCHEMA uses its db component as the schema name.
        if statement.kind == "SCHEMA":
            after.execute("CREATE SCHEMA USERS")
        else:
            after.execute(local_sql(statement))
    load_fastloads(after, business_date)
    for filename in ("10_load.sql", "30_views.sql"):
        for statement in conversion(filename, business_date):
            after.execute(local_sql(statement))


def save_pc_result(database, schema, table, rows):
    database.execute(f"CREATE TABLE {schema}.PC_{table} AS SELECT * FROM {schema}.{table} WHERE FALSE")
    if rows:
        columns = ", ".join("?" for _ in rows[0])
        database.executemany(f"INSERT INTO {schema}.PC_{table} VALUES ({columns})", rows)


def powercenter_source(before, dsn, business_date):
    folder, workflow = "SFX_CONTENT", "wf_SFX_CONTENT_DAILY"
    repo = Repository(INFORMATICA / "repository" / folder)
    param_files = sorted((INFORMATICA / "params").glob("*.par"))
    connection = SourceConnection(dsn)
    try:
        with TemporaryDirectory(prefix="accounts-teams-") as scratch:
            variables = process_variables(scratch)
            variables["$PMSourceFileDir"] = str(LANDING)
            for directory in variables.values():
                if directory.startswith(scratch):
                    Path(directory).mkdir(parents=True, exist_ok=True)
            for table in PC_TABLES:
                name = "s_m_SFX_" + table
                params = resolve(param_files, folder, workflow, name)
                params.update({"$$LOAD_DATE": business_date, "__WORKFLOW__": workflow})
                log = Log(Path(scratch) / (name + ".log"))
                session = repo.sessions[folder, name]
                stats = MappingRun(repo, session, params, variables, {"TD_SFX_EDW": connection}, log).run()
                if stats.rows_rejected or stats.transformation_errors:
                    raise ValueError(f"{name} reported rejected rows or transformation errors")
                rows = connection.conn.execute(
                    sql.SQL("SELECT * FROM {}").format(sql.Identifier("sfx_users", table.lower()))
                ).fetchall()
                save_pc_result(before, "SFX_USERS", table, rows)
    finally:
        connection.close(commit=False)


def powercenter_target(after, business_date):
    after.execute("BEGIN TRANSACTION")
    try:
        for filename in ("20_powercenter.sql", "21_powercenter_team_member.sql"):
            for statement in conversion(filename, business_date):
                if not isinstance(statement, (exp.Transaction, exp.Commit)):
                    after.execute(local_sql(statement))
        results = {table: after.execute(f"SELECT * FROM USERS.{table}").fetchall() for table in PC_TABLES}
    finally:
        after.execute("ROLLBACK")
    for table, rows in results.items():
        save_pc_result(after, "USERS", table, rows)


def macro_source(before, dsn, business_date):
    with Runner(connection=psycopg.connect(dsn), output=StringIO()) as runner:
        runner.execute(f"EXEC SFX_USERS.M_TEAM_COUNTS('{business_date}')")
        if runner.errorcode:
            raise ValueError(f"Teradata M_TEAM_COUNTS failed with code {runner.errorcode}")
        before.execute(
            f"CREATE TABLE SFX_USERS.{MACRO_OUTPUT} (TEAM_ID BIGINT, TEAM_NAME VARCHAR, MEMBER_COUNT BIGINT)"
        )
        if runner.rows:
            before.executemany(f"INSERT INTO SFX_USERS.{MACRO_OUTPUT} VALUES (?, ?, ?)", runner.rows)


def macro_target(after, business_date):
    _, function = conversion("40_routines.sql", business_date)
    body = local_sql(sqlglot.parse_one(function.expression.this, read="snowflake"))
    name = local_sql(function.this.this)
    args = ", ".join(arg.this.sql(dialect="duckdb") for arg in function.this.expressions)
    after.execute("CREATE SCHEMA IF NOT EXISTS OPS")
    after.execute(f"CREATE MACRO {name}({args}) AS TABLE ({body})")
    after.execute(f"CREATE TABLE USERS.{MACRO_OUTPUT} AS SELECT * FROM {name}(?)", [business_date])


def materialize(before, after, ready, errors):
    business_date = os.environ.get("BUSINESS_DATE", "20261109")
    if not re.fullmatch(r"[0-9]{8}", business_date):
        raise ValueError("BUSINESS_DATE must be YYYYMMDD")
    namespace = os.environ.get("NS", RunConfig.from_env().before_namespace)
    port = os.environ.get("TD_PG_PORT", str(54500 + zlib.crc32(namespace.encode()) % 1000))
    dsn = os.environ.get("BOARD_SOURCE_DSN", f"host=127.0.0.1 port={port} dbname=teradata user=postgres")
    ready.clear()
    pc_outputs = {"PC_" + table for table in PC_TABLES}
    try:
        core_target(after, business_date)
    except (duckdb.Error, sqlglot.errors.SqlglotError, ValueError) as error:
        errors.update({"USERS." + table: f"Accounts/teams target conversion failed: {str(error).splitlines()[0]}"
                       for table in CORE_OUTPUTS | pc_outputs | {MACRO_OUTPUT}})
        return
    ready.update("USERS." + table for table in CORE_OUTPUTS)
    try:
        macro_source(before, dsn, business_date)
        macro_target(after, business_date)
    except (psycopg.Error, ValueError, duckdb.Error, sqlglot.errors.SqlglotError) as error:
        errors[f"USERS.{MACRO_OUTPUT}"] = f"Team counts parity preparation failed: {str(error).splitlines()[0]}"
    else:
        ready.add(f"USERS.{MACRO_OUTPUT}")
    try:
        powercenter_source(before, dsn, business_date)
        powercenter_target(after, business_date)
    except (SessionFailed, OSError, psycopg.Error, duckdb.Error, sqlglot.errors.SqlglotError, ValueError) as error:
        errors.update({"USERS." + table: f"PowerCenter parity preparation failed: {str(error).splitlines()[0]}"
                       for table in pc_outputs})
    else:
        ready.update("USERS." + table for table in pc_outputs)
