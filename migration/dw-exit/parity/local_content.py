"""Actual PowerCenter BEFORE and shipped Scripting AFTER on identical local inputs."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys

from psycopg.conninfo import conninfo_to_dict
import sqlglot
from sqlglot import exp

from warehouse.run_config import render

ROOT = Path(__file__).resolve().parents[3]
XML = 'etl/informatica/repository/SFX_CONTENT/wf_SFX_CONTENT_DAILY.XML'
PROCEDURE = ROOT / 'migration/dw-exit/content/workflow.sql'
OUTPUTS = ('SFX_USERS.STG_APP_USER', 'SFX_USERS.APP_USER', 'SFX_USERS.ROLE_GRANT',
           'SFX_USERS.LOGIN_EVENT', 'SFX_USERS.TEAM_MEMBER', 'SFX_DOCUMENTS.STG_DOCUMENT',
           'SFX_DOCUMENTS.DOCUMENT', 'SFX_DOCUMENTS.DOC_SHARE')
DISPLAY_NAME_DECISION = ('approved widening: DISPLAY_NAME retains up to 200 characters; '
           'proof validates full input and retains raw legacy truncation measurements')
LANDING = {'APP_USER': ('users', 'SFX_USERS.STG_APP_USER'),
           'ROLE_GRANT': ('users', 'SFX_USERS.ROLE_GRANT'),
           'LOGIN_EVENT': ('users', 'SFX_USERS.LOGIN_EVENT'),
           'DOCUMENT': ('documents', 'SFX_DOCUMENTS.STG_DOCUMENT'),
           'DOC_SHARE': ('documents', 'SFX_DOCUMENTS.DOC_SHARE')}


def clone(before, after, source, destination):
    definitions = before.execute('DESCRIBE ' + source).fetchall()
    after.execute('CREATE SCHEMA IF NOT EXISTS ' + destination.split('.')[0])
    after.execute('CREATE TABLE ' + destination + ' (' + ', '.join('"' + c[0] + '" ' + c[1] for c in definitions) + ')')
    rows = before.execute('SELECT * FROM ' + source).fetchall()
    if rows:
        after.executemany('INSERT INTO ' + destination + ' VALUES (' + ','.join('?' for _ in definitions) + ')', rows)


def load_inputs(before, after, landing, business_date):
    hashes = {}
    for name, (area, source) in LANDING.items():
        destination = 'PC_SRC.' + name
        clone(before, after, source, destination)
        after.execute('DELETE FROM ' + destination)
        path = landing / area / name / (business_date + '.psv')
        hashes[str(path.relative_to(landing))] = hashlib.sha256(path.read_bytes()).hexdigest()
        after.execute('COPY ' + destination + " FROM '" + str(path).replace("'", "''")
                      + "' (DELIMITER '|', HEADER FALSE, NULL '')")
    return hashes


def statements(path=PROCEDURE):
    text = render(path.read_text())
    match = re.fullmatch(r'.*?\$\$\s*BEGIN\s*(.*?)\s*RETURN \'SUCCEEDED\';\s*END;\s*\$\$;\s*', text, re.S)
    if not match:
        raise ValueError('Unsupported content Scripting wrapper')
    body = match[1]
    sessions = {}
    for area in ('users', 'documents'):
        text = render((ROOT/'migration/dw-exit'/area/'52_sessions.sql').read_text())
        sessions.update(re.findall(r'CREATE OR REPLACE PROCEDURE\s+(\S+)\(\).*?\$\$\s*BEGIN\s*(.*?)\s*RETURN \'SUCCEEDED\';\s*END;\s*\$\$;', text, re.S))
    def expand(call):
        if call[1] not in sessions:
            raise ValueError('Unknown content session: '+call[1])
        return sessions[call[1]]
    body = re.sub(r'CALL\s+(\S+)\(\);', expand, body)
    for statement in sqlglot.parse(body, read='snowflake'):
        if not isinstance(statement, (exp.Insert, exp.Merge, exp.TruncateTable)):
            raise ValueError('Unsupported content statement: ' + type(statement).__name__)
        for table in statement.find_all(exp.Table):
            table.set('catalog', None)
        # DuckDB ignores VARCHAR(n) cast lengths; Snowflake casts truncate explicitly.
        for cast in list(statement.find_all(exp.Cast)):
            dtype = cast.args['to']
            if dtype.this == exp.DataType.Type.VARCHAR and dtype.expressions:
                size = dtype.expressions[0].this
                cast.set('this', exp.Substring(this=cast.this.copy(), start=exp.Literal.number(1), length=size.copy()))
        yield statement


def execute(after, path=PROCEDURE):
    for statement in statements(path):
        after.execute(statement.sql(dialect='duckdb'))


def run_source(dsn, ns, landing, business_date):
    if business_date != '20261109':
        raise ValueError('Content parameter file requires business date 20261109')
    params = conninfo_to_dict(dsn)
    if params.get('host') not in ('127.0.0.1', 'localhost'):
        raise ValueError('PowerCenter execution is restricted to the local emulator')
    env = dict(os.environ, NS=ns, MAPPINGS='all', LANDING_DIR=str(landing),
               TD_HOST=params['host'], TD_PORT=params.get('port', '5432'),
               TD_DB=params.get('dbname', 'teradata'), TD_USER=params.get('user', 'postgres'),
               TD_PASSWORD=params.get('password', ''),
               PMROOTDIR=str(ROOT / 'etl/informatica/infa_shared' / ns))
    result = subprocess.run([sys.executable, '-m', 'runner', 'startworkflow', '-f', 'SFX_CONTENT',
                             'wf_SFX_CONTENT_DAILY'], cwd=ROOT / 'etl/informatica', env=env,
                            text=True, capture_output=True)
    log = ROOT / 'migration/dw-exit/.runs/content-workflow.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError('PowerCenter failed; see ' + str(log.relative_to(ROOT)))
    return str(log.relative_to(ROOT))


def materialize(before, after, dsn, ns, snapshot, business_date='20261109'):
    ready, errors = set(), {}
    evidence = {'source_execution': 'PowerCenter runner startworkflow', 'procedure': str(PROCEDURE.relative_to(ROOT)),
                'target_execution': 'shipped procedure body on DuckDB', 'team_member': 'pre-workflow state preserved',
                'approved_owner_decision': DISPLAY_NAME_DECISION}
    actual = None
    try:
        evidence['pre_workflow'] = {}
        for source in OUTPUTS:
            rows = before.execute('SELECT * FROM ' + source).fetchall()
            evidence['pre_workflow'][source] = {'rows': len(rows),
                'sha256': hashlib.sha256(repr(sorted(rows, key=repr)).encode()).hexdigest()}
            clone(before, after, source, source.removeprefix('SFX_'))
        landing = Path(os.environ.get('LANDING_DIR', ROOT / 'warehouse/landing')).resolve()
        evidence['landing_sha256'] = load_inputs(before, after, landing, business_date)
        evidence['source_log'] = run_source(dsn, ns, landing, business_date)
        actual, actual_ready, source_errors = snapshot(dsn, set(OUTPUTS))
        if source_errors or actual_ready != set(OUTPUTS):
            raise ValueError('Incomplete post-workflow source snapshot')
        for source in OUTPUTS:
            before.execute('DROP TABLE ' + source)
            clone(actual, before, source, source)
        execute(after)
        ready.update(source.removeprefix('SFX_') for source in OUTPUTS)
    except Exception as error:
        errors.update({source.removeprefix('SFX_'): 'content execution: ' + type(error).__name__ + ': ' + str(error)
                       for source in OUTPUTS})
    finally:
        if actual is not None:
            actual.close()
    return ready, errors, evidence
