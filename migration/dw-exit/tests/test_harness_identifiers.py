import duckdb
import pytest

from parity import dbc_retire, local_audit, local_content, object_board, pc_users, spark_users


@pytest.mark.parametrize('name',['','../run_job','../../elsewhere','users_risk_score; SELECT 1'])
def test_snowpark_rejects_unlisted_code_before_reading_or_execution(name):
    with pytest.raises(ValueError,match='Unsupported shipped users Snowpark job'):
        spark_users.snowpark_query(None,name)


def test_snowpark_rejects_sql_in_schema_before_execution():
    with pytest.raises(ValueError,match='Invalid identifier'):
        spark_users.snowpark_query(None,'users_risk_score','SPARK_INPUT; SELECT 1')


@pytest.mark.parametrize('table',['','../other','APP_USER; SELECT 1'])
def test_pc_rejects_unlisted_models_and_capture_relations(table):
    with pytest.raises(ValueError,match='Unsupported PC model'):
        pc_users.model_query(table,None,{})
    with pytest.raises(ValueError,match='Unsupported PC model'):
        pc_users.execute_model(None,table)
    with pytest.raises(ValueError,match='Unsupported PC capture relation'):
        pc_users.copy_table(None,None,table,'INITIAL')


def test_dbc_and_subject_allowlists_reject_unknown_identifiers():
    with pytest.raises(ValueError,match='Unsupported DBC relation'):
        dbc_retire.emulator(None,'DBC.QRYLOGV; SELECT 1')
    with pytest.raises(ValueError,match='Unsupported DBC family'):
        dbc_retire.mapped_compare(None,'UNKNOWN')
    with pytest.raises(ValueError,match='Unsupported local subject'):
        object_board.materialize(None,set(),None,subject='billing; SELECT 1')


@pytest.mark.parametrize('clone',[local_audit.copy_relation,local_content.clone])
@pytest.mark.parametrize('source,target',[('SRC.ROWS; SELECT 1','DST.ROWS'),
                                        ('SRC.ROWS','DST.ROWS; SELECT 1')])
def test_clones_reject_sql_in_identifiers_before_execution(clone,source,target):
    with pytest.raises(ValueError,match='Invalid identifier'):
        clone(None,None,source,target)


@pytest.mark.parametrize('clone',[local_audit.copy_relation,local_content.clone])
@pytest.mark.parametrize('populated',[False,True])
def test_quoted_clone_preserves_rows_and_empty_tables(clone,populated):
    with duckdb.connect() as before,duckdb.connect() as after:
        before.execute('CREATE SCHEMA SRC; CREATE TABLE SRC.ROWS (ID BIGINT,VALUE VARCHAR)')
        after.execute('CREATE SCHEMA DST')
        if populated:
            before.execute("INSERT INTO SRC.ROWS VALUES (1, 'quoted '' value')")
        clone(before,after,'SRC.ROWS','DST.ROWS')
        assert before.execute('SELECT * FROM SRC.ROWS').fetchall()==after.execute('SELECT * FROM DST.ROWS').fetchall()
