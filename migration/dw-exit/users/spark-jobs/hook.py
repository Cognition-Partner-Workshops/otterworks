"""Local Snowpark-Python equivalents and independently executed Spark baseline."""
from contextlib import redirect_stdout
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

import duckdb
import sqlglot
from sqlglot import exp

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'etl/spark/jobs/py'))
sys.path.insert(0, str(ROOT / 'etl/spark/fixture'))
from common.schemas import SCHEMAS
from generate_fixture import generate
from warehouse.run_config import RunConfig

INPUTS = ('USER_PREF', 'LOGIN_EVENT', 'USER_ACTIVITY_DAILY', 'TEAM', 'TEAM_MEMBER', 'APP_USER')
JOBS = ('team_graph_components', 'user_pref_json_flatten', 'users_active_daily',
        'users_login_useragent_parse', 'users_risk_score', 'users_team_rollup')
FIXTURE_SEED = 1110


def table_expression(schema, name):
    return exp.Table(db=exp.to_identifier(schema, quoted=True),
                     this=exp.to_identifier(name, quoted=True))


def load_fixture(after, landing):
    for table in INPUTS:
        columns = {name: 'VARCHAR' if kind == 'TEXT' else kind for name, kind in SCHEMAS[table]}
        statement = sqlglot.parse_one('CREATE OR REPLACE TABLE placeholder AS SELECT * FROM read_csv(?, delim=\'|\', header=true, columns=?, escape=\'"\', nullstr=\'\')', read='duckdb')
        statement.set('this', table_expression('USERS', 'SPARK_FIXTURE_' + table))
        after.execute(statement.sql(dialect='duckdb'), [str(landing / 'users' / table / '*.psv'), columns])


def preference(raw, key):
    try:
        return str(json.loads(raw or '{}').get(key, ''))
    except (ValueError, TypeError):
        return None


def browser(agent):
    match = re.search(r'(Chrome|Firefox|Safari)/(\S+)', agent or '')
    return '/'.join(match.groups()) if match else 'Other'


def risk(logins, actions):
    if logins is None or actions is None:
        return None
    exponent = -(-2.1 + logins * 0.0004 - actions * 0.0001)
    return 0.0 if exponent > 709.782712893384 else 1.0 / (1.0 + math.exp(exponent))


def components(rows):
    teams = {}
    for team, user in rows:
        teams.setdefault(0 if team is None else team, set()).add(0 if user is None else user)
    edges = {(a, b) for users in teams.values() for a in users for b in users if a != b}
    labels = {a: a for a, _ in edges}
    for _ in range(6):
        updated = dict(labels)
        for a, b in edges:
            updated[b] = min(updated[b], labels[a])
        labels = updated
    return list(labels.items())


def convert(after, selected=JOBS):
    for statement in sqlglot.parse(RunConfig.from_env().render((HERE / '10_load.sql').read_text()), read='snowflake'):
        for table in statement.find_all(exp.Table):
            table.set('catalog', None)
        if statement.this.name.lower() in selected:
            after.execute(statement.sql(dialect='duckdb'))
    after.create_function('users_preference', preference, ['VARCHAR', 'VARCHAR'], 'VARCHAR', null_handling='special')
    after.create_function('users_browser', browser, ['VARCHAR'], 'VARCHAR', null_handling='special')
    after.create_function('users_risk', risk, ['BIGINT', 'BIGINT'], 'DOUBLE', null_handling='special')
    if 'user_pref_json_flatten' in selected:
        after.execute("CREATE TABLE USERS.USER_PREF_JSON_FLATTEN AS SELECT *, users_preference(PREF_JSON, 'theme') THEME, users_preference(PREF_JSON, 'notifications') NOTIFICATIONS, users_preference(PREF_JSON, 'locale') LOCALE FROM USERS.SPARK_FIXTURE_USER_PREF")
    if 'users_login_useragent_parse' in selected:
        after.execute('CREATE TABLE USERS.USERS_LOGIN_USERAGENT_PARSE AS SELECT *, users_browser(USER_AGENT) BROWSER FROM USERS.SPARK_FIXTURE_LOGIN_EVENT')
    if 'users_risk_score' in selected:
        after.execute('CREATE TABLE USERS.USERS_RISK_SCORE AS SELECT *, users_risk(LOGIN_COUNT, ACTION_COUNT) RISK_SCORE FROM USERS.SPARK_FIXTURE_USER_ACTIVITY_DAILY')
    if 'team_graph_components' not in selected:
        return
    after.execute('CREATE TABLE USERS.TEAM_GRAPH_COMPONENTS (USER_ID BIGINT, COMPONENT_ID BIGINT)')
    labels = components(after.execute('SELECT TEAM_ID, USER_ID FROM USERS.SPARK_FIXTURE_TEAM_MEMBER').fetchall())
    if labels:
        after.executemany('INSERT INTO USERS.TEAM_GRAPH_COMPONENTS VALUES (?, ?)', labels)


def materialize(before, after, ready, errors):
    targets = {'USERS.' + job.upper() for job in JOBS}
    work = ROOT / 'migration/dw-exit/.runs' / RunConfig.from_env().token / 'users-spark'
    landing = work / 'landing'
    work.mkdir(parents=True, exist_ok=True)
    try:
        rows = int(os.environ.get('BOARD_ROWS', '200'))
        with (work / 'fixture.log').open('w') as log, redirect_stdout(log):
            generate(landing, rows, FIXTURE_SEED)
        load_fixture(after, landing)
        convert(after)
        env = {'PATH': '/usr/bin:/bin', 'HOME': str(Path.home()),
               'USERS_PARITY_WORK': str(work), 'USERS_PARITY_JOBS': ','.join(JOBS),
               'LANDING_DIR': str(landing), 'SPARK_LOCAL_IP': '127.0.0.1',
               'PYSPARK_PYTHON': sys.executable, 'PYSPARK_DRIVER_PYTHON': sys.executable}
        with (work / 'legacy.log').open('w') as log:
            subprocess.run([sys.executable, str(HERE / 'legacy.py')], env=env,
                           stdout=log, stderr=subprocess.STDOUT, check=True, timeout=240)
        before.execute('CREATE SCHEMA IF NOT EXISTS SFX_USERS')
        for job in JOBS:
            statement = sqlglot.parse_one('CREATE OR REPLACE TABLE placeholder AS SELECT * FROM read_parquet(?)', read='duckdb')
            statement.set('this', table_expression('SFX_USERS', job.upper()))
            before.execute(statement.sql(dialect='duckdb'), [str(work / 'legacy' / job / '*.parquet')])
            ready.add('USERS.' + job.upper())
            errors.pop('USERS.' + job.upper(), None)
        print(f'Input: legacy Spark fixture, seed={FIXTURE_SEED}, rows={rows}; both sides read identical PSV files')
        print('Legacy Spark: unmodified job bodies executed: ' + ', '.join(JOBS) + '; log=' + str(work / 'legacy.log'))
    except (duckdb.Error, subprocess.SubprocessError, ValueError, OSError) as error:
        for target in targets:
            ready.discard(target)
            errors[target] = 'users Spark proof failed: ' + str(error).splitlines()[0] + '; log=' + str(work / 'legacy.log')
