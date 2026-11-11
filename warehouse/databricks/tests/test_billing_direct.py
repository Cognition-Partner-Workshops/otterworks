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


@pytest.mark.parametrize('version',['direct','fixed'])
def test_never_references_sibling_after_objects(version):
    sql=(Path(__file__).parents[1]/f'billing/{version}.sql').read_text()
    assert not re.search(r'cpw\.dbx_d1111_after\.(?:users|documents)__',sql)
    client=MagicMock()
    client.execute.return_value={'statement_id':'s'}
    assert run(client,sql)


@pytest.mark.parametrize('sql',[
    'DELETE FROM cpw.dbx_d1111_after.users__app_user;',
    'CREATE OR REPLACE TABLE cpw.dbx_d1111_after.documents__doc_version AS SELECT 1;',
    'INSERT INTO cpw.dbx_d1111_before.billing__subscription VALUES (1);',
])
def test_write_guard_rejects_sibling_and_baseline_mutation(sql):
    client=MagicMock()
    with pytest.raises(ValueError,match='billing-owned'):
        run(client,sql)
    client.execute.assert_not_called()


def test_fixed_semantics_and_final_tie_policy():
    sql=(Path(__file__).parents[1]/'billing/fixed.sql').read_text()
    assert 'ORDER BY VERSION_TS DESC, VERSION_NO DESC, VERSION_ID DESC)' in sql
    assert 'SELECT DISTINCT STORAGE_USAGE_ID' in sql
    assert 'rpad(substring(STATUS_CD,1,12),12' in sql
    assert 'substring(DISPLAY_NAME,1,60)' in sql
    assert 'upper(rtrim(s.PLAN_CODE))' in sql
    assert 'billing__td_date_int' in sql and 'billing__td_int_date' in sql
