from pathlib import Path
import re
import sqlite3

import pytest
import sqlglot
from warehouse.run_config import RunConfig


ROOT = Path(__file__).resolve().parents[2]


def render(path):
    text = (ROOT / path).read_text()
    text = re.sub(r"\{%.*?%\}|\{\{\s*config\(.*?\)\s*\}\}", "", text, flags=re.S)
    text = re.sub(r"\{\{\s*source\('[^']+',\s*'([^']+)'\)\s*\}\}", r"main.\1", text)
    return sqlglot.transpile(text, read="snowflake", write="sqlite")[0]


@pytest.mark.parametrize("grants,expected", [([], ["VIEW"]), ([(1, "ADMIN")], ["OWNER"]),
                                         ([(1, "ADMIN"), (1, "EDITOR")], ["EDIT", "OWNER"])])
def test_share_projection(grants, expected):
    query = render("dbt/models/pc/content/pc_content__doc_share.sql")
    with sqlite3.connect(":memory:") as db:
        db.create_function("LEFT", 2, lambda value, width: value[:width] if value is not None else None)
        db.execute("CREATE TABLE DOC_SHARE (SHARE_ID, DOCUMENT_ID, USER_ID, ACCESS_LEVEL, SHARED_DT)")
        db.execute("CREATE TABLE ROLE_GRANT (USER_ID, ROLE_CD)")
        db.execute("INSERT INTO DOC_SHARE VALUES (1, 2, 1, 'VIEW', NULL)")
        db.executemany("INSERT INTO ROLE_GRANT VALUES (?,?)", grants)
        assert sorted(row[3] for row in db.execute(query)) == expected
        db.execute("DELETE FROM DOC_SHARE")
        assert db.execute(query).fetchall() == []


@pytest.mark.parametrize("rows", [[], [(1, "abc")], [(1, "abcdefgh"), (1, "abcdefgh"), (2, None)]])
def test_table_projections(rows):
    source = RunConfig.from_env().render((ROOT.parent / "migration/dw-exit/billing/supplemental.sql").read_text())
    with sqlite3.connect(":memory:") as db:
        db.execute("CREATE TABLE feed (ID, VALUE)")
        db.executemany("INSERT INTO feed VALUES (?,?)", rows)
        for table in ("SET_ROWS", "TRUNCATION"):
            statement = next(s for s in source.split(";") if "CREATE OR REPLACE TABLE" in s and
                             f"BILLING_PROBES.{table}\n" in s)
            query = "SELECT " + statement.split("AS SELECT ", 1)[1]
            query = query.replace(RunConfig.from_env().database + ".BILLING_PROBES.FEED", "feed")
            assert db.execute(query).fetchall() == rows


@pytest.mark.parametrize("value,expected", [(5, 5), (0, None), (None, None)])
def test_numeric_projection(value, expected):
    source = (ROOT / "dbt/models/pc/audit/pc_audit__audit_event.sql").read_text()
    expression = re.search(r"case when DOCUMENT_ID.*?end", source).group()
    with sqlite3.connect(":memory:") as db:
        assert db.execute(f"SELECT {expression} FROM (SELECT ? AS DOCUMENT_ID)", (value,)).fetchone() == (expected,)
