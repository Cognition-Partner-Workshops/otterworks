import importlib.util
import json
from pathlib import Path
import re

import duckdb
import pytest
from sqlglot import exp

from parity import local_documents as documents
from parity.ladder import local_compare
from parity.local_billing import statements

ROOT = Path(__file__).resolve().parents[3]
MODELS = ROOT/'warehouse/dbt/models/pc/content'


@pytest.fixture
def connections():
    with duckdb.connect() as before, duckdb.connect() as after:
        before.execute('CREATE SCHEMA SFX_DOCUMENTS')
        for statement in statements(documents.CONVERSIONS/'00_tables.sql','20261109'):
            for table in statement.find_all(exp.Table):
                table.set('db',exp.to_identifier('SFX_DOCUMENTS'))
            for column in statement.find_all(exp.ColumnDef):
                column.set('constraints',[])
            before.execute(statement.sql(dialect='duckdb'))
        yield before, after


def seed(before):
    before.execute("INSERT INTO SFX_DOCUMENTS.STG_FOLDER VALUES (1,1,1,'Folder','2026-11-09')")
    before.execute("INSERT INTO SFX_DOCUMENTS.STG_DOCUMENT VALUES (1,1,1,1,'Name','2026-11-09','Active  ','txt ')")
    before.execute("INSERT INTO SFX_DOCUMENTS.STG_DOC_VERSION VALUES (1,1,1,'2026-11-09 12:00:00',4096,'abc')")
    before.execute("INSERT INTO SFX_DOCUMENTS.STG_DOC_SHARE VALUES (1,1,1,'VIEW  ','2026-11-09')")
    before.execute("INSERT INTO SFX_DOCUMENTS.STG_STORAGE_USAGE_DAILY VALUES (1,1,1,'2026-11-09',100,2),(1,1,1,'2026-11-09',100,2)")
    before.execute('INSERT INTO SFX_DOCUMENTS.STORAGE_USAGE_DAILY SELECT DISTINCT * FROM SFX_DOCUMENTS.STG_STORAGE_USAGE_DAILY')
    before.execute("INSERT INTO SFX_DOCUMENTS.STG_SEARCH_INDEX_LOG VALUES (1,1,'2026-11-09','ACTIVE  ',10),(2,NULL,NULL,'',NULL)")


def test_executor_normal_and_approved_set_dedupe(connections):
    before,after = connections
    seed(before)
    ready,errors = documents.execute(after,before)
    assert not errors and 'DOCUMENTS.V_WORKSPACE_STORAGE' in ready
    assert after.execute('SELECT STATUS_CD,FILE_TYPE FROM DOCUMENTS.DOCUMENT').fetchall() == [('Active','txt')]
    assert after.execute('SELECT TOTAL_BYTES FROM DOCUMENTS.V_WORKSPACE_STORAGE').fetchone()[0] == 4096
    measured = local_compare(before,after,'SFX_DOCUMENTS.STORAGE_USAGE_DAILY','DOCUMENTS.STORAGE_USAGE_DAILY')
    assert measured['row_count'] == {'before':1,'after':1}
    assert measured['keyed_row_hash']['difference'] == 0
    assert measured['passed']


def test_executor_empty(connections):
    before,after = connections
    ready,errors = documents.execute(after,before)
    assert len(ready) == 21 and not errors
    assert after.execute('SELECT * FROM DOCUMENTS.DOC_VERSION').fetchall() == []
    assert after.execute('SELECT * FROM DOCUMENTS.V_WORKSPACE_STORAGE').fetchall() == []


def test_storage_300_rows_become_250_without_dropping_distinct_payloads(connections):
    before,after = connections
    rows = [(i,1,1,'2026-11-09',100,2) for i in range(250)]
    before.executemany('INSERT INTO SFX_DOCUMENTS.STG_STORAGE_USAGE_DAILY VALUES (?,?,?,?,?,?)',rows+rows[:50])
    assert not documents.execute(after,before)[1]
    assert after.execute('SELECT COUNT(*),SUM(BYTES_USED) FROM DOCUMENTS.STORAGE_USAGE_DAILY').fetchone() == (250,25000)


@pytest.mark.parametrize('failure',['missing_source','invalid_date','bad_sql'])
def test_executor_fails_closed(connections,tmp_path,failure):
    before,after = connections
    kwargs = {}
    if failure == 'missing_source':
        before.execute('DROP TABLE SFX_DOCUMENTS.STG_FOLDER')
    elif failure == 'invalid_date':
        kwargs['business_date'] = '20260231'
    else:
        (tmp_path/'00_tables.sql').write_text('CREATE TABLE broken (')
        kwargs['conversion_dir'] = tmp_path
    ready,errors = documents.execute(after,before,**kwargs)
    assert not ready and errors
    assert after.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='DOCUMENTS'").fetchone()[0] == 0


@pytest.mark.parametrize('populated',[False,True])
def test_storage_resultset_normal_and_empty(connections,populated):
    before,after = connections
    if populated:
        seed(before)
    assert not documents.execute(after,before)[1]
    documents.resultset(before,after)
    rows = after.execute('SELECT * FROM DOCUMENTS.M_STORAGE_TOTALS_OUTPUT').fetchall()
    assert rows == ([(1,100,2)] if populated else [])
    measured = local_compare(before,after,'SFX_DOCUMENTS.M_STORAGE_TOTALS_OUTPUT','DOCUMENTS.M_STORAGE_TOTALS_OUTPUT')
    assert measured['passed']


def test_resultset_half_open_month(connections):
    before,after = connections
    before.execute("INSERT INTO SFX_DOCUMENTS.STG_STORAGE_USAGE_DAILY VALUES (1,1,1,'2026-11-01',100,2),(2,1,1,'2026-12-01',999,9)")
    before.execute('INSERT INTO SFX_DOCUMENTS.STORAGE_USAGE_DAILY SELECT * FROM SFX_DOCUMENTS.STG_STORAGE_USAGE_DAILY')
    assert not documents.execute(after,before)[1]
    documents.resultset(before,after)
    assert after.execute('SELECT * FROM DOCUMENTS.M_STORAGE_TOTALS_OUTPUT').fetchall() == [(1,100,2)]


@pytest.mark.parametrize('failure',['wrapper','unbound','missing_input'])
def test_resultset_errors_no_partial_output(connections,tmp_path,failure):
    before,after = connections
    assert not documents.execute(after,before)[1]
    text = (documents.CONVERSIONS/'35_reports.sql').read_text()
    if failure == 'wrapper':
        text = 'SELECT 1'
    elif failure == 'unbound':
        text = text.replace(':p_start',':unknown')
    else:
        after.execute('DROP TABLE DOCUMENTS.STORAGE_USAGE_DAILY')
    (tmp_path/'35_reports.sql').write_text(text)
    with pytest.raises((ValueError,duckdb.Error)):
        documents.resultset(before,after,conversion_dir=tmp_path)
    assert before.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name='M_STORAGE_TOTALS_OUTPUT'").fetchone()[0] == 0
    assert after.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name='M_STORAGE_TOTALS_OUTPUT'").fetchone()[0] == 0


def test_contract_keys_and_all_manifest_routes():
    contract = json.loads((documents.CONVERSIONS.parent/'parity/documents.json').read_text())
    assert len([r for r in contract if '.TD_DOCUMENTS_BASELINE.' in r['before']]) == 24
    assert all(r['keys'] for r in contract)
    routes = json.loads((documents.CONVERSIONS/'objects.json').read_text())
    assert len(routes) == 44
    assert all((ROOT/r['conversion']).is_file() for r in routes)
    shared = next(r for r in routes if r['name']=='10_storage_monthly')
    assert shared['shared'] and shared['conversion']=='migration/dw-exit/documents/12_storage_monthly.sql'


def test_procedure_bodies_match_executed_sql():
    load = (documents.CONVERSIONS/'10_load.sql').read_text()
    bodies = re.findall(r'-- OPS\.\w+[^\n]*\n(.*?)(?=\n-- OPS\.|\Z)',load,re.S)
    procedures = (documents.CONVERSIONS/'11_procedures.sql').read_text()
    assert len(bodies)==5 and all(body.strip() in procedures for body in bodies)
    assert 'ORDER BY VERSION_TS DESC, VERSION_NO DESC)' in load


@pytest.mark.parametrize('populated',[True,False])
def test_tpt_executes_shipped_projection(connections,tmp_path,populated):
    before,after = connections
    if populated:
        seed(before)
    assert not documents.execute(after,before)[1]
    for table, in before.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='SFX_DOCUMENTS' AND table_name LIKE 'STG_%'").fetchall():
        folder = tmp_path/'documents'/table.removeprefix('STG_')
        folder.mkdir(parents=True)
        before.execute('COPY SFX_DOCUMENTS.'+table+" TO '"+str(folder/'20261109.psv')+"' (DELIMITER '|', HEADER FALSE, NULL '')")
    documents.load_landing(after,tmp_path)
    for table in ('STG_DOCUMENT', 'STG_SEARCH_INDEX_LOG'):
        measured = local_compare(before,after,'SFX_DOCUMENTS.'+table,'DOCUMENTS.'+table)
        assert measured['passed']


def test_tpt_missing_input_rolls_back(connections,tmp_path):
    before,after = connections
    seed(before)
    assert not documents.execute(after,before)[1]
    with pytest.raises(OSError):
        documents.load_landing(after,tmp_path)
    assert after.execute('SELECT COUNT(*) FROM DOCUMENTS.STG_DOCUMENT').fetchone()[0] == 1


def test_pc_merge_preserves_filtered_existing_owner_and_empty():
    with duckdb.connect() as c:
        c.execute('CREATE SCHEMA PC_CONTENT')
        c.execute('CREATE SCHEMA USERS')
        c.execute('CREATE TABLE PC_CONTENT.STG_DOCUMENT (DOCUMENT_ID BIGINT,FOLDER_ID BIGINT,OWNER_USER_ID BIGINT,CUSTOMER_ID BIGINT,DOCUMENT_NAME VARCHAR,CREATED_DT DATE,STATUS_CD VARCHAR,FILE_TYPE VARCHAR)')
        c.execute("INSERT INTO PC_CONTENT.STG_DOCUMENT VALUES (1,1,99,1,'Name','2026-11-09','ACTIVE','txt')")
        c.execute('CREATE TABLE PC_CONTENT.DOCUMENT AS SELECT * FROM PC_CONTENT.STG_DOCUMENT')
        c.execute('CREATE TABLE USERS.APP_USER (USER_ID BIGINT,STATUS_CD VARCHAR)')
        query = documents.render_pc(MODELS/'pc_content__document.sql')
        assert c.execute(query).fetchall() == []
        documents.merge_pc(c,'DOCUMENT',query,'DOCUMENT_ID')
        assert c.execute('SELECT COUNT(*) FROM PC_CONTENT.DOCUMENT').fetchone()[0] == 1
        c.execute("INSERT INTO USERS.APP_USER VALUES (99,'ACTIVE')")
        documents.merge_pc(c,'DOCUMENT',query,'DOCUMENT_ID')
        assert c.execute('SELECT COUNT(*) FROM PC_CONTENT.DOCUMENT').fetchone()[0] == 1


def test_pc_effective_access_highest_privilege():
    with duckdb.connect() as c:
        c.execute('CREATE SCHEMA PC_SRC')
        c.execute('CREATE SCHEMA PC_CONTENT')
        c.execute('CREATE SCHEMA USERS')
        c.execute('CREATE TABLE PC_SRC.DOC_SHARE (SHARE_ID BIGINT,DOCUMENT_ID BIGINT,USER_ID BIGINT,ACCESS_LEVEL VARCHAR,SHARED_DT DATE)')
        c.execute('CREATE TABLE USERS.ROLE_GRANT (USER_ID BIGINT,ROLE_CD VARCHAR)')
        c.execute("INSERT INTO PC_SRC.DOC_SHARE VALUES (1,1,1,'view','2026-11-09'),(2,1,2,'view','2026-11-09'),(3,1,3,'view','2026-11-09')")
        c.execute("INSERT INTO USERS.ROLE_GRANT VALUES (1,'ADMIN'),(2,'EDITOR')")
        c.execute('CREATE TABLE PC_CONTENT.DOC_SHARE AS SELECT * FROM PC_SRC.DOC_SHARE WHERE FALSE')
        query = documents.render_pc(MODELS/'pc_content__doc_share.sql')
        documents.merge_pc(c,'DOC_SHARE',query,'SHARE_ID')
        assert c.execute('SELECT ACCESS_LEVEL FROM PC_CONTENT.DOC_SHARE ORDER BY SHARE_ID').fetchall()==[('OWNER',),('EDIT',),('VIEW',)]
        c.execute("INSERT INTO USERS.ROLE_GRANT VALUES (1,'EDITOR')")
        c.execute("INSERT INTO USERS.ROLE_GRANT VALUES (2,'READER'),(2,'EDITOR'),(3,'READER'),(3,'ADMIN')")
        documents.merge_pc(c,'DOC_SHARE',query,'SHARE_ID')
        assert c.execute('SELECT ACCESS_LEVEL FROM PC_CONTENT.DOC_SHARE ORDER BY SHARE_ID').fetchall()==[('OWNER',),('EDIT',),('OWNER',)]
        assert c.execute('SELECT COUNT(*), COUNT(DISTINCT SHARE_ID) FROM PC_CONTENT.DOC_SHARE').fetchone() == (3, 3)
        c.execute('DELETE FROM PC_SRC.DOC_SHARE')
        assert c.execute(query).fetchall() == []


@pytest.mark.parametrize('reverse',[False,True])
def test_latest_version_ties_choose_highest_number(connections,reverse):
    before,after = connections
    rows = [(10,1,1,'2026-11-09 12:00:00',100,'a'),
            (11,1,2,'2026-11-09 12:00:00',200,'b'),
            (12,1,9,'2026-11-08 12:00:00',300,'c')]
    before.executemany('INSERT INTO SFX_DOCUMENTS.STG_DOC_VERSION VALUES (?,?,?,?,?,?)',list(reversed(rows)) if reverse else rows)
    assert not documents.execute(after,before)[1]
    assert after.execute('SELECT VERSION_ID,VERSION_NO FROM DOCUMENTS.DOC_VERSION').fetchall() == [(11,2)]


def test_pc_template_fails_closed(tmp_path):
    path = tmp_path/'bad.sql'
    path.write_text("select * from {{ ref('unknown') }}")
    with pytest.raises(ValueError,match='Unsupported'):
        documents.render_pc(path)


@pytest.mark.parametrize('name,key',[('document','DOCUMENT_ID'),('doc_share','SHARE_ID')])
def test_snowpark_publisher_emits_merge(name,key):
    spec = importlib.util.spec_from_file_location('publisher',ROOT/'warehouse/snowpark'/('m_sfx_'+name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    class Session:
        def get_current_database(self):
            return 'SFX_1119'
        def sql(self,sql):
            assert 'MERGE INTO SFX_1119.DOCUMENTS.'+name.upper() in sql
            assert 'PC_CONTENT.'+name.upper() in sql and 't.'+key+'=s.'+key in sql
            return self
        def collect(self):
            return ['local SQL shape only']
    assert module.run(Session()) == ['local SQL shape only']

def test_document_dag_and_converted_role_grant_source():
    import yaml
    assert "-- depends_on: {{ ref('pc_content__app_user') }}" in (MODELS/'pc_content__document.sql').read_text()
    model = (MODELS/'pc_content__doc_share.sql').read_text()
    assert "source('users_converted', 'ROLE_GRANT')" in model
    sources = yaml.safe_load((documents.CONVERSIONS.parents[2]/'warehouse/dbt/models/documents/_documents_sources.yml').read_text())['sources']
    source = next(s for s in sources if s['name']=='users_converted')
    assert source['schema']=='USERS'
    assert {'name':'ROLE_GRANT'} in source['tables']
