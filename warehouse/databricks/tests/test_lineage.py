import json
from unittest.mock import MagicMock

import pytest

from warehouse.databricks.lineage import compare_sets, dependencies, leaves, run, source_graph


def test_sql_dependencies_and_cycle_safe_leaf_inputs():
    target, parents = dependencies('INSERT INTO SFX_BILLING.INVOICE_HDR SELECT * FROM SFX_BILLING.STG_INVOICE_HDR')
    assert target=='sfx_billing.invoice_hdr'
    assert parents=={'sfx_billing.stg_invoice_hdr'}
    assert leaves({'a':{'b','input'},'b':{'a','other'}},'a')=={'input','other'}
    assert leaves({},'empty')=={'empty'}


def source_fixture():
    source = MagicMock()
    def execute(query):
        cursor=MagicMock()
        if 'dbc.dbc_qrylog' in query:
            rows=[(1,'INSERT INTO SFX_BILLING.PAYMENT SELECT * FROM SFX_BILLING.STG_PAYMENT',
                   'SFX_BILLING','PAYMENT','WRITE'),
                  (1,'INSERT INTO SFX_BILLING.PAYMENT SELECT * FROM SFX_BILLING.STG_PAYMENT',
                   'SFX_BILLING','STG_PAYMENT','READ')]
        else:
            rows=[]
        cursor.fetchall.return_value=rows
        return cursor
    source.execute.side_effect=execute
    return source


def test_normalization_empty_uc_and_mismatched_inputs():
    spec={'objects':[{'object':'billing__payment'}]}
    graph={'sfx_billing.payment':{'sfx_billing.stg_payment'}}
    assert compare_sets(spec,graph,[])[0]['status'].startswith('empty')
    result=compare_sets(spec,graph,[['cpw.dbx_d1111_after.billing__payment','cpw.dbx_d1111_before.billing__stg_payment']])[0]
    assert result['status']=='match' and result['direct_upstream_match']
    assert compare_sets(spec,graph,[['cpw.dbx_d1111_after.billing__payment','cpw.dbx_d1111_before.billing__stg_tax_rate']])[0]['status']=='different'


def test_lineage_receipts_and_prior_empty_measurement_preserved(tmp_path):
    client=MagicMock()
    client.execute.return_value={'statement_id':'uc-first','rows':[]}
    spec={'objects':[{'object':'billing__payment'}]}
    path=tmp_path/'lineage.md'
    first=run(source_fixture(),client,spec,[{'statement_id':'fixed-id'}],path)
    assert first['objects'][0]['status'].startswith('empty')
    client.execute.return_value={'statement_id':'uc-second','rows':[
        ['cpw.dbx_d1111_after.billing__payment','cpw.dbx_d1111_before.billing__stg_payment','fixed-id',True]]}
    second=run(source_fixture(),client,spec,[{'statement_id':'fixed-id'}],path)
    assert second['objects'][0]['status']=='match'
    assert second['previous_uc_measurements'][0]['response']['statement_id']=='uc-first'
    assert 'uc-second' in path.read_text()
    assert json.loads(path.with_suffix('.json').read_text())['uc_response']['statement_id']=='uc-second'
    assert client.execute.call_args.kwargs['step']=='lineage-upstream'


def test_no_dbql_and_query_errors_are_not_fabricated_matches():
    source=MagicMock()
    source.execute.return_value.fetchall.return_value=[]
    with pytest.raises(RuntimeError,match='DBQL exists'):
        source_graph(source)
    source.execute.side_effect=RuntimeError('source unavailable')
    with pytest.raises(RuntimeError,match='source unavailable'):
        source_graph(source)
