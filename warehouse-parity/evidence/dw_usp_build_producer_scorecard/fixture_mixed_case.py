"""Mixed-case feed fixture for dw.usp_build_producer_scorecard.

Adds one feed row spelled P1003 next to the frozen p1003 row (same region MW, same feed_date),
runs both engines and compares with the harness. The frozen seed and shared Snowflake tables
are not changed: the legacy row is added to the local SQL Server container and removed again,
and on Snowflake session-scoped temporary tables shadow STG.PRODUCER_FEED, DW.PRODUCER_SCORECARD
and DW.ETL_LOG for this connection only.

Run from warehouse-parity/:  python evidence/dw_usp_build_producer_scorecard/fixture_mixed_case.py <label>
"""
import re
import sys
from pathlib import Path

from wp import parity
from wp.engines import Snowflake, SqlServer

OBJ = "dw.usp_build_producer_scorecard"
DAY = "2026-09-30"
COMPARE = f"SELECT * FROM dw.producer_scorecard WHERE scorecard_date = '{DAY}'"
KEYS = ["region_code", "producer_code"]
FEED_COLS = ["feed_id", "producer_code", "region_code", "policy_count", "claim_count", "written_premium", "feed_date"]
FIXTURE = (9001, "P1003", "MW", 5, 1, 100.00, DAY)
DDL = Path(__file__).resolve().parents[3] / "industries/insurance/azure-synapse/first_pass/snowflake/00_ddl.sql"

label = sys.argv[1]

leg = SqlServer()
leg.execute("DELETE FROM stg.producer_feed WHERE feed_id = %s", (FIXTURE[0],))
leg.execute(f"INSERT INTO stg.producer_feed ({','.join(FEED_COLS)}) VALUES (%s,%s,%s,%s,%s,%s,%s)", FIXTURE)
try:
    leg.execute(f"DELETE FROM dw.producer_scorecard WHERE scorecard_date = '{DAY}'")
    leg.execute(f"EXEC dw.usp_build_producer_scorecard @scorecard_date = '{DAY}'")
    legacy = leg.query(COMPARE)
finally:
    leg.execute("DELETE FROM stg.producer_feed WHERE feed_id = %s", (FIXTURE[0],))
    leg.execute(f"DELETE FROM dw.producer_scorecard WHERE scorecard_date = '{DAY}'")
    leg.execute(f"EXEC dw.usp_build_producer_scorecard @scorecard_date = '{DAY}'")

sf = Snowflake()
GUARD = ("SELECT (SELECT COUNT(*) FROM STG.PRODUCER_FEED), (SELECT HASH_AGG(*) FROM DW.PRODUCER_SCORECARD), "
         "(SELECT COUNT(*) FROM DW.ETL_LOG WHERE proc_name = 'usp_build_producer_scorecard')")
before = sf.query(GUARD)[1][0]
_, feed = sf.query(f"SELECT {','.join(FEED_COLS)} FROM STG.PRODUCER_FEED")
ddl = DDL.read_text()
for table in ("STG.PRODUCER_FEED", "DW.PRODUCER_SCORECARD", "DW.ETL_LOG"):
    stmt = re.search(rf"CREATE OR REPLACE TABLE {re.escape(table)}\b[^;]*;", ddl, re.I).group(0)
    sf.execute(stmt.replace("CREATE OR REPLACE TABLE", "CREATE TEMPORARY TABLE", 1))
try:
    assert sf.query("SELECT COUNT(*) FROM DW.PRODUCER_SCORECARD")[1][0][0] == 0, "temporary shadow not in effect"
    sf.insert_rows("STG.PRODUCER_FEED", FEED_COLS, [tuple(r) for r in feed] + [FIXTURE])
    sf.execute(f"CALL dw.usp_build_producer_scorecard('{DAY}'::DATE, NULL)")
    target = sf.query(COMPARE)
    assert target[1], "procedure did not write to the session's temporary scorecard"
finally:
    for table in ("STG.PRODUCER_FEED", "DW.PRODUCER_SCORECARD", "DW.ETL_LOG"):
        sf.execute(f"DROP TABLE IF EXISTS {table}")
after = sf.query(GUARD)[1][0]
assert before == after, f"shared tables changed: {before} -> {after}"

res = parity.compare(legacy, target, KEYS)
print(parity.summary_line(res))
for r in sorted(target[1], key=str):
    if str(r[2]).upper() == "P1003":
        print("snowflake", r)
for r in sorted(legacy[1], key=str):
    if str(r[2]).upper() == "P1003":
        print("legacy   ", r)
print(parity.write_evidence(OBJ, label, res))
