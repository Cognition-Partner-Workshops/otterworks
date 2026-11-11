from pathlib import Path
import re
from unittest.mock import MagicMock

import pytest

from warehouse.databricks.billing.run import run


def test_runner_tags_every_statement_and_stops_on_error():
    client = MagicMock()
    client.execute.side_effect = [{'statement_id':'s1'}, RuntimeError('failed')]
    with pytest.raises(RuntimeError, match='failed'):
        run(client, 'SELECT 1; SELECT 2; SELECT 3;')
    assert [c.kwargs['step'] for c in client.execute.call_args_list] == ['direct-1','direct-2']


def test_empty_runner_and_receipts():
    client = MagicMock()
    assert run(client, ' ') == []
    client.execute.return_value = {'statement_id':'s1'}
    assert run(client,'SELECT 1;')[0]['statement_id'] == 's1'


def test_only_staging_inputs_and_commented_objects():
    path = Path(__file__).parents[1]/'billing/direct.sql'
    sql = path.read_text()
    before = re.findall(r'cpw\.dbx_d1111_before\.(\w+)', sql)
    assert before and all('__stg_' in name for name in before)
    client = MagicMock()
    client.execute.return_value = {'statement_id':'s1'}
    for receipt in run(client, sql):
        statement = receipt['sql']
        if statement.startswith('CREATE'):
            assert "COMMENT 'run_token=dbx-d1111 expires=2026-11-24'" in statement
    assert 'ORDER BY VERSION_TS DESC)' in sql
    assert 'SELECT DISTINCT' not in sql
