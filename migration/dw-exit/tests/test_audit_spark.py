from contextlib import nullcontext
import os
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import duckdb
import pytest

from parity import spark_audit
from parity.ladder import local_compare
from parity.provenance import audit_branch, provenance
from tools.audit_outputs import artifacts, outputs
from tools.audit_parity import render

ROOT = Path(__file__).resolve().parents[3]


def model(name):
    return spark_audit.render_model((ROOT / 'warehouse/dbt/models/spark' / name / (name + '.sql')).read_text())


@pytest.fixture
def db():
    with duckdb.connect() as connection:
        connection.execute('CREATE SCHEMA AUDIT_SPARK_INPUT')
        connection.execute('CREATE SCHEMA SPARK')
        for table in ('AUDIT_EVENT', 'AUDIT_EVENT_ARCHIVE', 'COMPLIANCE_FLAG', 'USER_ACTIVITY_DAILY', 'LOGIN_EVENT'):
            definitions = spark_audit.schemas()[table]
            connection.execute('CREATE TABLE AUDIT_SPARK_INPUT.' + table + ' (' + ','.join(
                name + ' ' + kind.replace('TEXT', 'VARCHAR') for name, kind in definitions) + ')')
        yield connection


def test_empty_models(db):
    for name in spark_audit.INPUTS:
        db.execute('CREATE TABLE SPARK.' + name.upper() + ' AS ' + model(name))
        assert db.execute('SELECT COUNT(*) FROM SPARK.' + name.upper()).fetchone() == (0,)


def test_actor_skew_nulls_unicode_and_newline_bytes(db):
    db.execute("INSERT INTO AUDIT_SPARK_INPUT.AUDIT_EVENT VALUES (1,NULL,1,'x','2026-11-09',NULL),(2,7,1,'x','2026-11-09',NULL),(3,99,1,'x','2026-11-09',NULL)")
    db.execute("INSERT INTO AUDIT_SPARK_INPUT.USER_ACTIVITY_DAILY VALUES (1,8,'2026-11-09',13,5),(2,9,'2026-11-09',14,6),(3,7,'2026-11-09',2,7)")
    db.execute("INSERT INTO AUDIT_SPARK_INPUT.LOGIN_EVENT VALUES (1,8,'2026-11-09 07:00:00',NULL,'agent','é'),(2,9,'2026-11-09 06:00:00',NULL,'z',''),(3,9,'2026-11-09 05:00:00',NULL,NULL,NULL),(4,7,'2026-11-09 08:00:00',NULL,'other',NULL)")
    rows = db.execute(model('audit_actor_activity_join') + ' ORDER BY audit_event_id').fetchall()
    assert [(r[0], r[1], r[4], r[5], r[6]) for r in rows] == [(0,1,11,'z',3),(7,2,7,'other',0)]


def test_daily_distinct_null_actor_and_compaction(db):
    db.execute("INSERT INTO AUDIT_SPARK_INPUT.AUDIT_EVENT VALUES (1,2,1,'x','2026-11-09',NULL),(2,2,1,'x','2026-11-09',NULL),(3,NULL,1,'x','2026-11-09',NULL)")
    db.execute('CREATE TABLE SPARK.AUDIT_DAILY_SUMMARY AS ' + model('audit_daily_summary'))
    assert db.execute('SELECT EVENT_COUNT,ACTORS FROM SPARK.AUDIT_DAILY_SUMMARY').fetchall() == [(3,1)]
    assert db.execute(model('lake_compaction_audit')).fetchall() == db.execute('SELECT * FROM SPARK.AUDIT_DAILY_SUMMARY').fetchall()


def test_archive_preserves_duplicate_and_null_rows(db):
    db.execute("INSERT INTO AUDIT_SPARK_INPUT.AUDIT_EVENT_ARCHIVE VALUES (1,NULL,2,'x','2026-11-09',NULL),(1,NULL,2,'x','2026-11-09',NULL)")
    rows = db.execute(model('audit_archive_resort')).fetchall()
    assert len(rows) == 2 and rows[0] == rows[1]


def test_compliance_threshold_case_and_no_hidden_defaults(db):
    db.execute("INSERT INTO AUDIT_SPARK_INPUT.COMPLIANCE_FLAG VALUES (1,2,3,'x',7000,'closed'),(2,2,3,'x',7000,'open'),(3,2,3,'x',6999,'CLOSED'),(NULL,NULL,3,'x',NULL,NULL)")
    rows = db.execute(model('compliance_flag_rules')).fetchall()
    assert rows == [(1,2,7000,'resolved'),(2,2,7000,'review'),(3,2,6999,'monitor'),(None,None,None,'monitor')]


def test_templates_and_missing_dependency_fail_closed(db):
    with pytest.raises(ValueError, match='Unsupported audit dbt template'):
        spark_audit.render_model("select * from {{ ref('unknown') }}")
    with pytest.raises(duckdb.Error):
        db.execute(model('lake_compaction_audit'))


def test_jdbc_snapshot_reads_actual_columns_and_empty_outputs(monkeypatch):
    rows = [(1,2,7000,'review')]
    cursor = SimpleNamespace(description=[SimpleNamespace(name=name,type_code=kind) for name,kind in
        [('FLAG_ID',20),('DOCUMENT_ID',20),('SEVERITY',23),('DISPOSITION',25)]], fetchall=lambda: rows)
    monkeypatch.setattr(spark_audit.psycopg, 'connect', lambda dsn: nullcontext(SimpleNamespace(execute=lambda query: cursor)))
    with duckdb.connect() as connection:
        spark_audit.jdbc_snapshot(connection, 'test', 'SPARK_COMPLIANCE_REVIEW', 'result')
        assert connection.execute('SELECT * FROM result').fetchall() == rows
        rows.clear()
        spark_audit.jdbc_snapshot(connection, 'test', 'SPARK_COMPLIANCE_REVIEW', 'empty_result')
        assert connection.execute('SELECT * FROM empty_result').fetchall() == []
        cursor.description[0].type_code = 999
        with pytest.raises(ValueError, match='Unsupported audit JDBC type'):
            spark_audit.jdbc_snapshot(connection, 'test', 'SPARK_COMPLIANCE_REVIEW', 'invalid_result')


def test_real_outputs_and_branch_provenance():
    for name in spark_audit.INPUTS:
        obj = dict(name=name, system='spark', subject_area='audit', target_type='dbt_model', kind='spark_job')
        obj['output_relations'] = outputs(obj)
        assert artifacts(obj)[0] == 'lake/audit/' + name
        assert len(outputs(obj)) == (2 if name in spark_audit.JDBC else 1)
        converted = provenance(obj)['converted']
        assert all(converted.values())
        assert all('/' + audit_branch() + '/' in item['url'] for links in converted.values() for item in links)


def test_materialize_actual_parquet_missing_and_stale(tmp_path, monkeypatch):
    name = 'audit_archive_resort'
    runtime = tmp_path / 'etl/spark/.data/test'
    landing = runtime / 'landing/audit/AUDIT_EVENT_ARCHIVE'
    landing.mkdir(parents=True)
    feed = landing / 'test.psv'
    feed.write_text('AUDIT_EVENT_ARCHIVE_ID|ACTOR_USER_ID|DOCUMENT_ID|EVENT_TYPE|EVENT_AT|DETAILS\n1||2|x|2026-11-09 00:00:00|text\n')
    directory = tmp_path / 'warehouse/dbt/models/spark' / name
    directory.mkdir(parents=True)
    shutil.copy(ROOT / 'warehouse/dbt/models/spark' / name / (name + '.sql'), directory)
    lake = runtime / 'lake/audit' / name
    lake.mkdir(parents=True)
    parquet = lake / 'part.parquet'
    with duckdb.connect() as connection:
        connection.execute("COPY (SELECT 1::BIGINT AUDIT_EVENT_ARCHIVE_ID,NULL::BIGINT ACTOR_USER_ID,2::BIGINT DOCUMENT_ID,'x' EVENT_TYPE,TIMESTAMP '2026-11-09' EVENT_AT,'text' DETAILS) TO ? (FORMAT PARQUET)", [str(parquet)])
    monkeypatch.setattr(spark_audit, 'ROOT', tmp_path)
    objects = [dict(name=name, system='spark', subject_area='audit')]
    with duckdb.connect() as before, duckdb.connect() as after:
        ready, errors, evidence = spark_audit.materialize(before, after, objects, 'test')
        assert not errors and ready == {'SPARK.AUDIT_ARCHIVE_RESORT'}
        assert local_compare(before, after, 'SFX_SPARK.AUDIT_ARCHIVE_RESORT', 'SPARK.AUDIT_ARCHIVE_RESORT')['passed']
        assert len(evidence[name]['input_sha256']) == 1
    os.utime(parquet, (1,1))
    with duckdb.connect() as before, duckdb.connect() as after:
        ready, errors, _ = spark_audit.materialize(before, after, objects, 'test')
        assert not ready and 'predates inputs' in errors['SPARK.AUDIT_ARCHIVE_RESORT']
    parquet.unlink()
    with duckdb.connect() as before, duckdb.connect() as after:
        ready, errors, _ = spark_audit.materialize(before, after, objects, 'test')
        assert not ready and 'Missing Spark parquet' in errors['SPARK.AUDIT_ARCHIVE_RESORT']


def test_markdown_matches_billing_columns_and_links_real_json_lines():
    row = dict(name='audit_daily_summary', subject_area='audit', row_count={'before':2,'after':2},
               column_profile={'x':{'before':{'n':1},'after':{'n':1}}},
               keyed_row_hash={'x':{'difference':0}}, local_duckdb='green', snowflake='red')
    board = dict(summary={'audit':{'local_green':1,'local_red':0,'snowflake_reason':'not run'}}, rows=[row])
    text = json.dumps(board, indent=2)
    result = render(text, 'devin/test')
    first = text.count('\n',0,text.index('{',text.index('"rows":'))) + 1
    last = len(text.splitlines()) - 2
    assert '| Rows before/after | Profile diffs | Hash Δ | DuckDB | Snowflake |' in result
    assert '| audit_daily_summary | 2/2 | 0 | 0 | green | red |' in result
    assert f'/devin/test/migration/dw-exit/board/board.json#L{first}-L{last}' in result
    board['rows'] = []
    assert '| audit_daily_summary |' not in render(json.dumps(board,indent=2), 'devin/test')
    with pytest.raises(ValueError, match='Expected indented board rows array'):
        render(json.dumps(board), 'devin/test')
