import importlib.util
from pathlib import Path

import duckdb
import pytest
import sqlglot


GROUP = Path(__file__).parent
spec = importlib.util.spec_from_file_location('activity_hook', GROUP / 'hook.py')
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


@pytest.fixture
def target():
    connection = duckdb.connect()
    connection.execute('CREATE SCHEMA USERS')
    connection.execute('CREATE TABLE USERS.LOGIN_EVENT '
                       '(LOGIN_ID BIGINT, USER_ID BIGINT, LOGIN_TS TIMESTAMP, RESULT_CD VARCHAR, CLIENT_TYPE VARCHAR)')
    connection.execute('CREATE TABLE USERS.USER_ACTIVITY_DAILY '
                       '(ACTIVITY_ID BIGINT, USER_ID BIGINT, ACTIVITY_DT DATE, LOGIN_COUNT INTEGER, DOCUMENT_COUNT INTEGER)')
    query = (GROUP / '30_views.sql').read_text().replace('__RUN_DATABASE__.', '')
    connection.execute(sqlglot.transpile(query, read='snowflake', write='duckdb')[0])
    yield connection
    connection.close()


def run(target):
    ready = {'USERS.USER_ACTIVITY_DAILY', 'USERS.V_ACTIVITY_DAILY'}
    errors = {}
    hook.materialize(None, target, ready, errors)
    return ready, errors


def test_daily_counts_all_outcomes_preserves_base_and_replaces_generated(target, monkeypatch):
    monkeypatch.setenv('BUSINESS_DATE', '20261109')
    target.execute("INSERT INTO USERS.LOGIN_EVENT VALUES (1,7,'2026-11-09 00:00:00','SUCCESS',NULL),"
                   "(2,7,'2026-11-09 23:59:59','FAILED',NULL),(3,7,'2026-11-10',NULL,NULL)")
    target.execute("INSERT INTO USERS.USER_ACTIVITY_DAILY VALUES (1,7,'2026-11-08',9,2),"
                   "(10000000008,8,'2026-11-08',1,0)")
    ready, errors = run(target)
    assert not errors
    assert 'USERS.USER_ACTIVITY_DAILY' in ready
    assert target.execute('SELECT ACTIVITY_ID, LOGIN_COUNT, DOCUMENT_COUNT FROM USERS.USER_ACTIVITY_DAILY '
                          'ORDER BY ACTIVITY_ID').fetchall() == [(1, 9, 2), (10000000007, 2, 0)]
    run(target)
    assert target.execute('SELECT COUNT(*) FROM USERS.USER_ACTIVITY_DAILY').fetchone() == (2,)


def test_empty_day(target, monkeypatch):
    monkeypatch.setenv('BUSINESS_DATE', '20261109')
    assert run(target)[1] == {}
    assert target.execute('SELECT COUNT(*) FROM USERS.USER_ACTIVITY_DAILY').fetchone() == (0,)


def test_invalid_day_is_red(target, monkeypatch):
    monkeypatch.setenv('BUSINESS_DATE', 'invalid')
    ready, errors = run(target)
    assert 'USERS.USER_ACTIVITY_DAILY' not in ready
    assert errors['USERS.USER_ACTIVITY_DAILY'].startswith('daily procedure failed:')


def test_missing_input_is_red(target):
    ready, errors = {'USERS.USER_ACTIVITY_DAILY'}, {}
    hook.materialize(None, target, ready, errors)
    assert not ready
    assert errors['USERS.USER_ACTIVITY_DAILY'] == 'daily procedure input not materialized'
