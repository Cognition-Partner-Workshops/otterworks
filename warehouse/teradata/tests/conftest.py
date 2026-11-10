import io
import os
import sys
import uuid
from pathlib import Path

import psycopg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bteq import Runner


@pytest.fixture
def td():
    try:
        runner = Runner(output=io.StringIO())
    except psycopg.OperationalError as exc:
        if any(k.startswith('TD_PG_') for k in os.environ):
            pytest.fail(str(exc))
        pytest.skip('No PostgreSQL reachable')
    schema = 'test_' + uuid.uuid4().hex
    runner.execute('CREATE DATABASE ' + schema)
    runner.execute('DATABASE ' + schema)
    yield runner
    runner.conn.execute('DROP SCHEMA ' + schema + ' CASCADE')
    runner.conn.execute('DELETE FROM sfx_td.tables WHERE name LIKE %s', (schema + '.%',))
    runner.conn.execute('DELETE FROM sfx_td.routines WHERE name LIKE %s', (schema + '.%',))
    runner.conn.close()
