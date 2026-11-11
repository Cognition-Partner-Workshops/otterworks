import json
from unittest.mock import MagicMock

import pytest

from warehouse.databricks.gaps import probe_queries, run_gaps, tie_query


def client_fixture(different=False):
    client = MagicMock()
    def execute(query, *, step):
        rows = []
        if step == 'gap-qualify_ties':
            rows = [['1' if different else '0','50','49','0']]
        elif step == 'gap-format-history':
            rows = [['literal-failed-id','FAILED','YYYY-MM rejected']]
        elif step.startswith('gap-') and different:
            rows = [['9000000001','["ACTIVE      "]','["ACTIVE"]','1']]
        return {'statement_id':step+'-id','rows':rows}
    client.execute.side_effect = execute
    return client


def test_probe_scope_and_tie_policy_are_conversion_independent():
    queries = probe_queries()
    assert len(queries)==7
    assert all(obj.startswith('billing__') for obj,_ in queries.values())
    assert all('cpw.dbx_d1111_after.users__' not in q and 'cpw.dbx_d1111_after.documents__' not in q for _,q in queries.values())
    q = tie_query()
    assert 'documents__stg_doc_version' in q
    assert 'DENSE_RANK()' in q and 'array_contains(c.allowed,a.v)' in q
    assert 'VERSION_NO DESC' not in q.upper()
    assert 'n=1 AND NOT(bv <=> av)' in q


def test_fixed_probes_pass_with_different_valid_tie_candidates(tmp_path):
    results = run_gaps(client_fixture(), 'v2-fixed',tmp_path)
    assert len(results)==7 and all(r['status']=='pass' for r in results)
    tie = next(r for r in results if r['rung']=='qualify_ties')
    assert tie['detail']['different_baseline_picks']==49
    assert json.loads((tmp_path/'gaps_v2-fixed.json').read_text())==results


def test_direct_records_literal_format_failure_and_value_differences(tmp_path):
    results = run_gaps(client_fixture(True),'v1-direct',tmp_path)
    assert all(r['status']=='fail' for r in results)
    fmt = next(r for r in results if r['rung']=='format_period_key')
    assert fmt['detail']['literal_format_failure']['rows'][0][0]=='literal-failed-id'


def test_no_rows_is_pass_except_historical_direct_format_error(tmp_path):
    results = run_gaps(client_fixture(),'v1-direct',tmp_path)
    assert [r['rung'] for r in results if r['status']=='fail']==['format_period_key']


def test_missing_history_and_transport_errors_fail_closed(tmp_path):
    client=client_fixture()
    original=client.execute.side_effect
    client.execute.side_effect=lambda q,**kw: {'statement_id':'s','rows':[]} if kw['step']=='gap-format-history' else original(q,**kw)
    with pytest.raises(RuntimeError,match='missing tagged'):
        run_gaps(client,'v1-direct',tmp_path)
    client.execute.side_effect=RuntimeError('network unavailable')
    with pytest.raises(RuntimeError,match='network unavailable'):
        run_gaps(client,'v2-fixed',tmp_path)
