"""Run the first (verbatim Teradata SQL) and corrected (native) report queries on cpw.dbx_d1111_after,
print statement_ids, and record evidence rows + the consumer's migration_control row (RECORD=true)."""
import os
import re
import sys

from databricks import sql

SRC = os.path.join(os.path.dirname(__file__), "../../src/main/java/com/otterworks/report/financewarehouse/")
PERIOD = 202611  # finance-reconciliation contract period
UNREC_PERIOD = 202601  # unreconciled-invoices contract period
EXPECTED = {"INVOICED_TOTAL": "740016.90", "PAID_TOTAL": "268853.38", "AR_GL_BALANCE": "738280.13", "VARIANCE": "-267116.61"}
AS_OF = "2026-11-09"


def tag(step):
    return f"/* run=dbx-d1111 act=consumers step={step} consumer=report-service */\n"


def constant(cls, name):
    text = open(SRC + cls + ".java").read()
    body = re.search(r"static final String " + name + r"\s*=(.*?);\n", text, re.S).group(1)
    return "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', body)).replace('\\"', '"')


def run(cur, step, query, binds):
    try:
        cur.execute(tag(step) + query, binds)
        return "pass", cur.fetchall(), cur.query_id, None
    except Exception as exc:  # first failure is expected to be a parse error
        return "fail", None, getattr(cur, "query_id", None), " ".join(str(exc).split())[:400]


def main():
    host = os.environ["DATABRICKS_HOST"].replace("https://", "").rstrip("/")
    conn = sql.connect(server_hostname=host, http_path="/sql/1.0/warehouses/" + os.environ["DATABRICKS_WAREHOUSE_ID"],
                       access_token=os.environ["DATABRICKS_TOKEN"], catalog="cpw", schema="dbx_d1111_after")
    cur = conn.cursor()
    p4 = [PERIOD] * 4
    first = run(cur, "contract-first", constant("TeradataFinanceWarehouse", "SQL"), p4)
    fixed = run(cur, "contract-fixed", constant("DatabricksFinanceWarehouse", "SQL"), p4)
    unrec = run(cur, "contract-fixed", constant("DatabricksFinanceWarehouse", "UNRECONCILED_SQL"), [AS_OF, AS_OF, UNREC_PERIOD])
    first_detail = f"verbatim Teradata SQL on Databricks: {first[3]}"
    r = fixed[1][0] if fixed[1] else None
    if r and [f"{v:.2f}" for v in r[1:5]] != list(EXPECTED.values()):
        fixed = ("fail",) + fixed[1:]
    fixed_detail = (f"native SQL period={PERIOD} as_of={AS_OF}: INVOICED_TOTAL={r[1]} PAID_TOTAL={r[2]} "
                    f"AR_GL_BALANCE={r[3]} VARIANCE={r[4]}") if r else str(fixed[3])
    unrec_detail = f"native SQL unreconciled-invoices rows={len(unrec[1]) if unrec[1] else unrec[3]}"
    for label, res, detail in (("contract-first", first, first_detail), ("contract-fixed:finance-reconciliation", fixed, fixed_detail),
                               ("contract-fixed:unreconciled-invoices", unrec, unrec_detail)):
        print(f"{label}: {res[0]} statement_id={res[2]} {detail}")
    if os.environ.get("RECORD") == "true":
        rows = [("contract-first:finance-reconciliation", "databricks-teradata-sql", first[0], first_detail, first[2]),
                ("contract-fixed:finance-reconciliation", "databricks-native", fixed[0], fixed_detail, fixed[2]),
                ("contract-fixed:unreconciled-invoices", "databricks-native", unrec[0], unrec_detail, unrec[2])]
        for extra in os.environ.get("EXTRA_EVIDENCE", "").split(";;"):
            if extra:
                rows.append(tuple(extra.split("|", 4)))
        for check, path, outcome, detail, sid in rows:
            cur.execute(tag("evidence") + "INSERT INTO cpw.dbx_d1111_parity.consumer_contracts "
                        "(consumer, check_name, path, outcome, detail, statement_id, recorded_at) "
                        "VALUES ('report-service', ?, ?, ?, ?, ?, current_timestamp())", [check, path, outcome, detail, sid])
        ok = fixed[0] == "pass" and unrec[0] == "pass"
        cur.execute(tag("evidence") + """MERGE INTO cpw.dbx_d1111_control.migration_control t
USING (SELECT 'consumer:report-service' AS object_name) s ON t.object_name = s.object_name
WHEN MATCHED THEN UPDATE SET target = ?, status = ?, parity = ?, pr = ?, updated_at = current_timestamp(),
  owner = 'report-service', first_failure = ?, first_failure_statement_id = ?, corrected_parity = ?,
  parity_statement_id = ?, red_reason = ?
WHEN NOT MATCHED THEN INSERT (object_name, subject_area, source_system, target, status, parity, pr, updated_at, owner, kind,
  first_failure, first_failure_statement_id, corrected_parity, parity_statement_id, red_reason, run_token, expires)
VALUES ('consumer:report-service', 'billing', 'teradata', ?, ?, ?, ?, current_timestamp(), 'report-service', 'consumer',
  ?, ?, ?, ?, ?, 'dbx-d1111', '2026-11-24')""",
                    [*(vals := ["cpw.dbx_d1111_after (native rewrite)", "green" if ok else "red", "pass" if ok else "fail",
                                os.environ.get("PR_URL", ""), first_detail, first[2], fixed_detail, fixed[2],
                                os.environ.get("RED_REASON", "")]), *vals])
        print("recorded evidence + control row")
    sys.exit(0 if fixed[0] == "pass" and unrec[0] == "pass" else 1)


if __name__ == "__main__":
    main()
