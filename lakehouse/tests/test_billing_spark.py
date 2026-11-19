import json
import os
import shutil
import uuid
from datetime import date
from decimal import Decimal

import pytest

from lakehouse.billing.spark import churn_probability, inputs, publish, register_view, schema, transform
from lakehouse.billing.spark_inputs import JDBC, JOBS, atomic_json, digest, directory, generate, verify
from lakehouse.billing.spark_reference import driver_path
from lakehouse.orchestration.graph import load
from lakehouse.runtime.layout import data_root
from lakehouse.runtime.session import create_session


@pytest.fixture(scope='module')
def spark():
    original = os.environ.get('NS')
    os.environ['NS'] = 'test-billing-spark-' + uuid.uuid4().hex
    session = create_session()
    session.conf.set('spark.sql.ansi.enabled', 'false')
    yield session
    session.stop()
    shutil.rmtree(data_root())
    if original is None:
        del os.environ['NS']
    else:
        os.environ['NS'] = original


@pytest.fixture
def delivery(tmp_path, monkeypatch):
    monkeypatch.setenv('NS', 'test-billing-contract-' + uuid.uuid4().hex)
    generate(tmp_path, '20261109')
    yield tmp_path
    shutil.rmtree(data_root())


@pytest.mark.parametrize('failure', ['missing', 'extra', 'content', 'header', 'schema', 'date'])
def test_billing_spark_input_contract(delivery, failure):
    root = directory(delivery, '20261109')
    signature = verify(delivery, '20261109')
    assert len(list(root.glob('billing/*/*.psv'))) == 18
    path = next(root.glob('billing/USAGE_DAILY/*.psv'))
    manifest = json.loads((root / 'manifest.json').read_text())
    if failure == 'missing':
        path.unlink()
    elif failure == 'extra':
        (path.parent / 'unexpected.psv').write_bytes(path.read_bytes())
    elif failure == 'content':
        path.write_text(path.read_text() + '1|2|2026-11-09|3|4\n')
    elif failure == 'header':
        path.write_text(path.read_text().replace('USAGE_ID', 'WRONG_ID'))
        manifest['files'][str(path.relative_to(root))] = digest(path)
    elif failure == 'schema':
        manifest['schemas']['USAGE_DAILY'][0][1] = 'TEXT'
    else:
        manifest['business_date'] = '20261108'
    atomic_json(root / 'manifest.json', manifest)
    assert signature
    with pytest.raises(ValueError, match='contract|header'):
        verify(delivery, '20261109')


@pytest.mark.parametrize('job,count', list(zip(JOBS, [3, 2, 5, 2, 4, 3])))
def test_billing_spark_transformations(spark, tmp_path, job, count):
    generate(tmp_path, '20261109')
    root = directory(tmp_path, '20261109')
    rows = [r.asDict() for r in transform(job, lambda t: inputs(spark, root, t)).collect()]
    assert len(rows) == count
    if job == 'billing_invoice_summary_daily':
        row = next(r for r in rows if r['customer_id'] == 7)
        assert (row['line_count'], row['amount']) == (2, Decimal('10.00'))
    elif job == 'billing_payment_aging':
        assert len([r for r in rows if r['invoice_id'] == 1]) == 2
        assert next(r for r in rows if r['invoice_id'] == 4)['days_late'] is None
    elif job == 'billing_gl_trial_balance':
        row = next(r for r in rows if r['gl_account_id'] == 1 and r['currency_code'] == 'USD')
        assert (row['debits'], row['credits'], row['net']) == (10, 2, 0)
        assert next(r for r in rows if r['currency_code'] is None)['debits'] == 0
    elif job == 'billing_usage_append_daily':
        assert {r['usage_date'] for r in rows} == {date(2026, 11, 9)}
    elif job == 'billing_churn_score':
        assert all(0 < r['churn_score'] < 1 for r in rows)
        assert churn_probability('closed', 1) != churn_probability('Closed', 1)
    else:
        assert {r['plan_id']: r['revenue'] for r in rows} == {1: Decimal('10'), 2: Decimal('-5')}


@pytest.mark.parametrize('job', JOBS)
def test_billing_spark_empty(spark, job):
    assert transform(job, lambda table: spark.createDataFrame([], schema(table))).count() == 0


def test_billing_spark_errors(spark, tmp_path, monkeypatch):
    monkeypatch.setenv('LEGACY_NS', '../outside')
    with pytest.raises(ValueError, match='namespace'):
        driver_path()
    with pytest.raises(FileNotFoundError):
        verify(tmp_path, '20261109')
    with pytest.raises(ValueError, match='Unknown'):
        transform('unknown', lambda _: None)
    with pytest.raises(TypeError):
        churn_probability('closed', None)
    with pytest.raises(Exception, match='NoneType'):
        transform('billing_churn_score', lambda _: spark.createDataFrame(
            [(1, None, 1, date(2026, 11, 9), None, 'closed')], schema('SUBSCRIPTION'))).collect()
    path = tmp_path / 'bad.psv'
    path.write_text('USAGE_ID|CUSTOMER_ID|USAGE_DATE|UNITS|AMOUNT\nbad|1|invalid|2|invalid\n')
    row = spark.read.schema(schema('USAGE_DAILY')).option('header', True).option('sep', '|').csv(str(path)).first()
    assert row.usage_id is None and row.usage_date is None and row.amount is None


def test_billing_spark_append_replay_and_atomic_recovery(spark, tmp_path, monkeypatch):
    frame = spark.createDataFrame([(1, 7, date(2026, 11, 9), 2, Decimal('2'))] * 2, schema('USAGE_DAILY'))
    job = 'billing_usage_append_daily'
    ready = lambda: None
    current = publish(spark, job, '20261109', 'a', frame, ready, tmp_path)
    initial = current.resolve()
    assert publish(spark, job, '20261109', 'a', frame, ready, tmp_path).resolve() == initial
    with pytest.raises(ValueError, match='Changed completed'):
        publish(spark, job, '20261109', 'changed', frame, ready, tmp_path)
    replace = os.replace
    def interrupt(source, destination):
        if destination.name == 'current':
            raise OSError('injected commit failure')
        replace(source, destination)
    with monkeypatch.context() as patch:
        patch.setattr(os, 'replace', interrupt)
        with pytest.raises(OSError, match='commit failure'):
            publish(spark, job, '20261110', 'b', frame.limit(1), ready, tmp_path)
    assert current.resolve() == initial
    current = publish(spark, job, '20261110', 'b', frame.limit(1), ready, tmp_path)
    for surface, format in [('parquet', 'parquet'), ('jdbc', 'delta')]:
        assert spark.read.format(format).load(str(current / surface)).count() == 3
    assert publish(spark, job, '20261109', 'a', frame, ready, tmp_path).resolve() == current.resolve()
    def invalidate():
        raise ValueError('input mutated')
    committed = current.resolve()
    with pytest.raises(ValueError, match='input mutated'):
        publish(spark, job, '20261111', 'c', frame, invalidate, tmp_path)
    assert current.resolve() == committed
    register_view(spark, job, 'parquet', current / 'parquet')
    rows = spark.table('gold_billing.' + job + '_parquet').collect()
    assert {r.parity_row for r in rows} == {1, 2, 3}
    assert all(r.usage_id == 1 for r in rows)


def test_billing_spark_snapshot_replay(spark, tmp_path):
    frame = spark.createDataFrame([(1,)], 'subscription_id long')
    job = 'billing_churn_score'
    current = publish(spark, job, '20261109', 'a', frame, lambda: None, tmp_path)
    publish(spark, job, '20261109', 'corrected', frame.limit(0), lambda: None, tmp_path)
    assert spark.read.parquet(str(current / 'parquet')).count() == 0
    publish(spark, job, '20261110', 'b', frame, lambda: None, tmp_path)
    publish(spark, job, '20261109', 'a', frame, lambda: None, tmp_path)
    assert spark.read.parquet(str(current / 'parquet')).count() == 1


def test_billing_spark_cron_replacement():
    schedules = ['0 1 * * *', '1 1 * * *', '2 1 * * *', '3 1 * * *', '10 2 * * *', '15 2 * * *']
    dags = load()
    for job, schedule in zip(JOBS, schedules):
        dag = dags['lakehouse_' + job]
        nodes = {n['id']: n for n in dag['nodes']}
        assert dag['schedule'] == schedule and dag['timezone'] == 'UTC' and dag['paused']
        assert dag['catchup'] and dag['max_active_runs'] == dag['max_active_tasks'] == 1
        assert nodes['ready']['depends_on'] == ['validate_inputs']
        assert nodes['run']['depends_on'] == ['ready']
        assert nodes['parity']['depends_on'] == ['run']
        assert nodes['run']['command'][-1] == job
        assert 'spark_job:' + job in nodes['run']['legacy_objects']
        assert 'spark_submit:etl/spark/submit/' + job + '.sh' in nodes['run']['legacy_objects']
        assert len([v for v in nodes['run']['legacy_objects'] if v.startswith('cron_entry:')]) == 1
        assert len(nodes['parity']['specs']) == (2 if job in JDBC else 1)
