import duckdb
import pytest

from parity.documents_decisions import version_scope
from parity.ladder import local_compare
from parity.object_board import documents_apply_deviation as apply_deviation, documents_apply_storage


@pytest.mark.parametrize('populated', [False, True])
@pytest.mark.parametrize('failed', [False, True])
def test_storage_amber_spreads_only_from_proven_single_writer(populated, failed):
    from parity.owner_decisions import decision_registry
    decision = next(d for d in decision_registry() if d.get('decision_id') == 'documents-storage-finance-confirmation')
    rows = [dict(name=name, subject_area='billing' if 'SFX_BILLING.' in name else 'documents',
                 status='red' if 'SFX_BILLING.' in name or failed else 'green') for name in decision['blocks']]
    measurement = dict(passed=not failed, row_count={'before': int(populated), 'after': int(populated)},
                       column_profile={}, keyed_row_hash={'difference': 0}, sampled_differences=[])
    evidence = {'shared_billing_boundary': {name:measurement for name in ('USAGE_DAILY', 'INVOICE_LINE')}}
    documents_apply_storage(rows, evidence)
    assert {row['status'] for row in rows} == ({'red'} if failed else {'amber'})
    if not failed:
        assert all(row['storage_writer'].endswith('12_storage_monthly.sql:OPS.10_STORAGE_MONTHLY') for row in rows)
    documents_apply_storage(rows, {}, 'snowflake')


@pytest.mark.parametrize('failure',[None,'outside','inside','legacy','empty'])
def test_complete_version_scope_and_derived_owners(failure):
    with duckdb.connect() as before, duckdb.connect() as after:
        for db,schema in ((before,'SFX_DOCUMENTS'),(after,'DOCUMENTS')):
            db.execute('CREATE SCHEMA '+schema)
            db.execute('CREATE TABLE '+schema+'.STG_DOC_VERSION (VERSION_ID BIGINT, DOCUMENT_ID BIGINT, VERSION_NO BIGINT, VERSION_TS TIMESTAMP, FILE_SIZE BIGINT, CONTENT_HASH VARCHAR)')
            db.execute("INSERT INTO "+schema+".STG_DOC_VERSION VALUES (11,1,1,'2026-11-09',10,'a'),(12,1,2,'2026-11-09',11,'b'),(21,2,1,'2026-11-09',20,'c')")
            db.execute('CREATE TABLE '+schema+'.DOC_VERSION AS SELECT * FROM '+schema+'.STG_DOC_VERSION WHERE VERSION_ID IN ('+('11,21' if db is before else '12,21')+')')
            db.execute('CREATE TABLE '+schema+'.DOCUMENT (DOCUMENT_ID BIGINT,OWNER_USER_ID BIGINT)')
            db.execute('INSERT INTO '+schema+'.DOCUMENT VALUES (1,100),(2,200)')
            db.execute('CREATE VIEW '+schema+'.V_DOCUMENT_VERSIONS AS SELECT d.DOCUMENT_ID,d.OWNER_USER_ID,v.VERSION_ID,v.VERSION_TS,v.FILE_SIZE FROM '+schema+'.DOCUMENT d JOIN '+schema+'.DOC_VERSION v USING (DOCUMENT_ID)')
            db.execute('CREATE VIEW '+schema+'.V_WORKSPACE_STORAGE AS SELECT OWNER_USER_ID,COUNT(*) DOCUMENT_COUNT,CAST(SUM(FILE_SIZE) AS DECIMAL(38,0)) TOTAL_BYTES FROM '+schema+'.V_DOCUMENT_VERSIONS GROUP BY OWNER_USER_ID')
        if failure in ('inside','outside'):
            after.execute('UPDATE DOCUMENTS.DOC_VERSION SET FILE_SIZE=999 WHERE DOCUMENT_ID='+('1' if failure=='inside' else '2'))
        if failure=='legacy':
            before.execute("UPDATE SFX_DOCUMENTS.DOC_VERSION SET CONTENT_HASH='corrupt' WHERE DOCUMENT_ID=1")
        if failure=='empty':
            for db,schema in ((before,'SFX_DOCUMENTS'),(after,'DOCUMENTS')):
                for table in ('STG_DOC_VERSION','DOC_VERSION','DOCUMENT'):
                    db.execute('DELETE FROM '+schema+'.'+table)
        measurements = {name:local_compare(before,after,'SFX_DOCUMENTS.'+name,'DOCUMENTS.'+name)
                        for name in ('DOC_VERSION','V_DOCUMENT_VERSIONS','V_WORKSPACE_STORAGE')}
        version_scope(before,after,measurements)
        for name,value in measurements.items():
            proof = value['owner_decision']
            assert proof['scope_document_ids']==([] if failure=='empty' else [1])
            assert proof['approved_comparison']['passed']==(failure in (None,'legacy','empty'))
            row = dict(status='green' if value['passed'] else 'red')
            decision = dict(decision_id='documents-latest-version',status='approved',new_behaviour='Highest version wins')
            apply_deviation(row,{name:value},[decision])
            assert row['status']==('green' if failure=='empty' else
                                  'approved_deviation' if failure is None else 'red')
            if failure=='outside':
                assert proof['outside_scope_rows']>0


@pytest.mark.parametrize('failure',[None,'missing','scope','comparison','unregistered','unapproved','other_relation'])
def test_deviation_requires_every_failure_to_have_registered_exhaustive_proof(failure):
    proof = dict(decision_id='any-decision',scope_valid=failure!='scope',
                 approved_comparison={'passed':failure!='comparison'})
    measurements = {'ANY':dict(passed=False,owner_decision=proof)}
    decisions = [dict(decision_id='any-decision',status='unapproved' if failure=='unapproved' else 'approved',new_behaviour='Approved rule')]
    if failure=='missing':
        measurements['ANY'].pop('owner_decision')
    if failure=='unregistered':
        decisions=[]
    if failure=='other_relation':
        measurements['OTHER']=dict(passed=False)
    row = dict(status='red')
    apply_deviation(row,measurements,decisions)
    assert row['status']==('approved_deviation' if failure is None else 'red')
    if failure is None:
        decisions[0].update(status='approved-pending-confirmation',confirmation='Finance pending')
        row = dict(status='red')
        apply_deviation(row,measurements,decisions)
        assert row['status']==row['local_duckdb']=='amber'
        assert row['reason']=='Finance pending'
        assert row['measurement_status']=='red'
    assert apply_deviation(dict(status='red'),{},decisions)['status']=='red'
