import json
from unittest.mock import MagicMock

import pytest

from warehouse.databricks.parity import DOCUMENT_VERSION, RAW_DIFFERENCE, canonical, compare, encoded, hash_join, run, samples


SPEC = {"object": "billing__subscription", "keys": ["id"]}


def client_fixture(different=False, empty=False):
    client = MagicMock()
    def execute(sql, *, step):
        rows = []
        if sql.startswith("DESCRIBE"):
            rows = [["id", "bigint"], ["value", "string"]]
        elif step == "parity-count":
            rows = [[0 if empty else 1, 0 if empty else 2 if different else 1]]
        elif step == "parity-profile":
            rows = [[side, col, 0 if empty else 1, 0 if empty else 1,
                     None if empty else '1' if col == 'id' else 'a ',
                     None if empty else '1' if col == 'id' else 'a ',
                     None if empty else '1' if col == 'id' else '2']
                    for side in ['before', 'after'] for col in ['id', 'value']]
            if different:
                rows[-1][-1] = '3'
        elif step in {"parity-hash", "parity-sample"} and different:
            rows = [['["1"]', 'different_hash', ['["1","a "]'], ['["1","A"]']]]
        return {"statement_id": step + "-id", "rows": rows}
    client.execute.side_effect = execute
    return client


@pytest.mark.parametrize("empty", [False, True])
def test_equal_and_empty_tables_pass_all_rungs(empty):
    client = client_fixture(empty=empty)
    result = compare(client, SPEC)
    assert [r['status'] for r in result] == ['pass'] * 4
    assert [r['statement_id'] for r in result] == [f'parity-{r}-id' for r in ['count','profile','hash','sample']]
    assert all(not c.args[0].startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE')) for c in client.execute.call_args_list)


def test_differences_preserve_padding_case_and_column_details():
    result = compare(client_fixture(different=True), SPEC, sample_size=2)
    assert [r['status'] for r in result] == ['fail'] * 4
    assert list(result[1]['detail']) == ['value']
    assert result[3]['detail'][0]['columns'] == {'value': {'before': ['a '], 'after': ['A']}}


def test_renamed_target_keeps_original_baseline_and_scoped_replacement(tmp_path):
    client = client_fixture()
    spec = {**SPEC, 'object':'billing__in_users_app_user','before':'users__app_user'}
    run(client,'v1-direct',{'objects':[spec]},tmp_path,replace=True)
    sql = [c.args[0] for c in client.execute.call_args_list]
    assert any('DESCRIBE TABLE cpw.dbx_d1111_before.`users__app_user`'==s for s in sql)
    deletes = [s for s in sql if s.startswith('DELETE')]
    assert len(deletes)==1 and "object='billing__in_users_app_user'" in deletes[0]


def test_missing_keys_and_duplicate_rows_are_not_collapsed():
    query = hash_join('b', 'a', ['id','value'], ['id'], {'id':'bigint','value':'string'})
    assert 'FULL OUTER JOIN' in query
    assert 'missing_before' in query and 'missing_after' in query
    assert 'sort_array(collect_list(sha2(' in query
    result = samples([['["1"]', 'missing_after', '["[\\"1\\",\\"a \\"]"]', None]], ['id','value'])
    assert result[0]['columns']['value'] == {'before': ['a '], 'after': []}


def test_document_raw_differences_are_observations_not_keyed_parity(tmp_path):
    client = client_fixture(different=True)
    spec = {'object':DOCUMENT_VERSION,'before':'documents__doc_version','keys':['id']}
    rows = run(client,'v2-fixed',{'objects':[spec]},tmp_path,replace=True)
    assert rows[0]['rung']=='count' and rows[0]['status']=='fail'
    assert all(r['rung'].startswith(RAW_DIFFERENCE) and r['status']=='observed' for r in rows[1:])
    assert rows[2]['detail']['measured_values']['different_keys']==1
    assert rows[2]['detail']['raw_comparison_status']=='fail'
    deletes = [c.args[0] for c in client.execute.call_args_list if c.args[0].startswith('DELETE')]
    assert "'hash'" in deletes[0] and RAW_DIFFERENCE in deletes[0]


def test_canonical_values_are_null_safe_and_unambiguous():
    expression = encoded(['id','value'], {'id':'bigint','value':'string'})
    assert 'to_json(array(' in expression
    assert 'sha2' not in expression
    assert canonical('value','string') == 'CAST(`value` AS STRING)'
    assert not any(x in expression.lower() for x in ['trim(', 'upper(', 'lower('])


def test_receipts_written_to_delta_and_local_json(tmp_path):
    client = client_fixture()
    results = run(client, 'v1-direct', {'objects':[SPEC]}, evidence_dir=tmp_path)
    assert len(results) == 4
    saved = json.loads((tmp_path/'parity_v1-direct.json').read_text())
    assert saved[0]['statement_id'] == 'parity-count-id'
    assert all(r['receipt_statement_id'] == 'parity-results-id' for r in saved)
    writes = [c.args[0] for c in client.execute.call_args_list if c.args[0].startswith('INSERT')]
    assert len(writes) == 4
    assert all(s.startswith('INSERT INTO cpw.dbx_d1111_parity.results') for s in writes)


def test_errors_propagate_without_fabricating_pass(tmp_path):
    client = client_fixture()
    client.execute.side_effect = RuntimeError('statement failed')
    with pytest.raises(RuntimeError, match='statement failed'):
        run(client, 'bad', {'objects':[SPEC]}, evidence_dir=tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('spec', [{**SPEC,'keys':[]}, {**SPEC,'object':'x; DELETE'}, {**SPEC,'keys':['absent']}])
def test_invalid_specs_fail(spec):
    with pytest.raises(ValueError):
        compare(client_fixture(), spec)
