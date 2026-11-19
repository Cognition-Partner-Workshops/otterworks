import os
import shutil
import uuid
from datetime import date, datetime, timedelta

import pytest
import yaml
from jinja2 import Environment, StrictUndefined
from pyspark.sql import types as T

from lakehouse.audit.export import publish
from lakehouse.orchestration.graph import load
from lakehouse.parity.engine import compare
from lakehouse.parity.readers import Readers
from lakehouse.runtime.layout import ROOT, data_root
from lakehouse.runtime.session import create_session
from warehouse.seed.columns import TABLES


DAY = '20261109'
MODELS = {path.stem: path for layer in ('silver', 'gold')
          for path in (ROOT / 'dbt/models' / layer / 'audit').glob('*.sql')}


@pytest.fixture(scope='module')
def spark():
    original = os.environ.get('NS')
    os.environ['NS'] = 'test-audit-' + uuid.uuid4().hex
    session = create_session()
    yield session
    session.stop()
    shutil.rmtree(data_root())
    if original is None:
        del os.environ['NS']
    else:
        os.environ['NS'] = original


class Models:
    def __init__(self, spark, enabled=False):
        self.spark = spark
        self.enabled = enabled
        self.built = set()
        for table in TABLES:
            self.feed(table.name.lower(), [])
        spark.sql("select cast(null as bigint) as customer_id where false").createOrReplaceTempView(
            'audit_test_customer_account')

    def feed(self, name, rows):
        table = next(t for t in TABLES if t.name.lower() == name)
        schema = T.StructType([T.StructField(c.name.lower(), T.StringType()) for c in table.columns]
                              + [T.StructField('_business_date', T.DateType())])
        self.spark.createDataFrame(rows, schema).createOrReplaceTempView('audit_source_' + name)
        self.built.clear()

    def ref(self, name):
        target = 'audit_test_' + name
        if name not in MODELS or name in self.built:
            return target
        environment = Environment(undefined=StrictUndefined)
        sql = environment.from_string(
            (ROOT / 'dbt/macros/legacy_text.sql').read_text()
            + (ROOT / 'dbt/macros/audit_timestamp.sql').read_text() + MODELS[name].read_text()
        ).render(source=lambda domain, table: 'audit_source_' + table,
                 ref=self.ref, env_var=lambda _: DAY, config=lambda **_: '',
                 var=lambda name, default: self.enabled)
        self.spark.sql(sql).createOrReplaceTempView(target)
        self.built.add(name)
        return target

    def rows(self, name):
        return self.spark.table(self.ref(name)).collect()


def test_audit_empty_inputs(spark):
    models = Models(spark)
    for table in TABLES:
        if table.area == 'audit':
            assert models.rows(table.name.lower()) == []
    for name in ('stg_audit_event', 'audit_summary_final', 'v_event_actors', 'm_archive_overview'):
        assert models.rows(name) == []
    counts = models.rows('audit_recon_final')
    assert len(counts) == 37
    assert all(row.source_count == row.target_count == row.difference_count == 0 for row in counts)


@pytest.mark.parametrize('table', [t for t in TABLES if t.area == 'audit'
                                  and t.name != 'AUDIT_EVENT_ARCHIVE'], ids=lambda t: t.name)
def test_audit_load_types_widths_nulls_and_date(spark, table):
    models = Models(spark)
    values = [{'B': '1', 'I': '2', 'D': '2026-11-09', 'T': '2026-11-09 12:13:14'}.get(
        column.kind, 'MiXeD ' * 50) for column in table.columns]
    current = date(2026, 11, 9)
    models.feed(table.name.lower(), [tuple(values) + (current,),
                                   tuple(['99'] + values[1:]) + (current-timedelta(days=1),)])
    result = models.rows(table.name.lower())
    assert len(result) == 1
    for column, value in zip(table.columns, result[0]):
        if column.kind[0] in 'CV':
            width = int(column.kind[1:])
            assert value == values[list(table.columns).index(column)][:width]
        elif column.kind == 'B':
            assert value == 1
        elif column.kind == 'I':
            assert value == 2
    models.feed(table.name.lower(), [tuple(['1'] + [None]*(len(values)-1)) + (current,)])
    assert tuple(models.rows(table.name.lower())[0])[1:] == tuple([None]*(len(values)-1))
    values[0] = 'invalid-key'
    models.feed(table.name.lower(), [tuple(values) + (current,)])
    with pytest.raises(Exception, match='CAST_INVALID_INPUT'):
        models.rows(table.name.lower())


def test_daily_chain_does_not_apply_informatica_transformations(spark):
    models = Models(spark)
    models.feed('audit_event', [('1', '2', '-3', '-4', '2026-11-09 01:00:00',
                                ' doc_export ', '', date(2026, 11, 9))])
    event = models.rows('audit_event')[0]
    assert event.document_id == -3 and event.customer_id == -4
    assert event.event_type == ' doc_export ' and event.details == ''
    models.feed('security_alert', [('1', '2', '3', '2026-11-09 01:00:00',
                                   'HIGH', 'OPEN', date(2026, 11, 9)),
                                  ('2', None, None, None, 'UNKNOWN', 'OPEN', date(2026, 11, 9))])
    alerts = sorted(models.rows('security_alert'), key=lambda row: row.alert_id)
    assert alerts[0].status_cd == 'OPEN        '
    assert alerts[1].severity_cd == 'UNKNOWN     '


def test_audit_timestamp_rounding(spark):
    models = Models(spark)
    models.feed('audit_event', [
        ('1', None, None, None, '2026-11-09 23:59:59.500000', 'A', '', date(2026, 11, 9)),
        ('2', None, None, None, '2026-11-09 01:00:00.499999', 'A', '', date(2026, 11, 9))])
    rows = sorted(models.rows('audit_event'), key=lambda row: row.event_id)
    assert rows[0].event_ts == datetime(2026, 11, 10)
    assert rows[1].event_ts == datetime(2026, 11, 9, 1)


def test_summary_final_and_archive_gate(spark):
    models = Models(spark, enabled=True)
    current = date(2026, 11, 9)
    cutoff = current-timedelta(days=2555)
    models.feed('audit_event', [
        ('1', '2', '3', '4', '2026-11-09 12:00:00', 'DOC_EXPORT', '', current),
        ('2', '2', '3', '4', datetime.combine(cutoff-timedelta(days=1), datetime.min.time()).isoformat(' '), 'OLD', '', current),
        ('3', '2', '3', '4', datetime.combine(cutoff, datetime.min.time()).isoformat(' '), 'BOUNDARY', '', current)])
    models.feed('audit_daily_summary', [('1', '2026-11-09', '4', '7', '3', current),
                                      ('10000000001', '2026-11-08', '4', '9', '1', current)])
    rows = sorted(models.rows('audit_summary_final'), key=lambda row: row.summary_id)
    assert [(r.summary_id, r.event_count, r.export_count) for r in rows] == [(1, 7, 3), (10000000004, 1, 0)]
    archived = models.rows('audit_event_archive')
    assert len(archived) == 1 and archived[0].event_type == 'OLD         '
    models.enabled = False
    models.built.clear()
    assert models.rows('audit_event_archive') == []


def test_external_base_selection_rules(spark):
    models = Models(spark)
    current = date(2026, 11, 9)
    models.feed('doc_version', [('1', '5', '1', '2026-11-08 01:00:00', '1', 'a', current),
                               ('2', '5', '2', '2026-11-09 01:00:00', '2', 'b', current)])
    assert [row.version_id for row in models.rows('audit_doc_versions')] == [2]
    storage = ('1', '4', '2', '2026-11-09', '10', '1', current)
    models.feed('storage_usage_daily', [storage, storage])
    assert len(models.rows('audit_input_storage_usage_daily')) == 1
    models.feed('login_event', [('1', '2', '2026-11-09 01:00:00', 'OK', 'WEB', current),
                               ('2', '2', '2026-11-09 02:00:00', 'OK', 'WEB', current)])
    assert models.rows('audit_users_activity')[0].login_count == 2


def test_external_monthly_invoice_case_insensitive_plan_join(spark):
    models = Models(spark)

    def record(name, **values):
        table = next(t for t in TABLES if t.name.lower() == name)
        return tuple(values.get(c.name.lower()) for c in table.columns) + (date(2026, 11, 9),)

    models.feed('invoice_hdr', [record('invoice_hdr', invoice_id='1',
                                     subscription_id='2', invoice_dt='2026-11-09')])
    models.feed('subscription', [record('subscription', subscription_id='2', plan_code='pRo')])
    models.feed('plan_catalog', [record('plan_catalog', plan_id='1', plan_code='PRO'),
                                 record('plan_catalog', plan_id='2', plan_code='pro ')])
    assert len(models.rows('audit_invoice_line_keys')) == 2
    models.feed('usage_daily', [record('usage_daily', usage_id='1'),
                               record('usage_daily', usage_id='2', usage_type='storage')])
    assert [row.usage_id for row in models.rows('audit_usage_keys')] == [1]


def test_audit_graph_dependencies_and_exports():
    nodes = {node['id']: node for node in load()['lakehouse_daily']['nodes']}
    assert set(nodes['dbt_audit']['depends_on']) == {
        'bronze_audit', 'bronze_users', 'bronze_documents', 'dbt_billing'}
    assert nodes['export_audit_reconciliation']['depends_on'] == ['dbt_audit']
    assert nodes['parity_audit_reconciliation_export']['depends_on'] == ['export_audit_reconciliation']
    for node in nodes.values():
        if node['kind'] == 'parity' and node['spec'].startswith('audit.') and node['spec'] != 'audit.reconciliation_export':
            if node['spec'].startswith('audit.spark_'):
                assert node['depends_on'] == (['audit_delta_optimize'] if node['spec'].endswith(
                    'lake_compaction_audit') else ['audit_spark'])
            elif node['spec'].startswith('audit.stg_') and node['spec'] != 'audit.stg_audit_event':
                assert node['depends_on'] == ['bronze_audit']
            else:
                assert node['depends_on'] == ['dbt_audit']


def test_export_empty_retry_and_failure(tmp_path):
    target = tmp_path / '20261109/reconciliation.psv'
    publish([(1, 2, 3, -1)], target)
    first = target.read_bytes()
    publish([(1, 2, 3, -1)], target)
    assert target.read_bytes() == first == b'1|2|3|-1\n'

    def failed_rows():
        yield (2, 3, 4, -1)
        raise RuntimeError('read failed')

    with pytest.raises(RuntimeError, match='read failed'):
        publish(failed_rows(), target)
    assert target.read_bytes() == first
    assert not list(target.parent.glob('.reconciliation-*'))
    publish([], target)
    assert target.read_bytes() == b''


def test_export_null_counts(tmp_path):
    target = tmp_path / 'reconciliation.psv'
    publish([(1, None, 3, None)], target)
    assert target.read_bytes() == b'1||3|\n'
    spec = yaml.safe_load((ROOT / 'parity/specs/audit/reconciliation_export.yaml').read_text())
    lakehouse, columns = Readers(DAY).read(dict(spec['lakehouse'], path=str(target)))
    legacy = [dict(zip(columns, (1, None, 3, None)))]
    assert compare(legacy, lakehouse, spec, columns, columns)['passed']
