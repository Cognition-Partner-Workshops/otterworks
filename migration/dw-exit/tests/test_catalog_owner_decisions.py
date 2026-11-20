import json

import duckdb
import pytest

import assess
from parity import object_board, owner_decisions


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


@pytest.mark.parametrize('approved',[False,True])
def test_audit_retirement_requires_manifest_target_and_owner_approval(monkeypatch,approved):
    decisions = owner_decisions.approved_retirements() if approved else []
    monkeypatch.setattr(object_board,'approved_retirements',lambda:decisions)
    objects = [o for o in assess.build()['objects'] if o['subject_area']=='audit' and o['target_type']=='retire']
    assert len(objects)==6
    board = object_board.build_board({'objects':objects})
    assert all(row['status']==('retired' if approved else 'red') for row in board['rows'])
    assert board['summary']['audit']['local_retired'] == (6 if approved else 0)
    assert board['summary']['audit']['local_red'] == (0 if approved else 6)
    assert board['summary']['areas']['audit']['retire'] == (6 if approved else 0)
    assert all(row['migration_status']=='not_started' for row in board['rows'])
    assert all(row['snowflake']=='red' for row in board['rows'])
    row = dict(name=objects[0]['name'],status='red')
    owner_decisions.apply_retirement(row,{'target_type':'dbt_model'},decisions)
    assert row['status']=='red'
    assert object_board.build_board({'objects':[]})['summary']['areas']=={}
