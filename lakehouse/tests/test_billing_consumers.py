import io
import json
import os
import subprocess
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from psycopg import sql
from pyspark.sql import functions as F

from lakehouse.billing import consumer_queries as cq
from lakehouse.billing.consumer_exports import (CASEFOLD, NUMERIC, atomic_bytes, comparison_rows, invoice_csv, partner_csv,
                                                publish_partner, workbook_rows)
from lakehouse.billing.consumer_reference import legacy_rows, source_invoice_export
from lakehouse.runtime.layout import ROOT
from lakehouse.runtime.session import create_session
from lakehouse.orchestration.graph import load
from warehouse.teradata.bteq import Runner


INPUTS = {
    'CUSTOMER_ACCOUNT': "select 1L customer_id, 'A1' account_number, 'Acme' account_name, 'US' region_cd, 'ACTIVE' status_cd, date'2025-01-01' created_dt",
    'SUBSCRIPTION': "select 1L subscription_id, 1L customer_id, 'Team' plan_code, 'Active' status_cd",
    'PLAN_CATALOG': "select 'Team' plan_code, 'Team Plan' plan_name",
    'INVOICE_HDR': "select 1L invoice_id, 1L customer_id, 1L subscription_id, 'INV-1' invoice_number, date'2026-11-09' invoice_dt, date'2026-11-09' bill_dt, 'USD' currency_cd, cast(10 as decimal(14,2)) total_amount, cast(1 as decimal(14,2)) tax_amount, cast(9 as decimal(14,2)) subtotal_amount union all select 2L,1L,1L,'INV-2',date'2026-08-01',date'2026-11-09','USD',10,1,9",
    'PAYMENT': "select 1L invoice_id, 1L customer_id, date'2026-11-09' payment_dt, cast(2 as decimal(14,2)) amount",
    'CREDIT_NOTE': "select date'2026-11-09' credit_dt, cast(1 as decimal(14,2)) amount",
    'GL_ACCOUNT': "select 1L gl_account_id, '1200' account_number",
    'GL_JOURNAL_LINE': "select 1L gl_account_id, date'2026-11-09' posting_dt, cast(10 as decimal(14,2)) debit_amount, cast(0 as decimal(14,2)) credit_amount",
}


@pytest.fixture(scope='module')
def spark(tmp_path_factory):
    previous = os.environ.get('NS')
    os.environ['NS'] = 'test-billing-consumers-' + uuid.uuid4().hex
    session = create_session()
    yield session
    session.stop()
    if previous is None:
        os.environ.pop('NS', None)
    else:
        os.environ['NS'] = previous


@pytest.fixture
def inputs(spark, monkeypatch):
    frames = {name: spark.sql(query) for name, query in INPUTS.items()}
    frames['V_ACCOUNT_INVOICES'] = frames['INVOICE_HDR']
    frames['V_INVOICE_BASE'] = frames['INVOICE_HDR']
    mapping = {name: 'consumer_' + name.lower() for name in frames}
    for name, frame in frames.items():
        frame.createOrReplaceTempView(mapping[name])
    monkeypatch.setattr(cq, 'TABLES', mapping)
    return frames


@pytest.mark.parametrize('name,count', zip(cq.SOURCES, [2, 1, 1, 1, 12, 1, 0, 2]))
def test_consumer_queries(spark, inputs, name, count):
    result = cq.query(spark, name, '20261109')
    assert result.count() == count
    if name == 'legacy_aging':
        row = result.first()
        assert row.OPEN_BALANCE == 18 and row.CURRENT_AMT == 8 and row.DAYS_61_90 == 10
    if name == 'analytics_rollups':
        november = result.where("MONTH_LABEL='2026-11'").first()
        assert november.BILLED_REVENUE == 9 and november.COLLECTED_CASH == 2


@pytest.mark.parametrize('name', cq.SOURCES)
def test_empty_consumer_queries(spark, inputs, name):
    for table, frame in inputs.items():
        frame.limit(0).createOrReplaceTempView(cq.TABLES[table])
    rows = cq.query(spark, name, '20261109').collect()
    assert len(rows) == (1 if name in ('admin_summary', 'report_summary') else 0)
    if rows:
        assert all(value == 0 for k, value in rows[0].asDict().items() if k.lower() != 'period_id')


@pytest.mark.skipif(os.environ.get('SFX_LH_BILLING_CONSUMER_NATIVE_TEST') != '1', reason='Requires local legacy emulator')
def test_legacy_clock_boundary_and_matching_queries(spark, inputs):
    extra = (inputs['INVOICE_HDR'].where('invoice_id=1').withColumn('invoice_id', F.lit(3).cast('bigint'))
             .withColumn('invoice_number', F.lit('INV-3')).withColumn('currency_cd', F.lit('usd')))
    invoices = inputs['INVOICE_HDR'].unionByName(extra)
    for name in ('INVOICE_HDR', 'V_ACCOUNT_INVOICES', 'V_INVOICE_BASE'):
        inputs[name] = invoices
        invoices.createOrReplaceTempView(cq.TABLES[name])
    with Runner(output=io.StringIO()) as runner:
        types = {'bigint': 'bigint', 'string': 'text', 'date': 'date'}
        for name, frame in inputs.items():
            columns = sql.SQL(',').join(sql.Composed([sql.Identifier(f.name), sql.SQL(' '),
                                        sql.SQL(types.get(f.dataType.simpleString(), f.dataType.simpleString())),
                                        sql.SQL(' COLLATE sfx_td.ci' if f.name.upper() in ('STATUS_CD', 'PLAN_CODE', 'CURRENCY_CD') else '')])
                                        for f in frame.schema)
            runner.conn.execute(sql.Composed([sql.SQL('CREATE TEMP TABLE '), sql.Identifier('consumer_' + name.lower()),
                                             sql.SQL(' ('), columns, sql.SQL(')')]))
            for row in frame.collect():
                runner.conn.execute(sql.Composed([sql.SQL('INSERT INTO '), sql.Identifier('consumer_' + name.lower()),
                                    sql.SQL(' VALUES ('), sql.SQL(',').join(sql.Placeholder() for _ in row), sql.SQL(')')]), tuple(row))
        original = cq.bound_query

        def bound(*args, **kwargs):
            result = original(*args, **kwargs)
            for name in sorted(inputs, key=len, reverse=True):
                result = result.replace('SFX_BILLING.' + name, 'pg_temp.consumer_' + name.lower())
            return result

        with patch('lakehouse.billing.consumer_reference.bound_query', side_effect=bound):
            for name in cq.SOURCES:
                for clock in ('20261109', '20261110', '20270115'):
                    left = comparison_rows(legacy_rows(runner, name, '20261109', clock))
                    frame = cq.query(spark, name, '20261109', clock)
                    right = comparison_rows([dict(zip([c.lower() for c in frame.columns], r)) for r in frame.collect()])
                    assert len(left) == len(right), (name, clock)
                    for a, b in zip(left, right):
                        for key in a:
                            if a[key] is None:
                                assert b[key] is None
                            elif key in ('open_ratio', 'dso'):
                                assert abs(Decimal(str(a[key])) - Decimal(str(b[key]))) < Decimal('.000001')
                            elif key in NUMERIC:
                                assert Decimal(str(a[key])) == Decimal(str(b[key]))
                            elif key in CASEFOLD:
                                assert str(a[key]).strip().casefold() == str(b[key]).strip().casefold()
                            else:
                                assert str(a[key]).strip() == str(b[key]).strip(), (name, clock, key, a[key], b[key])
            assert legacy_rows(runner, 'partner_rows', '20261109', '20261109') == []
            assert len(legacy_rows(runner, 'partner_rows', '20261109', '20261110')) == 3
            assert len(legacy_rows(runner, 'report_unreconciled', '20261109', '20270115')) == 2


@pytest.mark.parametrize('raw', ['', 'INV-1,A1,2026-11-09,.10,.00,-.10,USD\n',
                                'INV-1,ACC-1,2026-11-09,-0.00,0.00,0.00,USD\n'])
def test_partner_postprocess_against_actual_script(tmp_path, raw):
    source, output = tmp_path / 'raw.csv', tmp_path / 'native.csv'
    source.write_text(raw)
    subprocess.run(['bash', str(ROOT.parent / 'consumers/partner-extract/bin/postprocess.sh'), str(source), str(output)], check=True)
    assert partner_csv(raw) == output.read_bytes()


@pytest.mark.parametrize('money', ['1.001', 'NaN', 'oops', '999999999999.00'])
def test_malformed_money_preserves_previous(tmp_path, money):
    good = 'INV-1,A1,2026-11-09,1.00,0.00,1.00,USD\n'
    current = publish_partner(good, tmp_path, '20261109')
    previous = current.resolve()
    with pytest.raises(ValueError):
        publish_partner(good.replace('1.00', money), tmp_path, '20261109')
    assert current.resolve() == previous


def test_duplicate_and_atomic_publication_errors(tmp_path, monkeypatch):
    raw = 'INV-1,A1,2026-11-09,1.00,0.00,1.00,USD\n'
    current = publish_partner(raw, tmp_path, '20261109')
    previous = current.resolve()
    for arguments in [dict(raw=raw * 2), dict(raw=raw, dry_run=False), dict(raw=raw, remote='bad\npath')]:
        with pytest.raises(ValueError):
            publish_partner(root=tmp_path, day='20261109', **arguments)
        assert current.resolve() == previous
    real = os.replace

    def fail(source, target):
        if Path(target).name == 'current':
            raise OSError('injected publication failure')
        return real(source, target)

    monkeypatch.setattr(os, 'replace', fail)
    with pytest.raises(OSError):
        publish_partner(raw.replace('INV-1', 'INV-2'), tmp_path, '20261109')
    assert current.resolve() == previous
    assert json.loads((current / 'transfer.json').read_text())['mode'] == 'simulated'


def test_invoice_csv_source_and_duplicates(tmp_path):
    row = dict(zip(('invoice_no', 'customer_name', 'account_no', 'invoice_date', 'currency_cd',
                    'amount_due', 'tax_amt', 'open_balance'), ['INV-1', 'A, "Name"', ' A1 ', date(2026, 11, 9), ' USD ', '1.00', '.10', '.90']))
    for rows in ([], [row], [row, row]):
        path = tmp_path / 'invoices.csv'
        source_invoice_export(rows, path)
        assert invoice_csv(rows) == path.read_bytes()
    for value in ['oops', '1,000.00']:
        with pytest.raises(Exception):
            invoice_csv([dict(row, amount_due=value)])
    with pytest.raises(ValueError):
        invoice_csv([row] * 100001)
    with pytest.raises(RuntimeError):
        source_invoice_export([row] * 100001, tmp_path / 'overflow.csv')


def test_atomic_bytes_and_bi_contract(tmp_path, monkeypatch):
    path = tmp_path / 'status.psv'
    atomic_bytes(path, b'2026-11-09|||2\n')
    assert workbook_rows(path) == [dict(business_date='2026-11-09', account_status=None, currency_code=None, account_count=2)]
    monkeypatch.setattr(os, 'replace', lambda *args: (_ for _ in ()).throw(OSError('failure')))
    with pytest.raises(OSError):
        atomic_bytes(path, b'broken')
    assert workbook_rows(path)[0]['account_count'] == 2
    path.write_text('2026-11-09|A|USD|9223372036854775808\n')
    with pytest.raises(ValueError):
        workbook_rows(path)


def test_consumer_parameters_and_cron_replacement():
    graph = load()
    node = next(n for n in graph['lakehouse_daily']['nodes'] if n['id'] == 'export_billing_consumers')
    assert 'export_billing_14_account_history_extract' in node['depends_on']
    cron = graph['lakehouse_billing_partner_extract']
    assert cron['schedule'] == '15 2 * * *' and cron['timezone'] == 'UTC' and cron['paused']
    assert '--partner-only' in next(n for n in cron['nodes'] if n['id'] == 'run')['command']
    for value in ('20190101', '20260230', 'invalid'):
        with pytest.raises(ValueError):
            cq.bound_query('partner_rows', value)
    with pytest.raises(ValueError):
        cq.bound_query('analytics_rollups', '20261109', status='')
    assert "x'' OR 1=1" in cq.bound_query('analytics_rollups', '20261109', plan="x' OR 1=1")
    assert "'A?'" in cq.bound_query('analytics_rollups', '20261109', status='A?', plan='Team')
