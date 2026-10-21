import json

import pytest

from wp import schemas
from wp.engines import Snowflake

P = "MIG_"


def r(sql):
    return schemas.remap(sql, P)


@pytest.mark.parametrize("sql,want", [
    ("SELECT * FROM dw.claim_fact", "SELECT * FROM MIG_DW.claim_fact"),
    ("DELETE FROM stg.claim_feed", "DELETE FROM MIG_STG.claim_feed"),
    ("SELECT * FROM audit.claim_event", "SELECT * FROM MIG_AUDIT.claim_event"),
    ("MERGE INTO PARITY.BOARD b", "MERGE INTO MIG_PARITY.BOARD b"),
    ('CREATE OR REPLACE TABLE DW."ClaimStatusRef" (x INT)', 'CREATE OR REPLACE TABLE MIG_DW."ClaimStatusRef" (x INT)'),
    ("SELECT * FROM dw.ClaimStatusRef s", "SELECT * FROM MIG_DW.ClaimStatusRef s"),
    ('SELECT * FROM "DW"."ClaimStatusRef"', 'SELECT * FROM "MIG_DW"."ClaimStatusRef"'),
    ("CALL dw.usp_refresh_policy_contact()", "CALL MIG_DW.usp_refresh_policy_contact()"),
    ("SELECT dw.fn_holder_display_name(a, b, c) FROM dw.dim_policy",
     "SELECT MIG_DW.fn_holder_display_name(a, b, c) FROM MIG_DW.dim_policy"),
    ("SELECT * FROM mydb.dw.dim_region", "SELECT * FROM mydb.MIG_DW.dim_region"),
    ("SELECT * FROM dw . dim_region", "SELECT * FROM MIG_DW . dim_region"),
])
def test_qualified_names(sql, want):
    assert r(sql) == want


@pytest.mark.parametrize("name", ["dw", "DW", "Dw", "dW"])
def test_case_variants(name):
    assert r(f"SELECT 1 FROM {name}.t") == "SELECT 1 FROM MIG_DW.t"


@pytest.mark.parametrize("sql,want", [
    ("CREATE SCHEMA IF NOT EXISTS STG;", "CREATE SCHEMA IF NOT EXISTS MIG_STG;"),
    ("CREATE SCHEMA IF NOT EXISTS parity", "CREATE SCHEMA IF NOT EXISTS MIG_PARITY"),
    ("create or replace schema audit", "create or replace schema MIG_AUDIT"),
    ("USE SCHEMA dw", "USE SCHEMA MIG_DW"),
    ("DROP SCHEMA IF EXISTS mydb.STG", "DROP SCHEMA IF EXISTS mydb.MIG_STG"),
    ("SHOW TABLES IN SCHEMA DW", "SHOW TABLES IN SCHEMA MIG_DW"),
])
def test_schema_keyword(sql, want):
    assert r(sql) == want


@pytest.mark.parametrize("sql", [
    "SELECT 'dw.claim_fact' AS label",
    "SELECT 'it''s dw.x' FROM t",
    "SELECT get_ddl('function', 'DW.FN_HOLDER_DISPLAY_NAME')",
    "SELECT 'a\\'dw.x' FROM t",
    "-- reads dw.claim_fact\nSELECT 1",
    "/* STG.claim_feed */ SELECT 1",
    "SELECT x.dw FROM t x",
    "SELECT a.b.dw.c FROM t",
    "SELECT dw FROM t",
    "SELECT * FROM t AS dw",
    'SELECT * FROM "dw".t',
    "SELECT * FROM mig_dw.t",
    "SELECT * FROM dwh.t, stage.t, audits.t, dw_x.t",
    "SELECT table_name FROM information_schema.tables WHERE table_schema = UPPER('dw')",
])
def test_no_false_hits(sql):
    assert r(sql) == sql


def test_literal_inside_statement_untouched_while_code_remapped():
    sql = "INSERT INTO dw.etl_log (proc_name, step) SELECT 'stg.claim_feed', 'post' FROM dw.claim_fact"
    assert r(sql) == ("INSERT INTO MIG_DW.etl_log (proc_name, step) SELECT 'stg.claim_feed', 'post' "
                      "FROM MIG_DW.claim_fact")


def test_dollar_quoted_body_is_remapped_but_its_literals_are_not():
    sql = ("CREATE OR REPLACE PROCEDURE DW.P() RETURNS VARCHAR LANGUAGE SQL AS\n$$\nBEGIN\n"
           "  INSERT INTO DW.ETL_LOG VALUES ('p', 'DW.ETL_LOG', 0);\n"
           "  sql_text := 'SELECT * FROM STG.PRODUCER_FEED WHERE x = ''PRODUCER''';\n"
           "  RETURN 'ok';\nEND;\n$$;")
    out = r(sql)
    assert "PROCEDURE MIG_DW.P()" in out
    assert "INSERT INTO MIG_DW.ETL_LOG VALUES ('p', 'DW.ETL_LOG', 0)" in out
    assert "'SELECT * FROM STG.PRODUCER_FEED WHERE x = ''PRODUCER'''" in out
    assert schemas.literal_refs(sql) == ["DW.", "STG."]


def test_idempotent_and_only_comparison_identifiers_change():
    q = "SELECT * FROM dw.producer_scorecard WHERE scorecard_date = '2026-09-30'"
    once = r(q)
    assert r(once) == once
    assert once.replace("MIG_DW.", "dw.") == q


def test_unset_prefix_is_passthrough(monkeypatch):
    monkeypatch.delenv("WP_SF_SCHEMA_PREFIX", raising=False)
    q = "CREATE SCHEMA IF NOT EXISTS DW; SELECT * FROM dw.t"
    assert schemas.remap(q) == q
    assert schemas.schema_name("dw") == "dw"


@pytest.mark.parametrize("bad", ["MIG-", "MIG_;DROP", "1MIG", "MIG ."])
def test_prefix_must_be_identifier(monkeypatch, bad):
    monkeypatch.setenv("WP_SF_SCHEMA_PREFIX", bad)
    with pytest.raises(ValueError):
        schemas.prefix()


def test_schema_name():
    assert schemas.schema_name("dw", P) == "MIG_DW"
    assert schemas.schema_name("PARITY", P) == "MIG_PARITY"
    assert schemas.schema_name("other", P) == "other"


def test_snowflake_engine_sends_only_prefixed_statements(monkeypatch, tmp_path):
    log = tmp_path / "dry.jsonl"
    monkeypatch.setenv("WP_DRY_RUN", str(log))
    monkeypatch.setenv("WP_SF_SCHEMA_PREFIX", P)
    sf = Snowflake()
    assert sf.default_schema == "MIG_DW"
    sf.run_script("CREATE SCHEMA IF NOT EXISTS STG;\nCREATE OR REPLACE TABLE DW.\"ClaimStatusRef\" (x INT);")
    sf.execute("DELETE FROM dw.claim_fact")
    sf.query("SELECT * FROM audit.claim_event")
    sf.insert_rows("stg.claim_feed", ["a"], [(1,)])
    assert sf.resolve("dw.ClaimStatusRef") == "dw.ClaimStatusRef"
    sent = [json.loads(line)["sql"] for line in log.read_text().splitlines()]
    assert sent == [
        "CREATE SCHEMA IF NOT EXISTS MIG_STG;\nCREATE OR REPLACE TABLE MIG_DW.\"ClaimStatusRef\" (x INT);",
        "DELETE FROM MIG_DW.claim_fact",
        "SELECT * FROM MIG_AUDIT.claim_event",
        "INSERT INTO MIG_STG.claim_feed (a) VALUES (%s)",
        ("SELECT table_name FROM information_schema.tables WHERE table_schema = UPPER('MIG_DW') "
         "AND UPPER(table_name) = UPPER('ClaimStatusRef')"),
    ]


def test_snowflake_engine_without_prefix_is_unchanged(monkeypatch, tmp_path):
    log = tmp_path / "dry.jsonl"
    monkeypatch.setenv("WP_DRY_RUN", str(log))
    monkeypatch.delenv("WP_SF_SCHEMA_PREFIX", raising=False)
    sf = Snowflake()
    assert sf.default_schema == "DW"
    sf.execute("DELETE FROM dw.claim_fact")
    assert json.loads(log.read_text())["sql"] == "DELETE FROM dw.claim_fact"


def test_harness_schemas_used():
    sql = ('CREATE SCHEMA IF NOT EXISTS MIG_STG; SELECT x.a FROM mig_dw.t x JOIN db.MIG_AUDIT."E" e '
           "ON 'dw.q' = x.dw JOIN information_schema.tables i ON 1=1")
    assert schemas.harness_schemas_used(sql, P) == ["MIG_AUDIT", "MIG_DW", "MIG_STG"]
    assert schemas.harness_schemas_used("SELECT * FROM dw.a; CREATE SCHEMA IF NOT EXISTS PARITY", P) == ["DW", "PARITY"]
    assert schemas.harness_schemas_used(r("SELECT * FROM dw.a JOIN stg.b JOIN audit.c JOIN parity.board"), P) == [
        "MIG_AUDIT", "MIG_DW", "MIG_PARITY", "MIG_STG"]
