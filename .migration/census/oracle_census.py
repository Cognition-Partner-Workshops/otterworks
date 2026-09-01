"""Read-only Oracle OW_BILLING census (profile discovery_commands, verbatim). Writes census/oracle_census.json."""
import json
import os
import sys

import oracledb

SCHEMA = "OW_BILLING"
QUERIES = {
    "tables": "SELECT owner, table_name, num_rows FROM all_tables WHERE owner = :schema ORDER BY num_rows DESC",
    "columns": "SELECT table_name, column_name, data_type, data_precision, data_scale, nullable, char_used, data_length, column_id "
               "FROM all_tab_columns WHERE owner = :schema ORDER BY table_name, column_id",
    "constraints": "SELECT c.table_name, c.constraint_name, c.constraint_type, cc.column_name, c.r_constraint_name, cc.position "
                   "FROM all_constraints c JOIN all_cons_columns cc ON c.constraint_name = cc.constraint_name AND c.owner = cc.owner "
                   "WHERE c.owner = :schema AND c.constraint_type IN ('P','R','U') ORDER BY c.table_name, cc.position",
    "indexes": "SELECT index_name, table_name, uniqueness, index_type FROM all_indexes WHERE owner = :schema",
    "plsql": "SELECT object_name, object_type, status FROM all_objects WHERE owner = :schema "
             "AND object_type IN ('PACKAGE','PACKAGE BODY','PROCEDURE','FUNCTION','TRIGGER','MATERIALIZED VIEW','VIEW','TYPE')",
    "dependencies": "SELECT name, type, referenced_name, referenced_type FROM all_dependencies WHERE owner = :schema AND referenced_owner = :schema",
    "sequences": "SELECT sequence_name, last_number, increment_by FROM all_sequences WHERE sequence_owner = :schema",
    "rowid_usage": "SELECT DISTINCT name, type FROM all_source WHERE owner = :schema AND UPPER(text) LIKE '%ROWID%'",
    "scheduler_jobs": "SELECT job_name, job_type, job_action, enabled FROM all_scheduler_jobs WHERE owner = :schema",
    "triggers": "SELECT trigger_name, trigger_type, triggering_event, table_name, status FROM all_triggers WHERE owner = :schema",
    "index_columns": "SELECT index_name, table_name, column_name, column_position FROM all_ind_columns WHERE index_owner = :schema ORDER BY index_name, column_position",
    "nls_patterns": "SELECT DISTINCT name, type FROM all_source WHERE owner = :schema AND (UPPER(text) LIKE '%NLS_SORT%' OR UPPER(text) LIKE '%NLS_COMP%' OR UPPER(text) LIKE '%UPPER(%' OR UPPER(text) LIKE '%LOWER(%')",
    "trap_patterns": "SELECT name, type, line, text FROM all_source WHERE owner = :schema AND (UPPER(text) LIKE '%CONNECT BY%' OR UPPER(text) LIKE '%MERGE INTO%' OR UPPER(text) LIKE '%OVER (%' OR UPPER(text) LIKE '%OVER(%' OR UPPER(text) LIKE '%FOR UPDATE%' OR UPPER(text) LIKE '%WHEN OTHERS%' OR UPPER(text) LIKE '%AUTONOMOUS_TRANSACTION%' OR UPPER(text) LIKE '%DBMS_%' OR UPPER(text) LIKE '%UTL_%' OR UPPER(text) LIKE '%SYSDATE%' OR UPPER(text) LIKE '%BULK COLLECT%') ORDER BY name, type, line",
}


def main() -> None:
    conn = oracledb.connect(user=os.environ.get("DB_USER", "ow_billing"), password=os.environ.get("DB_PASSWORD", "ow_billing"),
                            dsn=f"localhost:{os.environ.get('DB_PORT', '52521')}/FREEPDB1")
    conn.autocommit = False
    cur = conn.cursor()
    out = {}
    for name, sql in QUERIES.items():
        cur.execute(sql, schema=SCHEMA)
        cols = [d[0].lower() for d in cur.description]
        out[name] = [dict(zip(cols, r)) for r in cur.fetchall()]
    exact = {}
    for t in out["tables"]:
        cur.execute(f'SELECT COUNT(*) FROM "{SCHEMA}"."{t["table_name"]}"')
        exact[t["table_name"]] = cur.fetchone()[0]
    out["exact_counts"] = exact
    cur.execute("SELECT parameter, value FROM nls_database_parameters WHERE parameter IN ('NLS_CHARACTERSET','NLS_NCHAR_CHARACTERSET','NLS_SORT','NLS_COMP','NLS_DATE_FORMAT')")
    out["nls"] = dict(cur.fetchall())
    cur.execute("SELECT dbtimezone, sessiontimezone FROM dual")
    out["timezone"] = list(cur.fetchone())
    conn.rollback()
    path = os.path.join(os.path.dirname(__file__), "oracle_census.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(f"census written: {path}")
    for k, v in out.items():
        if isinstance(v, list):
            print(f"  {k}: {len(v)}")
    print("  exact_counts:", exact)
    print("  nls:", out["nls"], out["timezone"])


if __name__ == "__main__":
    sys.exit(main())
