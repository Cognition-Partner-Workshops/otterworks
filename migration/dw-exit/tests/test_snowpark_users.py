from datetime import date

import pytest

from parity.snowpark_users import execute


@pytest.mark.parametrize('populated',[False,True])
def test_local_snowpark_merge_empty_updates_inserts_and_retains(populated):
    initial = [(1,'old','a','ACTIVE',date(2020,1,1)),(9,'keep',None,None,None)] if populated else []
    staging = [(1,'x'*100,'b'*130,'PENDING',date(2021,1,1)),(2,'new',None,None,None)] if populated else []
    rows,changed = execute(initial,staging)
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
