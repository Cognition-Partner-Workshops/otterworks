import importlib.util
import os
from decimal import Decimal
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location('billing_reports',
    Path(__file__).resolve().parents[1] / 'billing/reports.py')
REPORTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORTS)


def test_period_report_uses_requested_date_range_not_stale_flags():
    sql = REPORTS.converted_queries('20261109')['PERIOD_CLOSE']
    assert 'PERIOD_CLOSED_CD' not in sql
    assert 'BILL_DT >=' in sql and 'BILL_DT <' in sql
    assert "DATEADD(month, -1, DATE_TRUNC(month, TO_DATE('20261109','YYYYMMDD')))" in sql


@pytest.mark.skipif(os.environ.get('SFX_LIVE_PARITY') != '1', reason='Live Snowflake opt-in')
def test_live_period_report_ignores_previous_closed_month():
    from parity.connection import connect
    sql = REPORTS.converted_queries('20261109')['PERIOD_CLOSE'].replace(
        'SFX_D1110_AFTER.BILLING.INVOICE_HDR', 'invoices')
    fixture = """WITH invoices AS (SELECT column1::DATE AS BILL_DT, column2 AS CURRENCY_CD,
        column3::NUMBER(14,2) AS TOTAL_AMOUNT, 'Y' AS PERIOD_CLOSED_CD FROM VALUES
        ('2026-09-30','USD',10), ('2026-10-01','USD',20),
        ('2026-10-31','USD',30), ('2026-11-01','USD',40)) """
    with connect('period_report_regression') as sf, sf.cursor() as cursor:
        cursor.execute(fixture + sql)
        assert cursor.fetchall() == [('USD', 2, Decimal('50.00'))]
