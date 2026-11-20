import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import duckdb
import pytest

spec = importlib.util.spec_from_file_location('users_spark_hook', Path(__file__).with_name('hook.py'))
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


def test_preference():
    assert hook.preference('{"theme":"dark","notifications":false}', 'theme') == 'dark'
    assert hook.preference('{"notifications":false}', 'notifications') == 'False'
    assert hook.preference(None, 'theme') == ''
    assert hook.preference('', 'theme') == ''
    assert hook.preference('bad json', 'theme') is None
    assert hook.preference('{"theme":null}', 'theme') == 'None'
    with pytest.raises(AttributeError):
        hook.preference('[]', 'theme')


def test_browser():
    assert hook.browser('Mozilla Chrome/120 Safari/1') == 'Chrome/120'
    assert hook.browser('Firefox/1.2 extra') == 'Firefox/1.2'
    assert hook.browser('chrome/1') == 'Other'
    assert hook.browser(None) == 'Other'
    assert hook.browser('') == 'Other'


def test_risk():
    assert hook.risk(10, 20) == 0.1092913626341005
    assert hook.risk(None, 20) is None
    assert hook.risk(0, 10**9) == 0.0


def test_components():
    assert hook.components([]) == []
    assert hook.components([(1, 7)]) == []
    assert dict(hook.components([(1, 2), (1, 3), (2, 3), (2, 4), (1, 2)])) == {2: 2, 3: 2, 4: 2}
    chain = [(team, user) for team in range(9) for user in (team, team + 1)]
    assert dict(hook.components(chain))[9] == 3


def test_empty_conversions():
    db = duckdb.connect()
    db.execute('CREATE SCHEMA USERS')
    definitions = {
        'USER_PREF': 'USER_PREF_ID BIGINT, USER_ID BIGINT, PREF_JSON VARCHAR',
        'LOGIN_EVENT': 'LOGIN_EVENT_ID BIGINT, USER_AGENT VARCHAR',
        'USER_ACTIVITY_DAILY': 'USER_ACTIVITY_ID BIGINT, USER_ID BIGINT, ACTIVITY_DATE DATE, LOGIN_COUNT BIGINT, ACTION_COUNT BIGINT',
        'TEAM': 'TEAM_ID BIGINT, TEAM_NAME VARCHAR',
        'TEAM_MEMBER': 'TEAM_ID BIGINT, USER_ID BIGINT',
        'APP_USER': 'USER_ID BIGINT',
    }
    for table, columns in definitions.items():
        db.execute(f'CREATE TABLE USERS.SPARK_FIXTURE_{table} ({columns})')
    hook.convert(db)
    for job in hook.JOBS:
        assert db.execute(f'SELECT COUNT(*) FROM USERS.{job.upper()}').fetchone() == (0,)
    db.close()


def test_fixture_loading_is_deterministic(tmp_path):
    snapshots = []
    for _ in range(2):
        subprocess.run([sys.executable, str(hook.ROOT / 'etl/spark/fixture/generate_fixture.py'),
                        '--rows', '3', '--seed', str(hook.FIXTURE_SEED), '--output', str(tmp_path)],
                       check=True, capture_output=True)
        db = duckdb.connect()
        db.execute('CREATE SCHEMA USERS')
        hook.load_fixture(db, tmp_path)
        snapshots.append({table: db.execute(f'SELECT * FROM USERS.SPARK_FIXTURE_{table} ORDER BY 1').fetchall()
                          for table in hook.INPUTS})
        hook.convert(db)
        assert db.execute('SELECT COUNT(*) FROM USERS.USER_PREF_JSON_FLATTEN').fetchone() == (3,)
        assert db.execute('SELECT COUNT(*) FROM USERS.USERS_LOGIN_USERAGENT_PARSE').fetchone() == (3,)
        assert db.execute('SELECT COUNT(*) FROM USERS.USERS_RISK_SCORE').fetchone() == (3,)
        db.close()
    assert snapshots[0] == snapshots[1]


def test_board_annotation(tmp_path):
    spec = importlib.util.spec_from_file_location('users_board_annotation', Path(__file__).with_name('annotate_board.py'))
    annotation = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(annotation)
    path = tmp_path / 'board.json'
    path.write_text(json.dumps({'measurement_contract': {}, 'rows': [
        {'status': 'green', 'reason': None}, {'status': 'red', 'reason': 'mismatch'}]}))
    annotation.annotate(path)
    first = path.read_text()
    annotation.annotate(path)
    assert path.read_text() == first
    payload = json.loads(first)
    assert payload['measurement_contract']['fixture']['seed'] == 1110
    assert payload['rows'][0]['reason'].startswith('Measured equal.')
    assert payload['rows'][1]['reason'].startswith('mismatch')
