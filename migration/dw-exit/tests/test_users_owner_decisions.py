import duckdb
import pytest

from parity import owner_decisions


@pytest.mark.parametrize('rows', [[], [(1, 'x', 'mail')], [(1, 'x'*60, 'mail')]])
def test_display_scope_empty_equal_and_widened(rows):
    with duckdb.connect() as before, duckdb.connect() as after:
        for db in (before, after):
            db.execute('CREATE SCHEMA USERS; CREATE TABLE USERS.APP_USER (USER_ID BIGINT, DISPLAY_NAME VARCHAR, EMAIL VARCHAR)')
        for row in rows:
            before.execute('INSERT INTO USERS.APP_USER VALUES (?,?,?)',row)
            after.execute('INSERT INTO USERS.APP_USER VALUES (?,?,?)',(row[0], row[1]+'long' if len(row[1]) == 60 else row[1],row[2]))
        proof = owner_decisions.display_names(before,after,'USERS.APP_USER','USERS.APP_USER')
        assert proof['scope_valid'] and proof['other_columns_hash_equal']


@pytest.mark.parametrize('change', ["UPDATE USERS.APP_USER SET EMAIL='other'", "UPDATE USERS.APP_USER SET DISPLAY_NAME='wrong'", "DELETE FROM USERS.APP_USER", "INSERT INTO USERS.APP_USER SELECT * FROM USERS.APP_USER", "UPDATE USERS.APP_USER SET DISPLAY_NAME=repeat('x',201)"])
def test_display_scope_fails_closed(change):
    with duckdb.connect() as before, duckdb.connect() as after:
        for db in (before, after):
            db.execute("CREATE SCHEMA USERS; CREATE TABLE USERS.APP_USER AS SELECT 1 USER_ID, repeat('x',60) DISPLAY_NAME, 'mail' EMAIL")
        after.execute(change)
        assert not owner_decisions.display_names(before,after,'USERS.APP_USER','USERS.APP_USER')['scope_valid']


@pytest.mark.parametrize('complete,valid,expected', [(True,True,'approved_deviation'),(False,True,'red'),(True,False,'red')])
def test_owner_application_requires_complete_scoped_measurement(complete, valid, expected):
    row = dict(name='SFX_USERS.APP_USER',status='red',row_count={'before':1,'after':1} if complete else None)
    owner_decisions.apply(row,[dict(scope_valid=valid,differing_rows=1)])
    assert row['status'] == expected
    if expected == 'approved_deviation':
        assert row['measurement_status'] == 'red'
