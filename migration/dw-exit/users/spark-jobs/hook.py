"""Local Snowpark-Python equivalents and independently executed Spark baseline."""
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import zlib

import duckdb
import sqlglot
from sqlglot import exp

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'migration/dw-exit/parity'))
from object_board import source_snapshot
from warehouse.run_config import RunConfig

INPUTS = ('USER_PREF', 'LOGIN_EVENT', 'USER_ACTIVITY_DAILY', 'TEAM', 'TEAM_MEMBER', 'APP_USER')
JOBS = ('team_graph_components', 'user_pref_json_flatten', 'users_active_daily',
        'users_login_useragent_parse', 'users_risk_score', 'users_team_rollup')


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
        after.execute("CREATE TABLE USERS.USER_PREF_JSON_FLATTEN AS SELECT *, users_preference(PREF_JSON, 'theme') THEME, users_preference(PREF_JSON, 'notifications') NOTIFICATIONS, users_preference(PREF_JSON, 'locale') LOCALE FROM USERS.STG_USER_PREF")
    if 'users_login_useragent_parse' in selected:
        after.execute('CREATE TABLE USERS.USERS_LOGIN_USERAGENT_PARSE AS SELECT *, users_browser(USER_AGENT) BROWSER FROM USERS.STG_LOGIN_EVENT')
    if 'users_risk_score' in selected:
        after.execute('CREATE TABLE USERS.USERS_RISK_SCORE AS SELECT *, users_risk(LOGIN_COUNT, ACTION_COUNT) RISK_SCORE FROM USERS.STG_USER_ACTIVITY_DAILY')
    if 'team_graph_components' not in selected:
        return
    after.execute('CREATE TABLE USERS.TEAM_GRAPH_COMPONENTS (USER_ID BIGINT, COMPONENT_ID BIGINT)')
    labels = components(after.execute('SELECT TEAM_ID, USER_ID FROM USERS.STG_TEAM_MEMBER').fetchall())
    if labels:
        after.executemany('INSERT INTO USERS.TEAM_GRAPH_COMPONENTS VALUES (?, ?)', labels)


def materialize(before, after, ready, errors):
    ns = os.environ.get('NS', RunConfig.from_env().before_namespace)
    port = os.environ.get('TD_PG_PORT', str(54500 + zlib.crc32(ns.encode()) % 1000))
    dsn = os.environ.get('BOARD_SOURCE_DSN', f'host=127.0.0.1 port={port} dbname=teradata user=postgres')
    sources, available, failures = source_snapshot(dsn, {'SFX_USERS.STG_' + name for name in INPUTS})
    targets = {'USERS.' + job.upper() for job in JOBS}
    if failures:
        for target in targets:
            errors[target] = 'legacy input unavailable: ' + json.dumps(failures, sort_keys=True)
        sources.close()
        return
    work = ROOT / 'migration/dw-exit/.runs' / RunConfig.from_env().token / 'users-spark'
    (work / 'inputs').mkdir(parents=True, exist_ok=True)
    try:
        for table in INPUTS:
            name = 'SFX_USERS.STG_' + table
            path = work / 'inputs' / (table + '.parquet')
            sources.execute(f"COPY {name} TO '{path}' (FORMAT PARQUET)")
            after.execute(f"CREATE OR REPLACE TABLE USERS.STG_{table} AS SELECT * FROM read_parquet(?)", [str(path)])
        requirements = {
            'user_pref_json_flatten': ('USER_PREF', {'USER_PREF_ID', 'USER_ID', 'PREF_JSON'}),
            'users_login_useragent_parse': ('LOGIN_EVENT', {'LOGIN_EVENT_ID', 'USER_ID', 'EVENT_AT', 'IP_ADDRESS', 'USER_AGENT', 'RAW_LINE'}),
            'users_active_daily': ('USER_ACTIVITY_DAILY', {'ACTIVITY_DATE', 'USER_ID', 'LOGIN_COUNT', 'ACTION_COUNT'}),
            'users_risk_score': ('USER_ACTIVITY_DAILY', {'USER_ACTIVITY_ID', 'USER_ID', 'ACTIVITY_DATE', 'LOGIN_COUNT', 'ACTION_COUNT'}),
        }
        selected = list(JOBS)
        for job, (table, expected) in requirements.items():
            actual = {row[0] for row in after.execute('DESCRIBE USERS.STG_' + table).fetchall()}
            missing = expected - actual
            if missing:
                selected.remove(job)
                errors['USERS.' + job.upper()] = ('Legacy Spark input schema incompatible: SFX_USERS.STG_' + table
                    + ' missing ' + ', '.join(sorted(missing)) + '; actual columns: ' + ', '.join(sorted(actual))
                    + '. No inferred column mapping or fabricated legacy output applied.')
        convert(after, selected)
        env = dict(os.environ, USERS_PARITY_WORK=str(work), USERS_PARITY_JOBS=','.join(selected), SPARK_LOCAL_IP='127.0.0.1')
        # Spark reads a directory, just as the production landing reader does.
        for table in INPUTS:
            directory = work / 'inputs' / table
            directory.mkdir(exist_ok=True)
            (work / 'inputs' / (table + '.parquet')).replace(directory / 'part.parquet')
        with (work / 'legacy.log').open('w') as log:
            subprocess.run([sys.executable, str(HERE / 'legacy.py')], env=env,
                           stdout=log, stderr=subprocess.STDOUT, check=True, timeout=240)
        before.execute('CREATE SCHEMA IF NOT EXISTS SFX_USERS')
        for job in selected:
            before.execute(f'CREATE OR REPLACE TABLE SFX_USERS.{job.upper()} AS SELECT * FROM read_parquet(?)',
                           [str(work / 'legacy' / job / '*.parquet')])
            ready.add('USERS.' + job.upper())
            errors.pop('USERS.' + job.upper(), None)
        print('Legacy Spark: unmodified job bodies executed: ' + ', '.join(selected) + '; log=' + str(work / 'legacy.log'))
    except (duckdb.Error, subprocess.SubprocessError, ValueError, OSError) as error:
        for target in targets:
            ready.discard(target)
            errors[target] = 'users Spark proof failed: ' + str(error).splitlines()[0] + '; log=' + str(work / 'legacy.log')
    finally:
        sources.close()
