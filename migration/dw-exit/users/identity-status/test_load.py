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
    names = set()
    for table, columns in (
        ('SSO_IDENTITY', 'IDENTITY_ID BIGINT, USER_ID BIGINT, PROVIDER_CD VARCHAR, '
         'SUBJECT_ID VARCHAR, CREATED_DT DATE'),
        ('USER_STATUS_HIST', 'STATUS_HISTORY_ID BIGINT, USER_ID BIGINT, STATUS_CD VARCHAR, '
         'VALID_FROM DATE, VALID_TO DATE'),
    ):
        for prefix in ('', 'STG_'):
            name = 'SFX_USERS.' + prefix + table
            names.add(name)
            before.execute(f'CREATE TABLE {name} ({columns})')
        if count:
            values = ("(1, NULL, 'oIdC', 'CaseSensitive', DATE '2026-01-01'),"
                      "(2, 7, NULL, NULL, NULL)" if table == 'SSO_IDENTITY' else
                      "(1, 7, 'Active', DATE '2026-01-01', NULL),"
                      "(2, NULL, NULL, NULL, NULL)")
            before.execute(f'INSERT INTO SFX_USERS.STG_{table} VALUES {values}')
            before.execute(f'INSERT INTO SFX_USERS.{table} VALUES {values}')
            code = 'PROVIDER_CD' if table == 'SSO_IDENTITY' else 'STATUS_CD'
            before.execute(f"UPDATE SFX_USERS.{table} SET {code} = RPAD({code}, 12, ' ')")
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
