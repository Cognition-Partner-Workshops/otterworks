import importlib.util
from pathlib import Path
import sys

import duckdb
import pytest
import sqlglot
from sqlglot import exp


GROUP = Path(__file__).resolve().parent
ROOT = GROUP.parents[3]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location(
    'identity_board', ROOT / 'migration/dw-exit/parity/object_board.py')
board = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(board)


@pytest.mark.parametrize('count', [0, 2])
def test_full_refresh_preserves_values_and_is_repeatable(count):
    before = duckdb.connect()
    before.execute('CREATE SCHEMA SFX_USERS')
    names = {'SFX_USERS.SSO_IDENTITY', 'SFX_USERS.STG_SSO_IDENTITY',
             'SFX_USERS.USER_STATUS_HIST', 'SFX_USERS.STG_USER_STATUS_HIST'}
    before.execute('CREATE TABLE SFX_USERS.SSO_IDENTITY '
                   '(IDENTITY_ID BIGINT, USER_ID BIGINT, PROVIDER_CD VARCHAR, '
                   'SUBJECT_ID VARCHAR, CREATED_DT DATE)')
    before.execute('CREATE TABLE SFX_USERS.STG_SSO_IDENTITY '
                   '(IDENTITY_ID BIGINT, USER_ID BIGINT, PROVIDER_CD VARCHAR, '
                   'SUBJECT_ID VARCHAR, CREATED_DT DATE)')
    before.execute('CREATE TABLE SFX_USERS.USER_STATUS_HIST '
                   '(STATUS_HISTORY_ID BIGINT, USER_ID BIGINT, STATUS_CD VARCHAR, '
                   'VALID_FROM DATE, VALID_TO DATE)')
    before.execute('CREATE TABLE SFX_USERS.STG_USER_STATUS_HIST '
                   '(STATUS_HISTORY_ID BIGINT, USER_ID BIGINT, STATUS_CD VARCHAR, '
                   'VALID_FROM DATE, VALID_TO DATE)')
    if count:
        identities = [(1, None, 'oIdC', 'CaseSensitive', '2026-01-01'),
                      (2, 7, None, None, None)]
        statuses = [(1, 7, 'Active', '2026-01-01', None),
                    (2, None, None, None, None)]
        before.executemany('INSERT INTO SFX_USERS.STG_SSO_IDENTITY VALUES (?, ?, ?, ?, ?)',
                           identities)
        before.executemany('INSERT INTO SFX_USERS.SSO_IDENTITY VALUES (?, ?, ?, ?, ?)',
                           identities)
        before.executemany('INSERT INTO SFX_USERS.STG_USER_STATUS_HIST VALUES (?, ?, ?, ?, ?)',
                           statuses)
        before.executemany('INSERT INTO SFX_USERS.USER_STATUS_HIST VALUES (?, ?, ?, ?, ?)',
                           statuses)
        before.execute("UPDATE SFX_USERS.SSO_IDENTITY SET PROVIDER_CD = RPAD(PROVIDER_CD, 12, ' ')")
        before.execute("UPDATE SFX_USERS.USER_STATUS_HIST SET STATUS_CD = RPAD(STATUS_CD, 12, ' ')")
    after, ready, errors = board.materialize(before, names, GROUP, ('USERS',))
    try:
        assert not errors
        for statement in sqlglot.parse(
            board.RunConfig.from_env().render((GROUP / '10_load.sql').read_text()),
            read='snowflake',
        ):
            for table in statement.find_all(exp.Table):
                table.set('catalog', None)
            after.execute(statement.sql(dialect='duckdb'))
        for table in ('SSO_IDENTITY', 'USER_STATUS_HIST'):
            target = 'USERS.' + table
            assert target in ready
            result = board.compare(before, after, 'SFX_USERS.' + table, target)
            assert result['passed']
            assert result['row_count'] == {'before': count, 'after': count}
    finally:
        before.close()
        after.close()


def test_missing_landing_is_not_ready():
    before = duckdb.connect()
    after, ready, errors = board.materialize(before, set(), GROUP, ('USERS',))
    try:
        assert not ready
        assert errors['USERS.SSO_IDENTITY'] == 'conversion input not materialized'
        assert errors['USERS.USER_STATUS_HIST'] == 'conversion input not materialized'
    finally:
        before.close()
        after.close()
