from datetime import datetime
from decimal import Decimal

import pytest

from lakehouse.billing.reports import publish
from lakehouse.billing.storage import export
from lakehouse.orchestration import graph, runner
from lakehouse.tests.test_audit import Models, spark
from warehouse.seed.columns import TABLES


def record(name, day='20261109', **values):
    table = next(t for t in TABLES if t.name.lower() == name)
    return tuple(values.get(c.name.lower()) for c in table.columns) + (
        datetime.strptime(day, '%Y%m%d').date(),)


@pytest.mark.parametrize('day,start,end', [
    ('20261109', '2026-11-01', '2026-12-01'),
    ('20261231', '2026-12-01', '2027-01-01'),
    ('20240229', '2024-02-01', '2024-03-01'),
])
def test_storage_month_boundaries_null_joins_and_replay(spark, day, start, end):
    models = Models(spark, day=day)
    models.feed('subscription', [record('subscription', day, customer_id='1', subscription_id='8'),
                                 record('subscription', day, customer_id='1', subscription_id='3'),
                                 record('subscription', day, customer_id=None, subscription_id='2')])
    models.feed('invoice_hdr', [record('invoice_hdr', day, customer_id='1', invoice_id='9'),
                                record('invoice_hdr', day, customer_id='1', invoice_id='4')])
    models.feed('storage_usage_daily', [record('storage_usage_daily', day, storage_usage_id=str(i),
        customer_id=customer, usage_dt=date, bytes_used=units, object_count='1')
        for i, customer, date, units in [(1, '1', start, '1073741824'), (2, '1', end, '999'),
                                         (3, '2', start, '100'), (4, None, start, '200')]])
    models.feed('usage_daily', [record('usage_daily', day, usage_id='1', usage_type='storage'),
                                record('usage_daily', day, usage_id='2', usage_type=None)])
    models.feed('invoice_line', [record('invoice_line', day, invoice_line_id='1', description='Monthly storage'),
                                 record('invoice_line', day, invoice_line_id='2', description=None)])
    first = models.rows('usage_daily_effective')
    assert {r.usage_id for r in first} == {2, 10000000001}
    generated = next(r for r in first if r.usage_id != 2)
    assert generated.units == 1073741824 and generated.subscription_id == 3
    assert str(generated.usage_dt) == datetime.strptime(day, '%Y%m%d').date().isoformat()
    lines = models.rows('invoice_line_effective')
    assert {r.invoice_line_id for r in lines} == {2, 11000000001}
    line = next(r for r in lines if r.invoice_line_id != 2)
    assert line.invoice_id == 4 and line.unit_price == line.line_amount == Decimal('0.25')
    models.built.clear()
    assert set(models.rows('usage_daily_effective')) == set(first)
    assert set(models.rows('invoice_line_effective')) == set(lines)


def test_storage_decimal_assignment_rounding_and_empty(spark):
    models = Models(spark)
    assert models.rows('usage_daily_effective') == models.rows('invoice_line_effective') == []
    models.feed('subscription', [record('subscription', customer_id='1', subscription_id='1')])
    models.feed('invoice_hdr', [record('invoice_hdr', customer_id='1', invoice_id='1')])
    for units, expected in [('21474836', '0.00'), ('21474837', '0.01'), ('-21474837', '-0.01')]:
        models.feed('storage_usage_daily', [record('storage_usage_daily', storage_usage_id='1',
            customer_id='1', usage_dt='2026-11-09', bytes_used=units, object_count='1')])
        assert models.rows('invoice_line_effective')[0].line_amount == Decimal(expected)


def test_audit_follows_actual_upstream_silver_and_shared_counts(spark):
    models = Models(spark)
    models.ref('app_user')
    def user_count():
        return spark.table(models.ref('audit_count_inputs')).where('recon_id = 20000000001').first()

    assert user_count().target_count == 0
    spark.sql('select cast(123 as bigint) as user_id').createOrReplaceTempView('audit_test_app_user')
    models.built.discard('audit_count_inputs')
    count = user_count()
    assert count.source_count == 0 and count.target_count == 1
    row = record('storage_usage_daily', storage_usage_id='1', customer_id=None,
                 usage_dt='2026-11-09', bytes_used='1')
    models.feed('storage_usage_daily', [row, row])
    shared = models.rows('shared_reconciliation')[0]
    assert (shared.source_count, shared.target_count, shared.difference_count) == (2, 1, 1)
    models.feed('audit_recon', [record('audit_recon', recon_id='21000000001', source_count='99')])
    assert spark.table(models.ref('audit_recon_final')).where('recon_id = 21000000001').count() == 1


def test_storage_atomic_export_retry_empty_and_failure(spark, tmp_path):
    path = tmp_path / 'storage_monthly.psv'
    columns = ('customer_id', 'bytes_used', 'object_count')
    spark.sql('CREATE OR REPLACE TABLE gold_documents.m_storage_totals USING DELTA AS '
              'select cast(1 as bigint) as customer_id, cast(10 as bigint) as bytes_used, '
              'cast(2 as bigint) as object_count')
    export(spark, '20261109', path)
    initial = path.read_bytes()
    export(spark, '20261109', path)
    assert path.read_bytes() == initial == b'1|10|2\n'

    def broken():
        yield dict(zip(columns, (2, 20, 3)))
        raise RuntimeError('read failed')

    with pytest.raises(RuntimeError, match='read failed'):
        publish(broken(), columns, path)
    assert path.read_bytes() == initial
    assert not list(tmp_path.glob('.storage_monthly.psv*'))
    spark.sql('DELETE FROM gold_documents.m_storage_totals')
    export(spark, '20261109', path)
    assert path.read_bytes() == b''


def test_monthly_report_consumes_storage_amount(spark):
    models = Models(spark)
    for name, values in {
        'subscription': dict(subscription_id='1', customer_id='1', plan_code='PRO'),
        'plan_catalog': dict(plan_id='1', plan_code='PRO', monthly_fee='10.00'),
        'tax_rate': dict(tax_rate_id='1', rate='0.1000'),
        'invoice_hdr': dict(invoice_id='1', customer_id='1', subscription_id='1',
                            invoice_dt='2026-11-09', tax_rate_id='1'),
        'storage_usage_daily': dict(storage_usage_id='1', customer_id='1',
                                    usage_dt='2026-11-09', bytes_used='1073741824'),
    }.items():
        models.feed(name, [record(name, **values)])
    row = models.rows('monthly_invoice_hdr')[0]
    assert (row.subtotal_amount, row.tax_amount, row.total_amount) == (
        Decimal('10.25'), Decimal('1.03'), Decimal('11.28'))


def test_storage_graph_and_base_exclusion():
    nodes = {n['id']: n for n in graph.load()['lakehouse_daily']['nodes']}
    assert nodes['dbt_billing']['exclude'] == 'tag:storage_monthly'
    assert runner.command(nodes['dbt_billing'], '.', '20261109')[-2:] == ['--exclude', 'tag:storage_monthly']
    assert set(nodes['dbt_storage_monthly']['depends_on']) == {'dbt_billing', 'dbt_documents'}
    assert 'dbt_storage_monthly' in nodes['dbt_billing_reporting']['depends_on']
    assert nodes['dbt_shared_reconcile']['depends_on'] == ['dbt_documents']
    assert 'dbt_shared_reconcile' in nodes['dbt_audit']['depends_on']
    with pytest.raises(ValueError):
        export(None, '20260230', None)
