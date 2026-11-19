import json
import os
import re
import shutil
import uuid
from datetime import date
from decimal import Decimal

import pytest
from dbt.cli.main import dbtRunner
from jinja2 import Environment, StrictUndefined
from pyspark.sql import types as T

from lakehouse.billing.calendar import variables
from lakehouse.billing.reports import REPORTS, export, publish
from lakehouse.orchestration.graph import load
from lakehouse.parity.engine import compare
from lakehouse.runtime.layout import ROOT, data_root
from lakehouse.runtime.session import create_session
from warehouse.seed.columns import TABLES


GOLD = ROOT / 'dbt/models/gold/billing'


def test_billing_stage_aware_indirect_tests(tmp_path, monkeypatch):
    monkeypatch.setenv('BUSINESS_DATE', '20261109')
    monkeypatch.setenv('LAKEHOUSE_DELTA_ROOT', str(tmp_path / 'delta'))
    for layer, expected in [('silver', False), ('gold', True)]:
        result = dbtRunner().invoke([
            'ls', '--project-dir', str(ROOT / 'dbt'), '--profiles-dir', str(ROOT / 'dbt'),
            '--target-path', str(tmp_path / layer), '--log-path', str(tmp_path / 'logs'),
            '--select', f'path:models/{layer}/billing', '--indirect-selection', 'buildable',
            '--resource-type', 'test', '--output', 'name',
        ])
        assert result.success, result.exception
        assert any('billing_monthly_amounts' in str(node) for node in result.result) == expected


@pytest.fixture(scope='module')
def spark():
    original = os.environ.get('NS')
    os.environ['NS'] = 'test-reporting-' + uuid.uuid4().hex
    session = create_session()
    yield session
    session.stop()
    shutil.rmtree(data_root())
    if original is None:
        del os.environ['NS']
    else:
        os.environ['NS'] = original


def inputs(spark, rows):
    kinds = {'B': T.LongType(), 'I': T.IntegerType(), 'D': T.DateType(),
             'N': T.DecimalType(14, 2), 'Q': T.DecimalType(7, 4)}
    for table in (t for t in TABLES if t.area == 'billing'):
        name = table.name.lower()
        schema = T.StructType([T.StructField(c.name.lower(), kinds.get(c.kind, T.StringType()))
                               for c in table.columns])
        values = [tuple(row.get(c.name) for c in schema.fields) for row in rows.get(name, [])]
        spark.createDataFrame(values, schema).createOrReplaceTempView('report_' + name)
    spark.createDataFrame(rows.get('customer_account_hist', []),
                          'customer_id long, valid_from_dt date, valid_to_dt date, status_cd string, currency_cd string'
                          ).createOrReplaceTempView('report_customer_account_hist')


def build(spark, day='20261109'):
    models = {p.stem: p.read_text() for p in GOLD.glob('*.sql')}
    result = {}

    def model(name):
        if name not in models or name in result:
            return
        for dependency in re.findall(r"ref\('([^']+)'\)", models[name]):
            model(dependency)
        sql = Environment(undefined=StrictUndefined).from_string(models[name]).render(
            ref=lambda n: 'report_' + n, env_var=lambda _: day)
        result[name] = spark.sql(sql)
        result[name].createOrReplaceTempView('report_' + name)

    for name in models:
        model(name)
    return result


def test_monthly_states_and_edges(spark, tmp_path):
    D = Decimal
    rows = {
        'customer_account': [{'customer_id': 1, 'account_name': 'Example'}],
        'gl_account': [dict(gl_account_id=i, account_number=number, account_name=name)
                       for i, number, name in [(1200, 'a123', 'Cash'), (4000, 'A123', 'Cash'),
                                               (4100, 'a123', 'Other'), (9999, None, None)]],
        'subscription': [{'subscription_id': 1, 'customer_id': 1, 'plan_code': 'plan'}],
        'plan_catalog': [{'plan_id': 1, 'plan_code': 'PLAN      ', 'monthly_fee': D('10.00')}],
        'tax_rate': [{'tax_rate_id': 1, 'rate': D('0.1000')}],
        'invoice_hdr': [dict(invoice_id=i, customer_id=1, subscription_id=(None if i == 3 else 1),
                             invoice_dt=day, bill_dt=day, period_start_dt=day.replace(day=1),
                             currency_cd=('usd' if i == 2 else 'USD'), tax_rate_id=1,
                             total_amount=D(amount), period_closed_cd='N')
                        for i, day, amount in [(1, date(2026, 10, 31), '99.00'),
                                               (2, date(2026, 11, 10), '42.00'),
                                               (3, date(2026, 11, 9), '17.00')]],
        'invoice_line': [dict(invoice_line_id=i, invoice_id=invoice, description=description,
                              line_amount=D(amount)) for i, invoice, description, amount in
                         [(1, 1, 'Usage', '2.00'), (2, 1, 'Monthly subscription', '999.00'),
                          (3, 1, None, '3.00'), (4, 2, 'Billing adjustment', '999.00')]],
        'billing_adj': [{'adjustment_id': 5, 'invoice_id': 1, 'amount': D('-1.00'),
                         'adjustment_dt': date(2026, 12, 1)}],
        'credit_note': [dict(credit_note_id=i, invoice_id=1, amount=D('1.10'), credit_dt=day)
                        for i, day in [(1, date(2026, 11, 9)), (2, date(2026, 11, 10))]],
        'gl_journal_line': [dict(journal_line_id=i, posting_dt=day, currency_cd='USD',
                                 debit_amount=D('5.00'), credit_amount=D('5.00'))
                            for i, day in [(1, date(2026, 10, 31)), (2, date(2026, 11, 1)), (3, None)]],
        'customer_account_hist': [(1, date(2026, 10, 1), date(2026, 11, 9), 'OLD', 'USD'),
                                  (1, date(2026, 11, 9), date(9999, 12, 31), None, None),
                                  (2, date(2026, 11, 1), date(9999, 12, 31), 'closed', 'USD'),
                                  (3, date(2026, 11, 1), date(9999, 12, 31), 'PENDING', 'USD')],
    }
    inputs(spark, rows)
    frames = build(spark)
    headers = {r.invoice_id: r for r in frames['monthly_invoice_hdr'].collect()}
    assert headers[1].subtotal_amount == D('14.00')
    assert headers[1].tax_amount == D('1.40') and headers[1].total_amount == D('15.40')
    assert headers[2].total_amount == D('42.00') and headers[3].total_amount == D('17.00')
    assert {r.currency_control_total for r in headers.values()} == {D('74.40')}
    assert frames['monthly_invoice_result'].first().n == 1
    assert {r.invoice_line_id for r in frames['monthly_invoice_line'].collect()} == {1, 3, 300000000001, 400000000005}
    journal = frames['monthly_gl_journal_line'].collect()
    assert len(journal) == 9
    assert {r.journal_line_id for r in journal if r.journal_line_id < 10} == {1, 3}
    assert sum(r.debit_amount for r in journal) == sum(r.credit_amount for r in journal)
    balance = (ROOT / 'dbt/macros/billing_reporting.sql').read_text().split('{% endtest %}')[0].split('%}', 1)[1]
    balance = Environment(undefined=StrictUndefined).from_string(balance).render(model='report_monthly_gl_journal_line')
    assert spark.sql(balance).count() == 0
    trial = frames['gl_trial_balance'].collect()
    assert len(trial) == 4
    cash = next(r for r in trial if r.account_name == 'Cash')
    assert cash.debit_amount == D('15.40') and cash.credit_amount == D('11.10')
    closed = {r.invoice_id: r for r in frames['closed_invoice_hdr'].collect()}
    assert closed[1].period_closed_cd == 'Y' and closed[2].period_closed_cd == 'N'
    assert closed[1].prior_period_end_dt == date(2026, 10, 30)
    assert closed[1].period_key == 20261001 and closed[1].invoice_month == 10
    assert frames['currency_daily'].count() == 1 and frames['currency_totals'].count() == 1
    assert frames['period_close'].first().total_amount == D('15.40')
    assert frames['v_invoice_revenue'].count() == 2
    assert frames['v_invoice_base'].count() == 3
    assert frames['v_subscription_plans'].first().plan_code == 'PLAN      '
    assert frames['subscription_plans'].first().plan_code == 'plan'
    status = next(r for r in frames['account_status'].collect() if r.status_cd is None)
    assert status.status_cd is None and status.currency_cd is None and status.account_count == 1
    replay = build(spark)
    for name in ('monthly_invoice_hdr', 'monthly_invoice_line', 'monthly_gl_journal_line'):
        assert set(replay[name].collect()) == set(frames[name].collect())
    for name, frame in frames.items():
        frame.createOrReplaceTempView('gold_export_' + name)

    class ExportSession:
        def table(self, name):
            return spark.table(name.replace('gold_billing.', 'gold_export_'))

    export(ExportSession(), '20261109', list(REPORTS), tmp_path)
    initial = {p.name: p.read_bytes() for p in tmp_path.glob('*.psv')}
    export(ExportSession(), '20261109', list(REPORTS), tmp_path)
    assert {p.name: p.read_bytes() for p in tmp_path.glob('*.psv')} == initial
    assert initial['account_status_20261109.psv'] == (b'2026-11-09|closed|USD|1\n'
                                                    b'2026-11-09|PENDING|USD|1\n'
                                                    b'2026-11-09|||1\n')
    rows['gl_journal_line'][0]['debit_amount'] = D('6.00')
    inputs(spark, rows)
    build(spark)
    assert spark.sql(balance).count() == 1
    rows['gl_journal_line'][0]['debit_amount'] = D('5.00')
    rows['tax_rate'][0]['rate'] = D('-1.0000')
    inputs(spark, rows)
    with pytest.raises(Exception, match='DIVIDE_BY_ZERO'):
        build(spark)['monthly_gl_journal_line'].collect()
    inputs(spark, {})
    empty = build(spark)
    for name, frame in empty.items():
        assert frame.count() == (1 if name in ('gl_trial_balance', 'monthly_invoice_result') else 0)
    assert empty['monthly_invoice_result'].first().n == 0
    assert empty['gl_trial_balance'].first().debit_amount == 0


def test_report_atomic_publication(tmp_path, monkeypatch):
    path = tmp_path / 'report.psv'
    publish([{'id': 1, 'text': 'Café', 'amount': Decimal('1.20'), 'day': date(2026, 11, 9)}],
            ['id', 'text', 'amount', 'day'], path)
    assert path.read_bytes() == '1|Café|1.20|2026-11-09\n'.encode()
    old = path.read_bytes()
    for rows in ([{'id': 'bad|field'}], [{'id': 'bad\nfield'}], [{}]):
        with pytest.raises((ValueError, KeyError)):
            publish(rows, ['id'], path)
        assert path.read_bytes() == old
        assert list(tmp_path.iterdir()) == [path]
    with monkeypatch.context() as patch:
        def fail(*args):
            raise OSError('publication failed')
        patch.setattr('lakehouse.billing.reports.os.replace', fail)
        with pytest.raises(OSError, match='publication failed'):
            publish([{'id': 2}], ['id'], path)
        assert path.read_bytes() == old
        assert list(tmp_path.iterdir()) == [path]
    publish([], ['id'], path)
    assert path.read_bytes() == b''
    for name, amount in [('subscription_plans', 'monthly_fee'), ('currency_daily', 'total_amount'),
                          ('invoice_monthly', 'total_amount'), ('period_close', 'total_amount')]:
        spec = json.loads((ROOT / 'parity/specs/billing' / ('file_' + name + '.yaml')).read_text())
        row = {c: '1' for c in spec['columns']}
        row[amount] = ''
        assert compare([row], [row], spec)['passed']
    with pytest.raises(ValueError):
        export(None, '20260230', [], tmp_path)
    leap = variables('20240301', tmp_path)
    assert leap['PERIOD_START_INT'] == '1240201' and leap['PERIOD_END_INT'] == '1240229'
    year = variables('20260101', tmp_path)
    assert year['PERIOD_START_INT'] == '1251201' and year['PERIOD_END_INT'] == '1251231'


def test_billing_reporting_stage_replacement():
    nodes = {n['id']: n for n in load()['lakehouse_daily']['nodes']}
    assert nodes['dbt_billing']['selector'] == 'path:models/silver/billing'
    gold = nodes['dbt_billing_reporting']
    assert gold['selector'] == 'path:models/gold/billing' and gold['depends_on'] == ['dbt_billing']
    names = ['10_subscription_report', '11_currency_daily', '12_invoice_monthly',
             '13_period_close', '14_account_history_extract']
    for i, name in enumerate(names):
        assert 'cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/' + name in gold['legacy_objects']
        node = nodes['export_billing_' + name]
        assert 'dbt_billing_reporting' in node['depends_on']
        if i:
            assert 'export_billing_' + names[i - 1] in node['depends_on']
    for name in REPORTS:
        parity = nodes['parity_billing_file_' + name]
        assert len(parity['depends_on']) == 1
        assert nodes[parity['depends_on'][0]]['kind'] == 'export'
    for model, dependency in [('monthly_invoice_hdr', 'monthly_invoice_line'),
                               ('closed_invoice_hdr', 'monthly_invoice_hdr'),
                               ('closed_invoice_hdr', 'monthly_gl_journal_line'),
                               ('v_account_invoices', 'closed_invoice_hdr')]:
        assert "ref('" + dependency + "')" in (GOLD / (model + '.sql')).read_text()
