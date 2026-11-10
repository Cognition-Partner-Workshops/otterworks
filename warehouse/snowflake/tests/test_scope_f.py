from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment
import pytest
from snowflake.connector.errors import ProgrammingError
import tomlkit
import yaml

import governance
import ledger
import sfx_conn
import snowconvert
import teardown
from test_operations import Cursor, HOUR, meter, query

ROOT = Path(__file__).resolve().parents[1]


def test_post_deploy_governance():
    calls = []
    governance.reapply(SimpleNamespace(execute=lambda sql, params: calls.append((sql, params))))
    assert len(governance.objects()) == 15
    assert len(calls) == 30
    assert all('SET TAG GOVERNANCE.SFX_RUN' in sql for sql, _ in calls[::2])
    assert all('COMMENT ON' in sql and 'sfx-d1110' in params[0] for sql, params in calls[1::2])
    assert len(set(governance.objects())) == 15
    assert 'reapply(cursor)' in (ROOT / 'deploy.py').read_text()
    assert "ALLOWED_VALUES 'sfx-d1110'" in (ROOT / 'migrations/V006__governance.sql').read_text()


def render_governance(policies=None, results=None, existing=(), missing=False, standalone=False):
    calls = []
    class Relation:
        is_view = True
        def __str__(self):
            return '"DB"."CORE_BILLING"."CUSTOMER"'
    adapter = SimpleNamespace(quote=lambda value: '"' + value.replace('"', '""') + '"',
                              get_relation=lambda **kw: None if missing else Relation())
    node = SimpleNamespace(name='customer', resource_type='model', database='DB',
                           schema='CORE_BILLING', alias='CUSTOMER', description='customer',
                           config=SimpleNamespace(materialized='view'))
    def run_query(sql):
        calls.append(' '.join(sql.split()))
        return SimpleNamespace(rows=existing)
    def fail(message):
        raise ValueError(message)
    env = Environment(extensions=['jinja2.ext.do'])
    env.globals.update(execute=True, adapter=adapter, run_query=run_query,
                       env_var=lambda *args: 'sfx-d1110', var=lambda *args: policies or {},
                       exceptions=SimpleNamespace(raise_compiler_error=fail),
                       graph=SimpleNamespace(nodes={'customer': node}),
                       log=lambda *args, **kw: '', **{'return': lambda value: value})
    module = env.from_string((ROOT.parent / 'dbt/macros/reapply_governance.sql').read_text()).module
    if standalone:
        module.reapply_governance()
    else:
        module.reapply_governance(results if results is not None else [SimpleNamespace(node=node, status='success')])
    return calls


def test_dbt_governance_normal_empty_missing_and_policies():
    assert len(render_governance()) == 2
    assert len(render_governance(standalone=True)) == 2
    assert render_governance(results=[]) == []
    assert render_governance(missing=True) == []
    policies = {'customer': {'masking': [{'column': 'EMAIL', 'policy': 'DB.GOVERNANCE.EMAIL_MASK'}],
                            'column_tags': {'EMAIL': {'DB.GOVERNANCE.SFX_RUN': 'sfx-d1110'}},
                            'row_access': {'policy': 'DB.GOVERNANCE.TENANT', 'columns': ['CUSTOMER_ID']}}}
    calls = render_governance(policies)
    assert any('modify column "EMAIL" set tag' in sql for sql in calls)
    assert any('set masking policy "DB"."GOVERNANCE"."EMAIL_MASK" force' in sql for sql in calls)
    assert any('add row access policy "DB"."GOVERNANCE"."TENANT" on ("CUSTOMER_ID")' in sql for sql in calls)
    calls = render_governance(policies, existing=[('DB.GOVERNANCE.TENANT',)])
    assert not any('add row access policy' in sql for sql in calls)
    with pytest.raises(ValueError, match='Different row access'):
        render_governance(policies, existing=[('DB.GOVERNANCE.OTHER',)])
    with pytest.raises(ValueError, match='database.schema.name'):
        render_governance({'customer': {'masking': [{'column': 'EMAIL', 'policy': 'BAD'}]}})
    assert not any('create ' in sql.lower() for sql in calls)
    config = yaml.safe_load((ROOT.parent / 'dbt/dbt_project.yml').read_text())
    assert config['vars']['governance_policies'] == {}
    assert '{{ reapply_governance(results) }}' in config['on-run-end']


def test_utc_records_and_pending_until_caught_up(monkeypatch):
    pacific = timezone(timedelta(hours=-8))
    cur = Cursor([(['STAMP'], [(HOUR.astimezone(pacific),)])])
    assert ledger.records(cur, 'select stamp')[0]['stamp'].isoformat() == '2026-11-10T12:00:00+00:00'
    q = query()
    q['start_time'] += timedelta(minutes=10)
    before = ledger.summarize([q], [meter()], [q], HOUR)
    after = ledger.summarize([q], [meter()], [q], HOUR + timedelta(minutes=11))
    assert before['groups']['total'][0]['credits'] == 'pending'
    assert after['groups']['total'][0]['credits'] == 0.6
    import snowflake.connector
    from cryptography.hazmat.primitives import serialization
    monkeypatch.setattr(serialization, 'load_pem_private_key', lambda *a, **kw:
                        SimpleNamespace(private_bytes=lambda *args: b'dummy'))
    monkeypatch.setattr(snowflake.connector, 'connect', lambda **kw: kw)
    for key in ('ACCOUNT', 'USER', 'ROLE', 'DATABASE', 'PRIVATE_KEY'):
        monkeypatch.setenv('SNOWFLAKE_' + key, 'dummy')
    params = sfx_conn.connect('ops', 'ledger')
    assert params['session_parameters']['TIMEZONE'] == 'UTC'
    assert json.loads(params['session_parameters']['QUERY_TAG'])['phase'] == 'ledger'


class Inventory:
    def __init__(self, name_mode=False, denied=None):
        self.name_mode = name_mode
        self.denied = denied
        self.calls = []
        self.deleted = set()
        self.user_dropped = False

    def execute(self, sql):
        self.calls.append(sql)
        if sql == self.denied:
            raise ProgrammingError(msg='insufficient privileges', errno=3001)
        rows = []
        name = 'SFX_D1110_EXTRA' if self.name_mode else 'EXTRA'
        comment = '' if self.name_mode else 'sfx-d1110'
        if sql.startswith('SHOW DATABASES'):
            rows = [dict(name='SFX_D1110_AFTER', comment=''),
                    dict(name=name, comment=comment),
                    dict(name='DROPPED_USER$FOREIGN', comment='', owner='OTHER')]
            if self.user_dropped and 'DROP DATABASE IF EXISTS "DROPPED_USER$EXTRA_123456" CASCADE' not in self.calls:
                rows += [dict(name='DROPPED_USER$EXTRA_123456', comment='', owner='OTHER')]
        elif sql.startswith('SHOW SCHEMAS'):
            rows = [dict(name='GOVERNANCE', comment='sfx-d1110')] if not self.name_mode else [dict(name=name, comment=comment)]
        elif sql == 'SHOW USERS':
            rows = [] if self.user_dropped else [dict(name=name, comment=comment)]
        elif sql.startswith('SHOW '):
            rows = [dict(name=name, comment=comment, database_name='SFX_D1110_AFTER', schema_name='GOVERNANCE')]
        elif sql.startswith('DROP USER'):
            self.user_dropped = True
        self.description = [(k,) for k in (list(rows[0]) if rows else ['name', 'comment'])]
        self.rows = [tuple(row[k[0]] for k in self.description) for row in rows]

    def fetchall(self):
        return self.rows


@pytest.mark.parametrize('name_mode', [True, False])
def test_inventory_matches_names_and_comments(name_mode):
    objects, denied = teardown.discover(Inventory(name_mode), 'sfx-d1110')
    assert not denied
    assert {obj.kind for obj in objects} == {'DATABASE', 'SCHEMA', 'TASK', 'STAGE', 'TAG',
        'USER', 'ROLE', 'WAREHOUSE', 'RESOURCE MONITOR', 'INTEGRATION', 'APPLICATION', 'COMPUTE POOL', 'SERVICE'}
    commands = teardown.plan(objects)
    assert any('ALTER COMPUTE POOL' in sql for sql in commands)
    assert any('DROP TAG' in sql for sql in commands)
    assert next(i for i, s in enumerate(commands) if s.startswith('DROP SERVICE')) < next(i for i, s in enumerate(commands) if s.startswith('DROP COMPUTE POOL'))
    assert not any('FOREIGN' in sql for sql in commands)


@pytest.mark.parametrize('command', ['SHOW INTEGRATIONS', 'SHOW APPLICATIONS', 'SHOW COMPUTE POOLS',
    'SHOW SERVICES IN ACCOUNT', 'SHOW TAGS IN SCHEMA "SFX_D1110_AFTER"."GOVERNANCE"'])
def test_inventory_privilege_per_type(command, capsys):
    _, denied = teardown.discover(Inventory(denied=command), 'sfx-d1110')
    assert denied
    assert 'not visible to role' in capsys.readouterr().out


def test_dropped_user_database_sweep_and_guard(capsys):
    cur = Inventory()
    teardown.cleanup(cur, 'sfx-d1110')
    assert 'DROP DATABASE IF EXISTS "DROPPED_USER$EXTRA_123456" CASCADE' in cur.calls
    assert not any('DROP DATABASE IF EXISTS "DROPPED_USER$FOREIGN"' in sql for sql in cur.calls)
    assert 'unattributed DROPPED_USER database; not removed' in capsys.readouterr().out
    cur = Inventory()
    teardown.cleanup(cur, 'sfx-d1110', dry_run=True)
    assert not any(sql.startswith('DROP ') for sql in cur.calls)


def dummy_env(tmp_path):
    return {**os.environ, **{'SNOWFLAKE_' + k: 'dummy-' + k.lower()
            for k in ('ACCOUNT', 'USER', 'ROLE', 'WAREHOUSE', 'DATABASE', 'PRIVATE_KEY')},
            'PATH': str(tmp_path / 'bin') + os.pathsep + os.environ['PATH']}


def test_connection_modes_and_merge(tmp_path):
    directory = tmp_path / '.snowflake'
    directory.mkdir()
    config = directory / 'connections.toml'
    config.write_text('# keep\n[other]\naccount = "untouched"\n[sfx_d1110]\npassword = "dummy"\n')
    env = dummy_env(tmp_path)
    snowconvert.configure_connection(tmp_path, env)
    doc = tomlkit.parse(config.read_text())
    assert doc['other'] == {'account': 'untouched'}
    assert '# keep' in config.read_text()
    assert set(doc['sfx_d1110']) == {'account', 'user', 'role', 'warehouse', 'database', 'authenticator', 'private_key_file'}
    assert doc['sfx_d1110']['authenticator'] == 'SNOWFLAKE_JWT'
    key = Path(doc['sfx_d1110']['private_key_file'])
    assert key.read_text() == env['SNOWFLAKE_PRIVATE_KEY']
    assert directory.stat().st_mode & 0o777 == 0o700
    assert config.stat().st_mode & 0o777 == key.stat().st_mode & 0o777 == 0o600
    snowconvert.configure_connection(tmp_path, env)
    assert tomlkit.parse(config.read_text()) == doc


@pytest.mark.parametrize('rejected', [False, True])
def test_fake_scai_receives_connection_and_keeps_raw(tmp_path, rejected):
    repo = tmp_path / 'repo'
    source = repo / 'warehouse/teradata'
    source.mkdir(parents=True)
    (source / 'input.bteq').write_text('select 1;')
    xml = repo / 'etl/informatica'
    xml.mkdir(parents=True)
    (xml / 'workflow.XML').write_text('<POWERMART/>')
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    tool = bin_dir / 'scai'
    tool.write_text('#!/usr/bin/python3\nimport os, pathlib, sys\n'
                    'assert os.environ["SNOWFLAKE_CONNECTION"] == "sfx_d1110"\n'
                    'assert "SNOWFLAKE_PRIVATE_KEY" not in os.environ\n'
                    'if sys.argv[1] == "init": pathlib.Path(sys.argv[2]).mkdir()\n'
                    + ('print("key-pair authentication not supported"); sys.exit(1)\n' if rejected else 'print("raw output unchanged")\n'))
    tool.chmod(0o700)
    env = dummy_env(tmp_path)
    code = snowconvert.run(repo, tmp_path, env)
    assert code == (2 if rejected else 0)
    output = next((repo / 'warehouse/snowconvert/raw').iterdir())
    summary = json.loads((output / 'summary.json').read_text())
    assert len(summary) == (1 if rejected else 4)
    if not rejected:
        assert summary[-1]['command'] == ['code', 'convert']
        assert (output / '03.stdout').read_bytes() == b'raw output unchanged\n'


def test_snowconvert_missing_empty_and_symlink(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(snowconvert.shutil, 'which', lambda *a, **kw: None)
    assert snowconvert.run(tmp_path, tmp_path, {}) == 2
    assert 'Install the SnowConvert AI CLI' in capsys.readouterr().out
    assert not (tmp_path / '.snowflake').exists()
    monkeypatch.setattr(snowconvert.shutil, 'which', lambda *a, **kw: 'scai')
    assert snowconvert.run(tmp_path, tmp_path, {}) == 0
    assert 'No SQL/BTEQ or Informatica XML input found' in capsys.readouterr().out
    (tmp_path / '.snowflake').symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        snowconvert.configure_connection(tmp_path, dummy_env(tmp_path))
