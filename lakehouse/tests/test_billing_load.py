import os
import shutil
import uuid
from datetime import date
from types import SimpleNamespace

import pytest
from jinja2 import Environment, StrictUndefined
from pyspark.sql import types as T

from lakehouse.orchestration.graph import load
from lakehouse.runtime.layout import ROOT, data_root
from lakehouse.runtime.session import create_session
from warehouse.seed.columns import TABLES


@pytest.fixture(scope='module')
def spark():
    original = os.environ.get('NS')
    os.environ['NS'] = 'test-billing-' + uuid.uuid4().hex
    session = create_session()
    yield session
    session.stop()
    shutil.rmtree(data_root())
    if original is None:
        del os.environ['NS']
    else:
        os.environ['NS'] = original


class Relation:
    database = None
    schema = 'silver_billing'

    def __init__(self, name):
        self.identifier = name

    def __str__(self):
        return self.schema + '.' + self.identifier


def render(spark, name, day='20261109', macro=None):
    relation = Relation(name)

    def existing(database, schema, identifier):
        target = schema + '.' + identifier
        return target if spark.catalog.tableExists(target) else None

    macros = (ROOT / 'dbt/macros/legacy_text.sql').read_text()
    macros += (ROOT / 'dbt/macros/billing_load.sql').read_text().split('{% test ')[0]
    template = '{{ ' + macro + '() }}' if macro else (
        ROOT / 'dbt/models/silver/billing' / (name + '.sql')).read_text()
    return Environment(undefined=StrictUndefined).from_string(macros + template).render(
        this=relation, execute=True, adapter=SimpleNamespace(get_relation=existing),
        config=lambda **_: '', env_var=lambda _: day,
        run_query=lambda sql: spark.sql(sql).collect(),
        source=lambda domain, table: 'test_bronze_' + table,
        ref=lambda table: 'test_' + table)


def stage_accounts(spark, rows):
    schema = 'customer_id long, status_cd string, currency_cd string'
    spark.createDataFrame(rows, schema).createOrReplaceTempView('test_stg_customer_account')


def history(spark, day):
    for macro in ('billing_history_guard', 'billing_history_keys'):
        spark.sql(render(spark, 'customer_account_hist', day, macro)).collect()
    sql = render(spark, 'customer_account_hist', day)
    spark.sql('create or replace table silver_billing.customer_account_hist using delta as ' + sql)
    spark.table('silver_billing.customer_account_hist').createOrReplaceTempView('test_customer_account_hist')
    sql = render(spark, 'account_hist_batch', day)
    spark.sql('create or replace table silver_billing.account_hist_batch using delta as ' + sql)


def history_rows(spark):
    return sorted(tuple(row) for row in spark.table('silver_billing.customer_account_hist').collect())


def test_billing_history_replay_and_order(spark):
    stage_accounts(spark, [(1, 'ACTIVE', 'USD'), (2, None, None)])
    history(spark, '20261109')
    initial = history_rows(spark)
    history(spark, '20261109')
    assert history_rows(spark) == initial
    stage_accounts(spark, [(1, 'closed', 'EUR'), (2, 'ACTIVE', None), (3, 'NEW', 'GBP')])
    history(spark, '20261110')
    changed = history_rows(spark)
    assert len(changed) == 5
    assert changed[0][2] == date(2026, 11, 10)
    assert changed[1][1:3] == (date(2026, 11, 10), date(9999, 12, 31))
    history(spark, '20261110')
    assert history_rows(spark) == changed
    stage_accounts(spark, [(1, 'ACTIVE', 'USD'), (2, None, None)])
    history(spark, '20261110')
    assert history_rows(spark) == initial
    # Case and trailing blanks compare without creating a new version.
    stage_accounts(spark, [(1, 'active  ', 'usd')])
    history(spark, '20261111')
    assert history_rows(spark) == initial
    batches = spark.table('silver_billing.account_hist_batch').collect()
    with pytest.raises(Exception, match='completed later account-history'):
        history(spark, '20261110')
    assert history_rows(spark) == initial
    assert spark.table('silver_billing.account_hist_batch').collect() == batches
    stage_accounts(spark, [])
    history(spark, '20261112')
    assert history_rows(spark) == initial
    assert spark.table('silver_billing.account_hist_batch').count() == 4
    for rows in ([(None, 'ACTIVE', 'USD')], [(1, 'ACTIVE', 'USD'), (1, 'NEW', 'EUR')]):
        stage_accounts(spark, rows)
        with pytest.raises(Exception, match='nonnull unique customer IDs'):
            history(spark, '20261113')
        assert history_rows(spark) == initial
        assert spark.table('silver_billing.account_hist_batch').count() == 4


def test_billing_load_types_empty_and_errors(spark):
    for table in (t for t in TABLES if t.area == 'billing'):
        name = table.name.lower()
        values = {'B': '1', 'I': '1', 'D': '2026-11-09', 'N': '1.235', 'Q': '0.12345'}
        row = [values.get(c.kind, 'x' * 25) for c in table.columns]
        schema = T.StructType([T.StructField(c.name.lower(), T.StringType()) for c in table.columns])
        schema.add('_business_date', T.DateType())
        source = 'test_bronze_' + name
        spark.createDataFrame([row + [date(2026, 11, 9)]], schema).createOrReplaceTempView(source)
        staged = spark.sql(render(spark, 'stg_' + name))
        staged.createOrReplaceTempView('test_stg_' + name)
        assert staged.count() == 1
        result = spark.sql(render(spark, name)).first()
        assert result[0] == 1
        for column in table.columns:
            key = column.name.lower()
            if column.kind == 'N':
                assert str(result[key]) == '1.24'
            if column.kind == 'Q':
                assert str(result[key]) == '0.1235'
        # A different business date is empty, never a fallback to the newest feed.
        assert spark.sql(render(spark, 'stg_' + name, '20261108')).count() == 0
        empty = spark.createDataFrame([], schema)
        empty.createOrReplaceTempView(source)
        assert spark.sql(render(spark, 'stg_' + name)).count() == 0
        row[0] = 'bad-key'
        spark.createDataFrame([row + [date(2026, 11, 9)]], schema).createOrReplaceTempView(source)
        with pytest.raises(Exception, match='CAST_INVALID_INPUT'):
            spark.sql(render(spark, 'stg_' + name)).collect()
    schema = 'customer_id string, owner_user_id string, account_name string, status_cd string, currency_cd string, created_dt string, account_number string, country_cd string, region_cd string, _business_date date'
    row = ['1', None, 'x' * 201, None, '', None, '', '', '', date(2026, 11, 9)]
    spark.createDataFrame([row], schema).createOrReplaceTempView('test_bronze_customer_account')
    with pytest.raises(Exception, match='exceeds 200 characters'):
        spark.sql(render(spark, 'stg_customer_account')).collect()
    row[2] = 'x' * 101
    spark.createDataFrame([row], schema).createOrReplaceTempView('test_bronze_customer_account')
    result = spark.sql(render(spark, 'customer_account')).first()
    assert result.account_name == 'x' * 100
    assert result.status_cd is None and result.currency_cd == '   '


def test_billing_journal_posting_date_append(spark):
    schema = 'journal_line_id long, invoice_id long, credit_note_id long, gl_account_id long, posting_dt date, currency_cd string, debit_amount decimal(14,2), credit_amount decimal(14,2), description string'

    def incoming(rows):
        spark.createDataFrame(rows, schema).createOrReplaceTempView('test_stg_gl_journal_line')

    def apply():
        sql = render(spark, 'gl_journal_line')
        spark.sql('create or replace table silver_billing.gl_journal_line using delta as ' + sql)

    incoming([(1, None, None, 1200, date(2026, 11, 9), 'USD', None, None, 'first')])
    apply()
    apply()
    assert spark.table('silver_billing.gl_journal_line').count() == 1
    incoming([(2, None, None, 1200, date(2026, 11, 9), 'USD', None, None, 'ignored'),
              (3, None, None, 1200, date(2026, 11, 10), 'EUR', None, None, 'new')])
    apply()
    assert {r.journal_line_id for r in spark.table('silver_billing.gl_journal_line').collect()} == {1, 3}
    incoming([])
    apply()
    assert spark.table('silver_billing.gl_journal_line').count() == 2
    incoming([(4, None, None, 1200, None, 'USD', None, None, 'null date')])
    apply()
    apply()
    assert spark.table('silver_billing.gl_journal_line').count() == 4


def test_billing_load_stage_replacement():
    nodes = {n['id']: n for n in load()['lakehouse_daily']['nodes']}
    dbt = nodes['dbt_billing']
    assert dbt['selector'] == 'path:models/silver/billing'
    assert dbt['depends_on'] == ['bronze_billing']
    names = ['01_load_accounts', '02_load_subscriptions', '03_load_invoices',
             '04_load_payments', '05_load_usage', 'load_account_history']
    for name in names:
        assert 'cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/' + name in dbt['legacy_objects']
    for name in [t.name.lower() for t in TABLES if t.area == 'billing'] + ['customer_account_hist', 'account_hist_batch']:
        assert (ROOT / 'dbt/models/silver/billing' / (name + '.sql')).is_file()
        for output in ([name, 'stg_' + name] if name not in ('customer_account_hist', 'account_hist_batch') else [name]):
            parity = next(n for n in nodes.values() if n.get('spec') == 'billing.' + output)
            assert 'dbt_billing' in parity['depends_on']
