import json
from pathlib import Path
import sys

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'snowflake'))
import pc_dag

FIXTURE = Path(__file__).parent / 'fixtures/pc_dag.yml'


def test_dag_sql():
    folder, root, tasks = pc_dag.load('sfx_billing', FIXTURE)
    assert folder == 'BILLING' and root == 'START'
    sql = pc_dag.create_sql(folder, tasks['PAYMENT'], tasks)
    assert 'SFX_D1110_AFTER.PC_BILLING.SFX_D1110_PC_BILLING_PAYMENT' in sql
    assert 'AFTER SFX_D1110_AFTER.PC_BILLING.SFX_D1110_PC_BILLING_START' in sql
    assert "COMMENT='run_token=sfx-d1110 expires=2026-11-24'" in sql
    assert 'WAREHOUSE=SFX_D1110_TRANSFORM_WH' in sql
    tag = json.loads(pc_dag.task_tag(folder))
    assert all(tag[k] == v for k, v in dict(run='sfx-d1110', act='scale', step='dag', folder='BILLING').items())
    assert 'SCHEDULE' not in sql and 'RESUME' not in sql


@pytest.mark.parametrize('change', ['cycle', 'warehouse', 'name', 'empty'])
def test_invalid_dag(tmp_path, change):
    doc = yaml.safe_load(FIXTURE.read_text())
    if change == 'cycle':
        doc['tasks']['PAYMENT']['after'] = ['FINISH']
    elif change == 'warehouse':
        doc['tasks']['START']['warehouse'] = 'OTHER_WH'
    elif change == 'name':
        doc['tasks']['bad-name'] = {'after': ['START'], 'sql': 'SELECT 1'}
    else:
        doc['tasks'] = {}
    path = tmp_path / 'dag.yml'
    path.write_text(yaml.safe_dump(doc))
    with pytest.raises(ValueError):
        pc_dag.load('billing', path)


def test_run_failure_suspends(monkeypatch):
    folder, root, tasks = pc_dag.load('billing', FIXTURE)
    calls = []
    class Cursor:
        def execute(self, sql, params=None):
            calls.append(sql)
            if sql.startswith('EXECUTE TASK'):
                raise RuntimeError('execution failed')
        def fetchone(self):
            return [None]
    monkeypatch.setattr(pc_dag, 'suspend', lambda *a: calls.append('SUSPEND VERIFIED'))
    with pytest.raises(RuntimeError, match='execution failed'):
        pc_dag.run_once(Cursor(), folder, root, tasks)
    assert calls[-1] == 'SUSPEND VERIFIED'
    assert sum('CANCEL_ONGOING' in c for c in calls) == 3


class RecordingCursor:
    def __init__(self, calls):
        self.calls = calls

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        if sql.startswith('EXECUTE TASK'):
            raise RuntimeError('graph started')

    def fetchone(self):
        return [None]


def test_run_once_builds_then_sets_batch_date(monkeypatch):
    folder, root, tasks = pc_dag.load('billing', FIXTURE)
    calls = []
    monkeypatch.setattr(pc_dag, 'suspend', lambda *a: None)
    with pytest.raises(RuntimeError, match='graph started'):
        pc_dag.run_once(RecordingCursor(calls), folder, root, tasks, load_date='20261110',
                        build=lambda: calls.append(('BUILD', None)))
    names = [sql for sql, _ in calls]
    config = next(i for i, sql in enumerate(names) if 'SET CONFIG' in sql)
    started = next(i for i, sql in enumerate(names) if sql.startswith('EXECUTE TASK'))
    assert names.index('BUILD') < config < started
    assert names[config] == 'ALTER TASK IDENTIFIER(%s) SET CONFIG=%s'
    assert calls[config][1][0] == 'SFX_D1110_AFTER.PC_BILLING.SFX_D1110_PC_BILLING_START'
    assert json.loads(calls[config][1][1]) == {'load_date': '20261110'}


def test_failed_build_skips_graph(monkeypatch):
    folder, root, tasks = pc_dag.load('billing', FIXTURE)
    calls = []
    monkeypatch.setattr(pc_dag, 'suspend', lambda *a: None)

    def build():
        raise RuntimeError('dbt build failed')
    with pytest.raises(RuntimeError, match='dbt build failed'):
        pc_dag.run_once(RecordingCursor(calls), folder, root, tasks, load_date='20261110', build=build)
    assert not any(sql.startswith('EXECUTE TASK') for sql, _ in calls)


def test_billing_decision_checks_batch_date():
    _, _, tasks = pc_dag.load('billing')
    sql = tasks['DEC_GL_POSTED']['sql']
    assert "SYSTEM$GET_TASK_GRAPH_CONFIG('load_date')" in sql
    assert 'MAX(REGEXP_SUBSTR' not in sql


def test_dbt_build_receives_load_date(monkeypatch):
    import run_dbt
    seen = []
    monkeypatch.setattr(run_dbt.subprocess, 'run', lambda command, **kw: seen.append(command))
    monkeypatch.setenv('SNOWFLAKE_PRIVATE_KEY', 'test-only')
    monkeypatch.setenv('SFX_COMMIT', 'test')
    monkeypatch.setattr(sys, 'argv', ['run_dbt.py', 'build', '--select', 'path:models/pc/billing',
                                      '--load-date', '20261110'])
    run_dbt.main()
    variables = json.loads(seen[0][seen[0].index('--vars') + 1])
    assert variables == {'phase': 'dbt', 'load_date': '20261110'}


def test_gl_journal_reuses_batch_keys():
    model = (Path(__file__).resolve().parents[2] / 'dbt/models/pc/billing/pc_billing__gl_journal_line.sql').read_text()
    assert model.index('{% set prior_keys') < model.index('{% set delete_load')
    assert 'pre_hook=[prior_keys, delete_load]' in model
    assert 'coalesce(PRIOR_ID' in model
