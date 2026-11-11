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
