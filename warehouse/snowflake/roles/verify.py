"""Apply the scoped plan and prove functional-role isolation on live scratch objects."""
import argparse
import json
import os
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dry_run

DATABASE = "SFX_D1110_AFTER"
MARTS = ("MART", "MART_SPARK", "COMPAT")


def main():
    import snowflake.connector
    from snowflake.connector.errors import ProgrammingError
    from cryptography.hazmat.primitives import serialization

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if os.environ["SNOWFLAKE_DATABASE"] != DATABASE or os.environ["SNOWFLAKE_ROLE"] != "SFX_D1110_ROLE":
        raise SystemExit("Live proof requires SFX_D1110_AFTER and SFX_D1110_ROLE")
    key = serialization.load_pem_private_key(os.environ["SNOWFLAKE_PRIVATE_KEY"].encode(), None)
    tag = {"run": "sfx-d1110", "act": "fix", "step": "analyst-grants"}
    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"],
        private_key=key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                                     serialization.NoEncryption()),
        role="SFX_D1110_ROLE", database=DATABASE, warehouse="SFX_D1110_TRANSFORM_WH",
        session_parameters={"QUERY_TAG": json.dumps(tag, separators=(",", ":")), "TIMEZONE": "UTC"},
    )
    evidence = []
    scratch = []
    name = "SFX_D1110_GRANTS_" + uuid.uuid4().hex[:12].upper()
    with conn, conn.cursor() as cur:
        def execute(sql):
            try:
                cur.execute(sql)
                return cur.fetchall()
            except ProgrammingError as error:
                evidence.append({"sql": sql, "result": "failed", "query_id": error.sfqid,
                                 "errno": error.errno, "sqlstate": error.sqlstate})
                raise

        def rows(sql):
            result = execute(sql)
            return [dict(zip((d[0].lower() for d in cur.description), row)) for row in result]

        def check(sql, denied=False):
            try:
                result = execute(sql)
            except ProgrammingError as error:
                if not denied or error.sqlstate not in ("42501", "02000"):
                    raise
                evidence.append({"sql": sql, "result": "denied", "query_id": cur.sfqid,
                                 "errno": error.errno, "sqlstate": error.sqlstate})
            else:
                evidence.append({"sql": sql, "result": "allowed", "query_id": cur.sfqid})
                if denied:
                    raise AssertionError("Analyst unexpectedly allowed: " + sql)
                return result

        execute("USE SECONDARY ROLES NONE")
        try:
            if args.apply:
                for sql in (dry_run.ROOT / "migrations/V010__spark_schemas.sql").read_text().split(";"):
                    if sql.strip():
                        check(sql.strip())
            for role in ("ANALYST", "TRANSFORMER", "LOADER", "PARITY", "SNOWPARK", "OPS"):
                execute(f"SHOW GRANTS TO ROLE SFX_D1110_{role}")
            if args.apply:
                for _, _, sql in dry_run.validate(dry_run.statements()):
                    if not sql.startswith("CREATE ROLE "):
                        check(sql)
            grants = rows("SHOW GRANTS TO ROLE SFX_D1110_ANALYST")
            future = rows("SHOW FUTURE GRANTS TO ROLE SFX_D1110_ANALYST")
            for grant in grants + future:
                privilege = grant["privilege"]
                obj = grant["name"]
                kind = grant.get("granted_on", grant.get("grant_on"))
                if kind == "WAREHOUSE":
                    assert privilege == "USAGE" and obj == "SFX_D1110_TRANSFORM_WH", grant
                elif kind == "DATABASE":
                    assert privilege == "USAGE" and obj == DATABASE, grant
                else:
                    assert obj.startswith(DATABASE + ".") and obj.split(".")[1] in MARTS, grant
                    assert ((kind == "SCHEMA" and privilege == "USAGE") or
                            (kind in ("TABLE", "VIEW") and privilege == "SELECT")), grant
                assert str(grant.get("grant_option", "false")).lower() == "false", grant
            assert grants and future
            evidence.append({"check": "analyst current/future grants are mart-only USAGE/SELECT",
                             "current_grants": len(grants), "future_grants": len(future)})
            published = []
            protected = []
            for schema in MARTS:
                for kind in ("TABLES", "VIEWS"):
                    published.extend((schema, row["name"]) for row in
                                     rows(f"SHOW {kind} IN SCHEMA {DATABASE}.{schema}"))
            for schema in ("CORE_BILLING", "RAW_BILLING"):
                tables = rows(f"SHOW TABLES IN SCHEMA {DATABASE}.{schema}")
                assert tables, f"No existing table to prove read denial in {schema}"
                protected.append((schema, tables[0]["name"]))
            execute("USE ROLE SFX_D1110_TRANSFORMER")
            assert check("SELECT CURRENT_ROLE(), CURRENT_DATABASE()") == [("SFX_D1110_TRANSFORMER", DATABASE)]
            for schema in ("MART", "MART_SPARK"):
                table = f"{DATABASE}.{schema}.{name}"
                view = table + "_V"
                scratch.append((table, view))
                check(f"CREATE TABLE {table} (ID INT) COMMENT='run_token=sfx-d1110 expires=2026-11-24 role proof'")
                check(f"CREATE VIEW {view} COMMENT='run_token=sfx-d1110 expires=2026-11-24 role proof' AS SELECT ID FROM {table}")
                check(f"INSERT INTO {table} VALUES (1)")
                check(f"UPDATE {table} SET ID=2 WHERE ID=1")
                check(f"DELETE FROM {table} WHERE ID=2")
                check(f"INSERT INTO {table} VALUES (1)")
                for area in ("BILLING", "DOCUMENTS", "USERS", "AUDIT"):
                    source = rows(f"SHOW TABLES IN SCHEMA {DATABASE}.SPARK_RAW_{area}")
                    if source:
                        check(f"SELECT * FROM {DATABASE}.SPARK_RAW_{area}.{source[0]['name']} LIMIT 0")
            execute("USE ROLE SFX_D1110_ANALYST")
            assert check("SELECT CURRENT_ROLE(), CURRENT_DATABASE()") == [("SFX_D1110_ANALYST", DATABASE)]
            for schema, relation in published:
                check(f'SELECT * FROM {DATABASE}."{schema}"."{relation}" LIMIT 1')
            for table, view in scratch:
                assert check(f"SELECT ID FROM {table}") == [(1,)]
                assert check(f"SELECT ID FROM {view}") == [(1,)]
                for sql in (
                    f"INSERT INTO {table} VALUES (2)", f"UPDATE {table} SET ID=2",
                    f"DELETE FROM {table}", f"TRUNCATE TABLE {table}",
                    f"ALTER TABLE {table} ADD COLUMN EXTRA INT", f"DROP TABLE {table}",
                    f"CREATE TABLE {table}_DENIED (ID INT)",
                    f"CREATE VIEW {view}_DENIED AS SELECT 1 AS ID",
                ):
                    check(sql, denied=True)
                assert check(f"SELECT ID FROM {table}") == [(1,)]
            for schema in ("CORE_BILLING", "RAW_BILLING", "LANDING", "SCHEMACHANGE"):
                check(f"CREATE TABLE {DATABASE}.{schema}.{name}_DENIED (ID INT)", denied=True)
            check(f"CREATE SCHEMA {DATABASE}.{name}_DENIED", denied=True)
            for schema, relation in protected:
                check(f'SELECT * FROM {DATABASE}."{schema}"."{relation}" LIMIT 0', denied=True)
            evidence.append({"caveat": "Snowflake permits session-local temporary tables with USAGE; persistent DDL and warehouse writes are denied"})
        finally:
            execute("USE ROLE SFX_D1110_ROLE")
            for table, view in scratch:
                execute(f"DROP VIEW IF EXISTS {view}")
                execute(f"DROP TABLE IF EXISTS {table}")
            history = rows(
                "SELECT QUERY_ID, ROLE_NAME, QUERY_TAG, QUERY_TEXT, EXECUTION_STATUS, ERROR_CODE, START_TIME "
                "FROM TABLE(SFX_D1110_AFTER.INFORMATION_SCHEMA.QUERY_HISTORY_BY_SESSION(RESULT_LIMIT => 10000)) "
                "WHERE QUERY_TAG = '" + json.dumps(tag, separators=(",", ":")) + "' ORDER BY START_TIME"
            )
            print(json.dumps({"query_tag": tag, "evidence": evidence, "query_history": history},
                             indent=2, default=str))


if __name__ == "__main__":
    main()
