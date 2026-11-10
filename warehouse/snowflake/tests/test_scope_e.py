from contextlib import nullcontext
import csv
from datetime import datetime, timezone
import importlib.util
from io import StringIO
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import consumer_reads
import task_dag
import teardown
from test_operations import Cursor, InventoryCursor, roles

NOW = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)


def test_compat_shapes_normal_and_empty():
    spec = yaml.safe_load((ROOT / 'fixture_columns.yml').read_text())
    sql = (ROOT / 'migrations/V004__compat.sql').read_text()
    views = dict(re.findall(r'CREATE OR REPLACE VIEW COMPAT\.(\w+).*?\nAS (SELECT.*?);', sql, re.S))
    expected = dict(CUSTOMER='CUSTOMER_ACCOUNT', ACCOUNT='CUSTOMER_ACCOUNT', INVOICE='INVOICE_HDR',
                    INVOICE_LINE='INVOICE_LINE', PAYMENT='PAYMENT', GL_JOURNAL_LINE='GL_JOURNAL_LINE')
    assert set(views) == {*expected, 'DAILY_USAGE'}
    with sqlite3.connect(':memory:') as db:
        for area in ('billing', 'users'):
            db.execute(f"attach database ':memory:' as RAW_{area.upper()}")
            for table, columns in spec[area].items():
                declaration = ','.join(f'{c} NUMERIC' for c in columns)
                db.execute(f'create table RAW_{area.upper()}.{table} ({declaration})')
                with (ROOT / 'fixtures/landing' / area / table / '20261101.psv').open() as stream:
                    rows = list(csv.reader(stream, delimiter='|'))[1:]
                db.executemany(f'insert into RAW_{area.upper()}.{table} values ({",".join("?" for _ in columns)})', rows)
        for name, query in views.items():
            cursor = db.execute(query)
            assert len(cursor.fetchall()) == 20
            columns = [c[0] for c in cursor.description]
            if name in expected:
                wanted = list(spec['billing'][expected[name]])
                if name == 'CUSTOMER':
                    wanted += ['OWNER_FIRST_NAME', 'OWNER_LAST_NAME', 'OWNER_EMAIL']
                assert columns == wanted
            else:
                assert columns == ['CUSTOMER_ID', 'USAGE_DATE', 'CURRENCY_CODE', 'QUANTITY', 'AMOUNT']
        for area in ('billing', 'users'):
            for table in spec[area]:
                db.execute(f'delete from RAW_{area.upper()}.{table}')
        assert all(db.execute(query).fetchall() == [] for query in views.values())
    assert 'GRANT SELECT ON FUTURE VIEWS' not in sql
    assert 'GRANT USAGE ON SCHEMA COMPAT TO ROLE SFX_D1110_ROLE' in sql
    assert 'GRANT SELECT ON ALL VIEWS IN SCHEMA COMPAT TO ROLE SFX_D1110_ROLE' in sql
    roles.validate(roles.statements())


def test_repeatable_procedure_discovery_and_comments(tmp_path):
    from schemachange.session.Script import get_all_scripts_recursively
    config = yaml.safe_load((ROOT / 'schemachange-config.yml').read_text())
    deploy_root = (ROOT / config['root-folder']).resolve()
    assert deploy_root == ROOT
    assert (ROOT / 'procedures').is_relative_to(deploy_root)
    for path in (ROOT / 'procedures').glob('R__*.sql'):
        for statement in re.split(r'(?im)(?=^CREATE )', path.read_text()):
            if statement.startswith('CREATE '):
                assert re.search(r"COMMENT\s*=\s*'sfx-d1110[^']*'", statement)
        assert 'sfx-d1110' in path.read_text()
    folder = tmp_path / 'procedures'
    folder.mkdir()
    (folder / 'R__ORCH__example.sql').write_text("CREATE PROCEDURE x() RETURNS VARCHAR LANGUAGE SQL COMMENT='sfx-d1110 test' AS $$ BEGIN RETURN 'ok'; END; $$;")
    scripts = get_all_scripts_recursively(tmp_path)
    assert scripts['r__orch__example.sql'].type == 'R'


def test_dag_matches_map():
    module_spec = importlib.util.spec_from_file_location('renderer', ROOT / 'tools/render_dag.py')
    renderer = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(renderer)
    assert renderer.TARGET.read_text() == renderer.render()
    steps = task_dag.step_map()
    assert steps['session_b']['after'] == steps['session_c']['after'] == ['worklet_a']
    assert steps['session_d']['after'] == ['session_b', 'session_c']
    sql = renderer.render()
    assert sql.count('CREATE OR REPLACE TASK') == len(steps)
    assert sql.count('"phase":"task_dag"') == len(steps)
    assert 'SYSTEM$SET_RETURN_VALUE' in sql and 'SYSTEM$GET_PREDECESSOR_RETURN_VALUE' in sql
    assert 'RESUME' not in sql
    from snowflake.connector.util_text import split_statements
    statements = [statement for statement, _ in split_statements(StringIO(sql))]
    session_d = next(s for s in statements if s.startswith('CREATE OR REPLACE TASK ORCH.DAG_SESSION_D'))
    assert 'AS EXECUTE IMMEDIATE $$ BEGIN' in session_d
    assert "CALL SYSTEM$SET_RETURN_VALUE('CONTINUE')" in session_d
    assert 'END; $$' in session_d


class DagCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))

    def fetchone(self):
        return (NOW,)


@pytest.mark.parametrize('outcome', ['success', 'empty', 'failure'])
def test_dag_success_timeout_and_failure_cleanup(monkeypatch, outcome):
    cursor = DagCursor()
    steps = task_dag.step_map()
    history = [dict(name=s['task'], state='SUCCEEDED', graph_run_group_id='graph') for s in steps.values()]
    if outcome == 'empty':
        history = []
    elif outcome == 'failure':
        history[0]['state'] = 'FAILED'

    def fake_records(cursor, sql, params=()):
        cursor.calls.append((sql, params))
        if sql.startswith('SHOW'):
            return [dict(name=s['task'], state='suspended') for s in steps.values()]
        assert 'SCHEDULED_TIME_RANGE_START=>TO_TIMESTAMP_LTZ(%s)' in sql
        return history

    monkeypatch.setattr(task_dag, 'records', fake_records)
    clock = iter((0, 181))
    monkeypatch.setattr(task_dag.time, 'monotonic', lambda: next(clock))
    if outcome == 'success':
        assert task_dag.run_once(cursor) == history
    else:
        with pytest.raises(TimeoutError if outcome == 'empty' else RuntimeError):
            task_dag.run_once(cursor)
    sql = [s for s, _ in cursor.calls]
    assert 'ALTER TASK ORCH.DAG_START RESUME' not in sql
    assert sql.count('ALTER TASK ORCH.DAG_START SUSPEND') == 2
    for step in steps.values():
        assert sql.count(f"ALTER TASK ORCH.{step['task']} SUSPEND") == 2
    assert any(s == 'EXECUTE TASK ORCH.DAG_START' for s in sql)
    assert any('CANCEL_ONGOING_EXECUTIONS' in s for s in sql) == (outcome != 'success')


def test_dag_suspension_verification(monkeypatch):
    monkeypatch.setattr(task_dag, 'records', lambda *a: [])
    with pytest.raises(RuntimeError, match='suspension verification failed'):
        task_dag.suspend_tasks(DagCursor(), task_dag.step_map())


def read(qid='q1', rows=5, consumer='compat-smoke'):
    return dict(query_id=qid, start_time=NOW, rows_produced=rows,
                query_text='select * from "SFX_D1110_AFTER"."COMPAT"."INVOICE"', consumer=consumer)


def test_consumers_union_dedupe_objects_pending_and_empty():
    assert consumer_reads.summarize([], [], None) == []
    assert consumer_reads.compat_objects('select * from compat.account join COMPAT.CUSTOMER using (customer_id)') == ['COMPAT.ACCOUNT', 'COMPAT.CUSTOMER']
    result = consumer_reads.summarize([read()], [read(rows=99), read('q2')], NOW)
    assert result[0]['reads'] == 2 and result[0]['rows_produced'] == 10
    assert result[0]['objects_read'] == ['COMPAT.INVOICE']
    assert result[0]['account_usage'] == 'pending'
    assert consumer_reads.summarize([read()], [read()], NOW)[0]['account_usage'] == 'landed'
    assert consumer_reads.summarize([], [read(rows=None)], None)[0]['rows_produced'] == 'pending'


def test_consumer_sql_filters_and_parameters():
    columns = list(read())
    cursor = Cursor([(columns, [tuple(read().values())]), (columns, []), (['QUERY_MAX_START'], [(NOW,)])])
    landed, recent, fresh = consumer_reads.read_history(cursor, 'sfx-d1110', 24)
    assert landed == [read()] and recent == [] and fresh == NOW
    for sql, params in cursor.calls[:2]:
        assert ':act::VARCHAR' in sql and "'consumers'" in sql
        assert ':run::VARCHAR = %s' in sql
        assert 'QUERY_TYPE' in sql and 'EXECUTION_STATUS' in sql
        assert params[-2:] == ('%sfx-d1110%', 'sfx-d1110')


def test_consumers_missing_and_argument_error(monkeypatch, capsys):
    class Connection:
        def cursor(self):
            return nullcontext(None)
    monkeypatch.setattr(consumer_reads, 'connect', lambda *a: nullcontext(Connection()))
    monkeypatch.setattr(consumer_reads, 'read_history', lambda *a: ([], [], None))
    monkeypatch.setattr(sys, 'argv', ['consumer_reads.py'])
    consumer_reads.main()
    output = capsys.readouterr().out
    assert all(name + ' | no reads yet' in output for name in consumer_reads.EXPECTED)
    monkeypatch.setattr(sys, 'argv', ['consumer_reads.py', '--hours', '0'])
    with pytest.raises(SystemExit):
        consumer_reads.main()


def test_teardown_discovers_new_schemas_and_tasks():
    class NewCursor(InventoryCursor):
        def execute(self, sql):
            super().execute(sql)
            if sql.startswith('SHOW SCHEMAS'):
                self.rows += [('COMPAT', 'sfx-d1110 compat'), ('ORCH', 'sfx-d1110 orchestration')]
            if sql.startswith('SHOW TASKS') and '"ORCH"' in sql:
                self.rows = [(s['task'], 'sfx-d1110 placeholder') for s in task_dag.step_map().values()]
    objects, denied = teardown.discover(NewCursor(), 'sfx-d1110')
    assert not denied
    commands = teardown.plan(objects)
    assert 'DROP SCHEMA IF EXISTS "SFX_D1110_AFTER"."COMPAT" CASCADE' in commands
    assert 'DROP SCHEMA IF EXISTS "SFX_D1110_AFTER"."ORCH" CASCADE' in commands
    assert 'ALTER TASK "SFX_D1110_AFTER"."ORCH"."DAG_START" SUSPEND' in commands


@pytest.mark.parametrize('decision, expected', [
    ('distinct', 'select distinct * from source_rows'),
    ('keep_all', 'select * from source_rows'),
    (None, 'SET table decision required for example_model: choose distinct or keep_all'),
    ('invalid', 'SET table decision required for example_model: choose distinct or keep_all'),
])
def test_set_decision_with_offline_dbt(tmp_path, decision, expected):
    (tmp_path / 'macros').mkdir()
    shutil.copyfile(ROOT.parent / 'dbt/macros/set_table_semantics.sql', tmp_path / 'macros/set_table_semantics.sql')
    (tmp_path / 'analyses').mkdir()
    (tmp_path / 'analyses/check.sql').write_text("{{ log(set_table_semantics('source_rows', 'example_model') | trim, info=True) }} select 1")
    (tmp_path / 'dbt_project.yml').write_text("name: offline_set_test\nversion: '1.0'\nconfig-version: 2\nprofile: sfx_warehouse\n")
    shutil.copyfile(ROOT.parent / 'dbt/profiles.yml', tmp_path / 'profiles.yml')
    env = {**os.environ, 'DBT_ENV_SECRET_SNOWFLAKE_PRIVATE_KEY': 'offline_dummy',
           'SFX_QUERY_TAG': '{}', 'DBT_SEND_ANONYMOUS_USAGE_STATS': 'false'}
    env.update({'SNOWFLAKE_' + key: 'offline_dummy' for key in ('ACCOUNT', 'USER', 'ROLE', 'DATABASE')})
    result = subprocess.run([str(Path(sys.executable).with_name('dbt')), 'parse',
        '--project-dir', str(tmp_path), '--profiles-dir', str(tmp_path), '--vars',
        json.dumps({'set_table_decisions': {} if decision is None else {'example_model': decision}})],
        env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert expected in result.stdout, result.stdout
    assert (result.returncode == 0) == (decision in ('distinct', 'keep_all')), result.stdout
