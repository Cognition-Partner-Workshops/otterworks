import duckdb
import pytest
from jinja2 import Environment
import sqlglot

import assess
from parity import object_board
from parity.ladder import local_compare
from parity.owner_decisions import apply_confirmation
from parity import local_audit as audit


def test_pending_confirmation_is_general_and_keeps_measurement():
    row = dict(name='ANY.RELATION', status='green')
    decision = dict(status='approved-pending-confirmation',
                    board_objects=['ANY.RELATION'], confirmation='Owner confirmation pending')
    apply_confirmation(row, [decision])
    apply_confirmation(row, [decision])
    assert row['status'] == row['local_duckdb'] == 'amber'
    assert row['measurement_status'] == 'green'
    assert row['reason'] == 'Owner confirmation pending'
    assert apply_confirmation(dict(name='OTHER', status='red'), [decision])['status'] == 'red'
    assert apply_confirmation(dict(name='OTHER', status='red'), [])['status'] == 'red'


def test_storage_board_amber_without_fabricating_measurement():
    obj = next(o for o in assess.build()['objects'] if o['name']=='SFX_DOCUMENTS.STORAGE_USAGE_DAILY')
    board = object_board.build_board({'objects':[obj]})
    row = board['rows'][0]
    assert row['status'] == 'amber'
    assert row['measurement_status'] == 'red' and row['row_count'] is None
    assert 'Finance' in row['reason']
    assert board['summary']['amber'] == 1
    assert object_board.build_board({'objects':[]})['summary']['amber'] == 0


@pytest.mark.parametrize('failure',[None,'suffix','legacy_prefix'])
def test_widening_full_input_and_raw_120_row_legacy_evidence(failure):
    with duckdb.connect() as c:
        c.execute('CREATE SCHEMA USERS; CREATE SCHEMA SFX_USERS')
        c.execute('CREATE TABLE USERS.STG_APP_USER (USER_ID BIGINT,DISPLAY_NAME VARCHAR)')
        rows = [(i,'User '+str(i)+'x'*(90 if i<100 else 0)) for i in range(120)]
        c.executemany('INSERT INTO USERS.STG_APP_USER VALUES (?,?)',rows)
        c.execute('CREATE TABLE USERS.APP_USER AS SELECT * FROM USERS.STG_APP_USER')
        c.execute('CREATE TABLE SFX_USERS.APP_USER AS SELECT USER_ID,LEFT(DISPLAY_NAME,60) DISPLAY_NAME FROM USERS.STG_APP_USER')
        if failure == 'suffix':
            c.execute("UPDATE USERS.APP_USER SET DISPLAY_NAME=LEFT(DISPLAY_NAME,60)||'bad' WHERE USER_ID=1")
        if failure == 'legacy_prefix':
            c.execute("UPDATE SFX_USERS.APP_USER SET DISPLAY_NAME='bad' WHERE USER_ID=1")
        result = local_compare(c,c,'SFX_USERS.APP_USER','USERS.APP_USER')
        assert result['passed'] == (failure is None)
        assert not result['raw_legacy']['passed']
        assert result['comparison_rules']['legacy_truncated_rows'] == 100
        c.execute('DELETE FROM USERS.APP_USER; DELETE FROM SFX_USERS.APP_USER')
        assert local_compare(c,c,'SFX_USERS.APP_USER','USERS.APP_USER')['passed']


@pytest.mark.parametrize('reverse',[False,True])
def test_audit_numbering_by_date_then_key(reverse):
    with duckdb.connect() as c:
        c.execute('CREATE SCHEMA AUDIT')
        audit.execute(c,(audit.SQL/'00_tables.sql').read_text(),'20261109')
        rows = [(1,1,1,9,'2026-11-10','DOC_EXPORT','x'),
                (2,1,1,8,'2026-11-09','DOC_EXPORT','x'),
                (3,1,1,2,'2026-11-09','DOC_EXPORT','x')]
        c.executemany('INSERT INTO AUDIT.AUDIT_EVENT VALUES (?,?,?,?,?,?,?)',list(reversed(rows)) if reverse else rows)
        audit.execute(c,'CALL X.AUDIT.M_SFX_AUDIT_DAILY_SUMMARY();','20261109')
        assert c.execute('SELECT SUMMARY_ID,CUSTOMER_ID FROM AUDIT.AUDIT_DAILY_SUMMARY ORDER BY SUMMARY_ID').fetchall() == [(50001,2),(50002,8),(50003,9)]
        audit.execute(c,'CALL X.AUDIT.M_SFX_AUDIT_DAILY_SUMMARY();','20261109')
        assert c.execute('SELECT COUNT(*) FROM AUDIT.AUDIT_DAILY_SUMMARY').fetchone() == (3,)
        model = audit.ROOT/'warehouse/dbt/models/pc/audit/pc_audit__audit_daily_summary.sql'
        query = Environment().from_string(model.read_text()).render(
            config=lambda **kwargs:'',var=lambda name,default:default,
            ref=lambda name:'AUDIT.AUDIT_EVENT')
        dbt_rows = c.execute(sqlglot.transpile(query,read='snowflake',write='duckdb')[0]).fetchall()
        shipped_rows = c.execute('SELECT * FROM AUDIT.AUDIT_DAILY_SUMMARY').fetchall()
        assert sorted(dbt_rows) == sorted(shipped_rows)
