"""Offline close execution and strict comparison regression tests."""
from decimal import Decimal
import datetime as dt
from pathlib import Path
import sys

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'billing'))
from close_parity import compare, markdown
from duckdb_close import business_day, execute_sql, load_landing, run, SQL
from warehouse.seed.generate import generate


def test_compare_normal_empty_and_duplicate_rows():
    columns = ['INVOICE_ID', 'CURRENCY_CD', 'TOTAL_AMOUNT']
    assert compare(columns, [], [])['passed']
    row = (1, 'USD', Decimal('1.20'))
    assert compare(columns, [row], [('1', 'USD', '1.2')])['passed']
    result = compare(columns, [row, row], [row])
    assert result['hash_differences'] == 1
    assert not result['money_equal']
    assert '| FAIL |' in markdown({'invoice': result})
    assert not compare(['ID', 'ACCOUNT_NUMBER'], [(1, '001')], [(1, '1')])['passed']
    assert not compare(columns, [row], [(1, 'usd', Decimal('1.20'))])['passed']


def test_invalid_date_and_malformed_landing(tmp_path):
    with pytest.raises(ValueError):
        business_day('20260230')
    landing = tmp_path / 'landing'
    path = landing / 'billing/CUSTOMER_ACCOUNT/20261109.psv'
    path.parent.mkdir(parents=True)
    path.write_text('1|too few\n', encoding='utf-8')
    with duckdb.connect() as conn:
        conn.execute('CREATE SCHEMA BILLING')
        execute_sql(conn, (SQL / '00_tables.sql').read_text(), '20261109')
        with pytest.raises(ValueError, match='column count'):
            load_landing(conn, landing, '20261109')


def test_hash_normalization_preserves_real_differences():
    columns = ['INVOICE_ID', 'CURRENCY_CD', 'TOTAL_AMOUNT', 'POSTING_TS', 'RUN_DT']
    before = [(1, 'USD   ', Decimal('1.50'), dt.datetime(2026, 11, 9, 12), dt.date(2026, 11, 9))]
    after = [('1', 'USD', '1.5', '2026-11-09T12:00:00.000000', '2026-11-09')]
    result = compare(columns, before, after)
    assert result['passed']
    assert result['strict_hash_differences'] == 2
    assert result['money_equal']
    for index, different in [(1, 'usd'), (1, ' USD'), (1, 'US D'), (1, 'USD\t'),
                             (2, '1.51'), (3, '2026-11-09T12:00:01'), (4, '2026-11-10')]:
        changed = list(after[0])
        changed[index] = different
        assert not compare(columns, before, [changed])['passed']
    assert not compare(['TEXT'], [(None,)], [('',)])['passed']


def test_offline_seeded_close(tmp_path):
    landing, output = tmp_path / 'landing', tmp_path / 'output'
    generate(8, 1110, landing, '20261109')
    run(landing, '20261109', output)
    for name in ['invoice_monthly', 'gl_trial_balance', 'period_close', 'invoice_periods']:
        assert (output / (name + '.psv')).exists()
    assert (output / 'inputs.json').exists()
    with duckdb.connect(str(output / 'close.duckdb'), read_only=True) as conn:
        assert conn.execute('SELECT COUNT(*) FROM BILLING.INVOICE_HDR').fetchone()[0] > 0
        assert conn.execute('SELECT COUNT(*) FROM PC_BILLING.GL_JOURNAL_LINE').fetchone()[0] > 0
        assert conn.execute('SELECT COUNT(*) FROM BILLING.INVOICE_LINE WHERE DESCRIPTION=\'Monthly subscription\'').fetchone()[0] > 0
