import os
from pathlib import Path

import pytest


@pytest.mark.skipif(os.environ.get('SFX_LIVE_PARITY') != '1', reason='Live Snowflake opt-in')
def test_query_history_runs_against_information_schema():
    from parity.connection import connect
    sql = (Path(__file__).resolve().parents[1] / 'query_history.sql').read_text()
    with connect('query_history_regression') as sf, sf.cursor() as cursor:
        cursor.execute(sql)
        assert {c[0] for c in cursor.description} == {
            'QUERY_ID', 'START_TIME', 'WAREHOUSE_NAME', 'STEP',
            'EXECUTION_STATUS', 'ROWS_PRODUCED', 'QUERY_TEXT'}
        assert cursor.fetchall()
