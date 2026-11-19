import ast
from decimal import Decimal
import os
from pathlib import Path

import duckdb
import pytest
import yaml

from parity import provenance, report_outputs, spark_billing
from parity.local_billing import statements
from parity.ladder import local_compare

ROOT = Path(__file__).resolve().parents[3]
BILLING = ROOT/'migration/dw-exit/billing'
JOBS = ['billing_churn_score', 'billing_gl_trial_balance', 'billing_invoice_summary_daily',
        'billing_payment_aging', 'billing_revenue_by_plan', 'billing_usage_append_daily']
REPORTS = ['10_subscription_report', '11_currency_daily', '12_invoice_monthly',
           'SFX_BILLING.M_CURRENCY_TOTALS', 'SFX_BILLING.M_SUBSCRIPTION_PLANS']


def test_new_outputs_and_provenance():
    manifest = yaml.safe_load((ROOT/'migration/dw-exit/manifest.yaml').read_text())
    objects = {row['name']: row for row in manifest['objects']}
    for name in JOBS + REPORTS:
        obj = objects[name]
        assert obj['output_relations']
        links = provenance.provenance(obj)
        assert links['source'] and links['metrics']
        for relation in obj['output_relations']:
            assert links['converted'][relation]
            for entry in links['converted'][relation]:
                assert '#L' in entry['url'] and entry['end_line'] >= entry['start_line']
    assert len(objects['12_invoice_monthly']['output_relations']) == 2


def test_report_queries_execute_shipped_bodies():
    source = report_outputs.source_queries()
    target = report_outputs.target_queries()
    assert set(source) == report_outputs.OUTPUTS
    assert set(target) == report_outputs.OUTPUTS - {'GL_TRIAL_BALANCE_OUTPUT'}
    with duckdb.connect() as db:
        db.execute('CREATE SCHEMA BILLING')
        db.execute("CREATE TABLE BILLING.SUBSCRIPTION AS SELECT 1 SUBSCRIPTION_ID, 2 CUSTOMER_ID, 'pro ' PLAN_CODE")
        db.execute("CREATE TABLE BILLING.PLAN_CATALOG AS SELECT 'PRO' PLAN_CODE, 1.23 MONTHLY_FEE")
        assert db.execute(target['M_SUBSCRIPTION_PLANS_OUTPUT']).fetchall() == [(1, 2, 'pro ', Decimal('1.23'))]
        db.execute('DELETE FROM BILLING.SUBSCRIPTION')
        assert db.execute(target['M_SUBSCRIPTION_PLANS_OUTPUT']).fetchall() == []
        db.execute("CREATE TABLE BILLING.INVOICE_HDR AS SELECT 'USD' CURRENCY_CD, 1.23456 TOTAL_AMOUNT")
        assert db.execute(target['M_CURRENCY_TOTALS_OUTPUT']).fetchall() == [('USD', 1, Decimal('1.23456'))]
        db.execute('DELETE FROM BILLING.INVOICE_HDR')
        assert db.execute(target['M_CURRENCY_TOTALS_OUTPUT']).fetchall() == []


def test_trial_balance_empty_and_null_sums():
    source = report_outputs.postgres_query(report_outputs.source_queries()['GL_TRIAL_BALANCE_OUTPUT'])
    assert 'ZEROIFNULL' not in source.upper() and 'COALESCE' in source.upper()
    with duckdb.connect() as db:
        db.execute('CREATE SCHEMA BILLING')
        db.execute('CREATE SCHEMA SFX_BILLING')
        db.execute('CREATE TABLE BILLING.GL_ACCOUNT (GL_ACCOUNT_ID INT, ACCOUNT_NUMBER VARCHAR, ACCOUNT_NAME VARCHAR)')
        db.execute('CREATE TABLE BILLING.GL_JOURNAL_LINE (GL_ACCOUNT_ID INT, DEBIT_AMOUNT DECIMAL(18,2), CREDIT_AMOUNT DECIMAL(18,2))')
        for statement in statements(BILLING/'35_reports.sql', '20261109'):
            db.execute(statement.sql(dialect='duckdb'))
        for table in ('GL_ACCOUNT', 'GL_JOURNAL_LINE'):
            db.execute(f'CREATE VIEW SFX_BILLING.{table} AS SELECT * FROM BILLING.{table}')
        for populated in (False, True):
            if populated:
                db.execute("INSERT INTO BILLING.GL_ACCOUNT VALUES (1, '1000', 'Cash')")
                db.execute('INSERT INTO BILLING.GL_JOURNAL_LINE VALUES (1, 1.25, NULL)')
            expected = db.execute(source).fetchall()
            actual = db.execute('SELECT * FROM BILLING.GL_TRIAL_BALANCE_OUTPUT').fetchall()
            assert sorted(actual) == sorted(expected)
        assert actual[-1][2:] == (Decimal('1.25'), Decimal('0.00'))


def test_report_missing_wrapper_fails_closed(tmp_path, monkeypatch):
    (tmp_path/'migration/dw-exit/billing').mkdir(parents=True)
    (tmp_path/'migration/dw-exit/billing/20_routines.sql').write_text(
        'CREATE OR REPLACE PROCEDURE X.BILLING.M_BROKEN() AS $$ BEGIN SELECT 1; END; $$;')
    monkeypatch.setattr(report_outputs, 'ROOT', tmp_path)
    with pytest.raises(ValueError, match='Unsupported resultset wrapper'):
        report_outputs.target_queries()


def test_spark_latest_date_initial_matches_legacy():
    model = ROOT/'warehouse/dbt/models/spark/billing_usage_append_daily/billing_usage_append_daily.sql'
    tree = ast.parse((ROOT/'etl/spark/jobs/py/billing_usage_append_daily.py').read_text())
    legacy = next(node.args[0].value for node in ast.walk(tree)
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'sql')
    with duckdb.connect() as db:
        db.execute('CREATE SCHEMA SPARK_INPUT')
        db.execute('CREATE TABLE SPARK_INPUT.USAGE_DAILY (USAGE_ID INT, CUSTOMER_ID INT, USAGE_DATE DATE, UNITS INT, AMOUNT DECIMAL(18,2))')
        db.execute('CREATE VIEW USAGE_DAILY AS SELECT * FROM SPARK_INPUT.USAGE_DAILY')
        for populated in (False, True):
            if populated:
                db.execute("INSERT INTO SPARK_INPUT.USAGE_DAILY VALUES (1, 1, '2026-11-08', 1, 1.25), (2, 1, '2026-11-09', 2, 2.50)")
            assert db.execute(spark_billing.render_model(model.read_text())).fetchall() == db.execute(legacy).fetchall()


def test_spark_model_month_format_and_unsupported_templates():
    with duckdb.connect() as db:
        query = spark_billing.render_model("SELECT TO_CHAR(d, 'YYYY-MM') period, SUM(n) total FROM (VALUES (DATE '2026-01-01', 1), (DATE '2026-01-02', 2)) t(d,n) GROUP BY 1")
        assert db.execute(query).fetchall() == [('2026-01', 3)]
    with pytest.raises(ValueError, match='Unsupported dbt template'):
        spark_billing.render_model('{{ ref("unknown") }}')
    with pytest.raises(ValueError, match='Unsupported Spark model date format'):
        spark_billing.render_model("SELECT TO_CHAR(d, 'unknown')")


def test_churn_uses_shipped_udf_and_projection():
    with duckdb.connect() as db:
        db.execute('CREATE SCHEMA SPARK_INPUT')
        db.execute('CREATE TABLE SPARK_INPUT.SUBSCRIPTION (SUBSCRIPTION_ID INT, CUSTOMER_ID BIGINT, PLAN_ID INT, START_DATE DATE, END_DATE DATE, STATUS VARCHAR)')
        query = spark_billing.churn_query(db)
        assert db.execute(query).fetchall() == []
        db.execute("INSERT INTO SPARK_INPUT.SUBSCRIPTION (SUBSCRIPTION_ID, CUSTOMER_ID, STATUS) VALUES (1, 1, 'closed'), (2, 1, 'active')")
        rows = db.execute(query).fetchall()
        assert rows[0][:2] == (1, 1) and rows[0][-1] > rows[1][-1]
        assert all(0 < row[-1] < 1 for row in rows)


def test_missing_spark_outputs_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(spark_billing, 'ROOT', tmp_path)
    monkeypatch.setattr(spark_billing, 'schemas', lambda: {})
    objects = [{'name': JOBS[0], 'system': 'spark', 'subject_area': 'billing'}]
    with duckdb.connect() as before, duckdb.connect() as after:
        ready, errors, evidence = spark_billing.materialize(before, after, objects, 'test')
    assert not ready and not evidence
    assert 'Missing Spark parquet output or landing inputs' in errors['SPARK.BILLING_CHURN_SCORE']


def test_spark_materialization_and_stale_inputs(tmp_path, monkeypatch):
    name = 'billing_usage_append_daily'
    model = ROOT/f'warehouse/dbt/models/spark/{name}/{name}.sql'
    destination = tmp_path/model.relative_to(ROOT)
    destination.parent.mkdir(parents=True)
    destination.write_text(model.read_text())
    runtime = tmp_path/'etl/spark/.data/test'
    landing = runtime/'landing/billing/USAGE_DAILY/input.psv'
    landing.parent.mkdir(parents=True)
    landing.write_text('USAGE_ID|CUSTOMER_ID|USAGE_DATE|UNITS|AMOUNT\n1|1|2026-11-09|2|1.25\n')
    output = runtime/f'lake/billing/{name}/part.parquet'
    output.parent.mkdir(parents=True)
    with duckdb.connect() as db:
        db.execute(f"COPY (SELECT 1 USAGE_ID, 1 CUSTOMER_ID, DATE '2026-11-09' USAGE_DATE, 2 UNITS, 1.25 AMOUNT) TO '{output}' (FORMAT PARQUET)")
    monkeypatch.setattr(spark_billing, 'ROOT', tmp_path)
    monkeypatch.setattr(spark_billing, 'schemas', lambda: {'USAGE_DAILY': [
        ('USAGE_ID', 'BIGINT'), ('CUSTOMER_ID', 'BIGINT'), ('USAGE_DATE', 'DATE'), ('UNITS', 'BIGINT'), ('AMOUNT', 'DECIMAL(18,2)')]})
    objects = [{'name': name, 'system': 'spark', 'subject_area': 'billing'}]
    with duckdb.connect() as before, duckdb.connect() as after:
        ready, errors, evidence = spark_billing.materialize(before, after, objects, 'test')
        assert ready == {'SPARK.BILLING_USAGE_APPEND_DAILY'} and not errors
        assert evidence[name]['landing_sha256']
        result = local_compare(before, after, 'SFX_SPARK.BILLING_USAGE_APPEND_DAILY', 'SPARK.BILLING_USAGE_APPEND_DAILY')
        assert result['passed'] and result['row_count']['before'] == 1
    os.utime(output, (0, 0))
    with duckdb.connect() as before, duckdb.connect() as after:
        ready, errors, evidence = spark_billing.materialize(before, after, objects, 'test')
    assert not ready and not evidence
    assert 'predates landing inputs' in errors['SPARK.BILLING_USAGE_APPEND_DAILY']


def test_churn_unsupported_body_fails_closed(tmp_path, monkeypatch):
    path = tmp_path/'warehouse/snowpark/billing_churn_score.py'
    path.parent.mkdir(parents=True)
    path.write_text('pass')
    monkeypatch.setattr(spark_billing, 'ROOT', tmp_path)
    with duckdb.connect() as db, pytest.raises(ValueError, match='Expected one shipped Python UDF body'):
        spark_billing.churn_query(db)
