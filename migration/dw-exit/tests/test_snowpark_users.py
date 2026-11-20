from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest

from parity.snowpark_users import execute


def test_handler_resolves_current_database_for_both_relations():
    from warehouse.snowpark.m_sfx_app_user import run
    session = MagicMock()
    session.get_current_database.return_value = 'A_DIFFERENT_RUN_DB'
    target, source = MagicMock(), MagicMock()
    session.table.side_effect = [target, source]
    target.merge.return_value = SimpleNamespace(rows_inserted=2, rows_updated=1)
    assert run(session) == 3
    session.get_current_database.assert_called_once_with()
    assert session.table.call_args_list == [
        call(['A_DIFFERENT_RUN_DB', 'USERS', 'APP_USER']),
        call(['A_DIFFERENT_RUN_DB', 'USERS', 'STG_APP_USER']),
    ]


@pytest.mark.parametrize('populated',[False,True])
@pytest.mark.parametrize('database', ['SFG1120_USERS_PROOF', 'ANOTHER_RUN_DATABASE'])
def test_local_snowpark_merge_empty_updates_inserts_and_retains(populated, database):
    initial = [(1,'old','a','ACTIVE',date(2020,1,1)),(9,'keep',None,None,None)] if populated else []
    staging = [(1,'x'*100,'b'*130,'PENDING',date(2021,1,1)),(2,'new',None,None,None)] if populated else []
    rows,changed = execute(initial,staging,database)
    assert sorted(rows,key=lambda r:r[0]) == ([(1,'x'*100,'b'*120,'PENDING',date(2021,1,1)),(2,'new',None,None,None),(9,'keep',None,None,None)] if populated else [])
    assert changed == (2 if populated else 0)


def test_local_snowpark_missing_input_fails_without_connecting(monkeypatch):
    import snowflake.connector
    from snowflake.snowpark import Session
    from snowflake.snowpark.mock.exceptions import SnowparkLocalTestingException
    from warehouse.snowpark.m_sfx_app_user import run

    def forbidden(*args, **kwargs):
        pytest.fail('live connector must not be called')

    monkeypatch.setattr(snowflake.connector, 'connect', forbidden)
    with Session.builder.config('local_testing', True).create() as session:
        with pytest.raises(SnowparkLocalTestingException):
            run(session)
