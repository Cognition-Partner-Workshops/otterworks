import json
from unittest.mock import MagicMock

import pytest

from warehouse.databricks.gaps import conversion_ordering, probe_queries, run_gaps, tie_query


def client_fixture(different=False):
    client = MagicMock()
    def execute(query, *, step):
        rows = []
        if step == 'gap-qualify_ties':
            rows = [['1' if different else '0','50','49','0','0',
                     '50' if 'GROUP BY document_id,VERSION_TS HAVING' in query else '0']]
        elif step == 'gap-format-literal':
            raise RuntimeError('statement literal-failed-id: INCONSISTENT_BEHAVIOR_CROSS_VERSION.DATETIME_PATTERN_RECOGNITION: YYYY-MM rejected')
        elif step.startswith('gap-') and different:
            rows = [['9000000001','["ACTIVE      "]','["ACTIVE"]','1']]
        return {'statement_id':step+'-id','rows':rows}
    client.execute.side_effect = execute
    return client


def test_probe_scope_and_tie_policy_are_conversion_independent():
    queries = probe_queries()
    assert len(queries)==8
    assert all(obj.startswith('billing__') for obj,_ in queries.values())
    assert all('cpw.dbx_d1111_after.users__' not in q and 'cpw.dbx_d1111_after.documents__' not in q for _,q in queries.values())
    q = tie_query()
    assert 'documents__stg_doc_version' in q
    assert 'DENSE_RANK()' in q and 'array_contains(c.allowed,a.v)' in q
    assert 'VERSION_NO DESC,VERSION_ID DESC' in q.upper()
    assert 'n=1 AND NOT(bv <=> av)' in q


def test_fixed_probes_pass_with_different_valid_tie_candidates(tmp_path):
    results = run_gaps(client_fixture(), 'v2-fixed',tmp_path)
    assert len(results)==8 and all(r['status']=='pass' for r in results)
    tie = next(r for r in results if r['rung']=='qualify_ties')
    assert tie['detail']['different_baseline_picks']==49
    assert json.loads((tmp_path/'gaps_v2-fixed.json').read_text())==results


def test_direct_records_literal_format_failure_and_value_differences(tmp_path):
    results = run_gaps(client_fixture(True),'v1-direct',tmp_path)
    assert all(r['status']=='fail' for r in results)
    fmt = next(r for r in results if r['rung']=='format_period_key')
    assert fmt['detail']['literal_format_failure']['rows'][0][0]=='literal-failed-id'


def test_no_value_diffs_does_not_hide_unresolved_direct_ordering(tmp_path):
    results = run_gaps(client_fixture(),'v1-direct',tmp_path)
    assert [r['rung'] for r in results if r['status']=='fail']==['qualify_ties','format_period_key']


def test_fresh_warehouse_needs_no_query_history(tmp_path):
    client=client_fixture()
    results=run_gaps(client,'v2-fixed',tmp_path,rungs=['format_period_key'])
    assert results[0]['status']=='pass'
    assert results[0]['detail']['literal_format_failure']['statement_id']=='literal-failed-id'
    assert all('system.query.history' not in c.args[0] for c in client.execute.call_args_list)


@pytest.mark.parametrize('error',[None,RuntimeError('network unavailable')])
def test_literal_unexpected_success_and_transport_errors_fail_closed(tmp_path,error):
    client=client_fixture()
    original=client.execute.side_effect
    def execute(query,**kwargs):
        if kwargs['step']=='gap-format-literal':
            if error:
                raise error
            return {'statement_id':'s','rows':[]}
        return original(query,**kwargs)
    client.execute.side_effect=execute
    with pytest.raises(RuntimeError,match='network unavailable' if error else 'unexpectedly succeeded'):
        run_gaps(client,'v2-fixed',tmp_path,rungs=['format_period_key'])


def test_document_scope_preserves_unrelated_gap_receipts(tmp_path):
    original = run_gaps(client_fixture(), 'v2-fixed', tmp_path)
    client = client_fixture()
    refreshed = run_gaps(client, 'v2-fixed', tmp_path, objects=['billing__in_documents_doc_version'])
    steps = [c.kwargs['step'] for c in client.execute.call_args_list if c.kwargs['step'].startswith('gap-')]
    assert steps == ['gap-qualify_ties', 'gap-untied_exact']
    assert next(r for r in refreshed if r['rung']=='char_padding') == original[0]
    assert 'EXCEPT ALL' in probe_queries()['untied_exact'][1]


def test_final_rule_violation_fails_even_for_valid_candidate(tmp_path):
    client = client_fixture()
    original = client.execute.side_effect
    def execute(query, **kwargs):
        if kwargs['step']=='gap-qualify_ties':
            return {'statement_id':'tie-id','rows':[['0','50','49','0','1','0']]}
        return original(query, **kwargs)
    client.execute.side_effect = execute
    results = run_gaps(client,'v2-fixed',tmp_path,objects=['billing__in_documents_doc_version'])
    assert next(r for r in results if r['rung']=='qualify_ties')['status']=='fail'


def test_ordering_keys_come_from_actual_conversion_and_probe_is_scoped(tmp_path):
    assert conversion_ordering('v1-direct') == ['VERSION_TS']
    assert conversion_ordering('v2-fixed') == ['VERSION_TS','VERSION_NO','VERSION_ID']
    for label, expected in [('v1-direct',50),('v2-fixed',0)]:
        client = client_fixture()
        rows = run_gaps(client,label,tmp_path,rungs=['qualify_ties'])
        assert len(rows)==1
        assert rows[0]['detail']['unresolved_tied_documents']==expected
        assert rows[0]['status']==('fail' if expected else 'pass')
        measured = [c.kwargs['step'] for c in client.execute.call_args_list if c.kwargs['step'].startswith('gap-')]
        assert measured==['gap-qualify_ties']
