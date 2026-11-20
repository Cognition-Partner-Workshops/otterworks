import json

import duckdb
import pytest

from parity import owner_decisions


def approval():
    return json.loads((owner_decisions.ROOT/'migration/dw-exit/dbc/decisions.json').read_text())[0]


@pytest.mark.parametrize('case',['missing_only','empty','retained_value','missing_row','extra_row','metric_value','reordered','unapproved'])
def test_missing_fields_only_promote_exact_scoped_multisets(case):
    with duckdb.connect() as db:
        db.execute('CREATE SCHEMA SRC; CREATE SCHEMA DST')
        db.execute('CREATE TABLE SRC.LOG (ID BIGINT,VALUE VARCHAR,ClientID VARCHAR,AMPCPUTime DOUBLE,TotalIOCount BIGINT)')
        db.execute('CREATE TABLE DST.LOG AS SELECT * FROM SRC.LOG')
        if case != 'empty':
            db.execute("INSERT INTO SRC.LOG VALUES (1,'x','client',1.5,7),(1,'x','client',1.5,7)")
            db.execute("INSERT INTO DST.LOG VALUES (1,'x',NULL,NULL,NULL),(1,'x',NULL,NULL,NULL)")
        if case == 'retained_value':
            db.execute("UPDATE DST.LOG SET VALUE='corrupt'")
        elif case == 'missing_row':
            db.execute('DELETE FROM DST.LOG WHERE rowid=0')
        elif case == 'extra_row':
            db.execute('INSERT INTO DST.LOG SELECT * FROM DST.LOG LIMIT 1')
        elif case == 'metric_value':
            db.execute('UPDATE DST.LOG SET AMPCPUTime=999')
        elif case == 'reordered':
            db.execute('CREATE OR REPLACE TABLE DST.LOG AS SELECT VALUE,ID,ClientID,AMPCPUTime,TotalIOCount FROM DST.LOG')
        decision = approval()
        if case == 'unapproved':
            decision['status'] = 'proposed'
        scoped = owner_decisions.missing_fields(db,'SRC.LOG','DST.LOG',{'passed':False},decision)
        row = dict(name='DBC.QRYLOGV',status='red',local_duckdb='red')
        owner_decisions.apply_deviation(row,{'log':scoped},[decision])
        assert (row['status']=='approved_deviation') == (case in ('missing_only','empty'))
        assert scoped['owner_decision']['approved_comparison']['row_count']['before'] == (0 if case=='empty' else 2)


def test_missing_field_identifiers_are_validated():
    with pytest.raises(ValueError,match='Invalid identifier'):
        owner_decisions.missing_fields(None,'SRC.LOG; SELECT 1','DST.LOG',{},approval())


@pytest.mark.parametrize('case',['normal','partial','empty','read','non_mp_execute','mp_read','extra','multiplicity'])
def test_row_scope_requires_both_mp_and_execute_and_never_filters_target(case):
    with duckdb.connect() as db:
        db.execute('CREATE TABLE OLD (ID BIGINT,ObjectType VARCHAR,UsageType VARCHAR)')
        db.execute('CREATE TABLE NEW AS SELECT * FROM OLD')
        if case != 'empty':
            db.execute("INSERT INTO OLD VALUES (1,'T','READ'),(2,'M','EXECUTE'),(3,'P','EXECUTE'),(4,'T','EXECUTE'),(5,'M','READ')")
            db.execute('INSERT INTO NEW SELECT * FROM OLD WHERE ID IN (1,4,5)')
        if case in ('read','non_mp_execute','mp_read'):
            db.execute('DELETE FROM NEW WHERE ID=?',[{'read':1,'non_mp_execute':4,'mp_read':5}[case]])
        elif case == 'partial':
            db.execute("INSERT INTO NEW VALUES (2,'M','EXECUTE')")
        elif case == 'extra':
            db.execute("INSERT INTO NEW VALUES (99,'M','EXECUTE')")
        elif case == 'multiplicity':
            db.execute('INSERT INTO NEW SELECT * FROM NEW LIMIT 1')
        decision = {**approval(),'missing_rows':{'ObjectType':['M','P'],'UsageType':['EXECUTE']}}
        result = owner_decisions.missing_fields(db,'OLD','NEW',{'passed':False},decision)
        assert result['owner_decision']['scope_valid'] == (case in ('normal','partial','empty'))
        assert result['owner_decision']['excluded_source_rows'] == (0 if case=='empty' else 1 if case=='partial' else 2)


@pytest.mark.parametrize('column',['StatementGroup','AccessCount'])
def test_widened_timestamp_scope_does_not_ignore_other_fields(column):
    with duckdb.connect() as db:
        db.execute('CREATE TABLE OLD (CollectTimeStamp BIGINT,LastAccessTimeStamp BIGINT,StatementGroup VARCHAR,AccessCount BIGINT)')
        db.execute("INSERT INTO OLD VALUES (1,2,'SELECT',9)")
        db.execute("CREATE TABLE NEW AS SELECT 99 AS CollectTimeStamp,NULL AS LastAccessTimeStamp,StatementGroup,AccessCount FROM OLD")
        assert owner_decisions.missing_fields(db,'OLD','NEW',{'passed':False},approval())['owner_decision']['scope_valid']
        if column == 'StatementGroup':
            db.execute("UPDATE NEW SET StatementGroup='other'")
        else:
            db.execute('UPDATE NEW SET AccessCount=10')
        assert not owner_decisions.missing_fields(db,'OLD','NEW',{'passed':False},approval())['owner_decision']['scope_valid']
