from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'snowflake'))
import pc_dag
import pc_dag_audit

FX = 'SFX_D1110_AFTER.PC_FX_UNT9_AUDIT_WF.'
MERGES = {'s_m_SFX_AUDIT_EVENT': 'AUDIT_EVENT', 's_m_SFX_AUDIT_DAILY_SUMMARY': 'AUDIT_DAILY_SUMMARY',
          's_m_SFX_SECURITY_ALERT': 'SECURITY_ALERT'}


def fake_run(tmp_path):
    stg = tmp_path / 's_m_SFX_STG_AUDIT_EVENT'
    stg.mkdir()
    (stg / 'run.sql').write_text(f'create or replace transient table {FX}STG_AUDIT_EVENT as (select 1 as EVENT_ID);')
    (stg / 'compiled.sql').write_text('select 1 as EVENT_ID')
    for session, name in MERGES.items():
        path = tmp_path / session
        path.mkdir()
        (path / 'compiled.sql').write_text(f'select * from {FX}SOURCE_OF_{name}')
        # Shape of dbt-snowflake incremental run SQL: comment plus explicit transaction wrapper.
        (path / 'run.sql').write_text(f'-- back compat for old kwarg name\n  begin;\n    merge into {FX}{name} as '
                                      f'DBT_INTERNAL_DEST using {FX}{name}__dbt_tmp as DBT_INTERNAL_SOURCE on (1=1) '
                                      'when matched then update set X = 1\n;\n    commit;')
    return tmp_path


def test_generated_dag_matches_workflow(tmp_path):
    doc = pc_dag_audit.generate(fake_run(tmp_path), 'PC_FX_UNT9_AUDIT_WF', 'PC_AUDIT')
    out = tmp_path / 'audit.yml'
    import yaml
    out.write_text(yaml.safe_dump(doc))
    folder, root, tasks = pc_dag.load('SFX_AUDIT', out)
    assert folder == 'AUDIT' and root == 'START'
    assert {n: t.get('after', []) for n, t in tasks.items()} == {
        'START': [], 'STG_AUDIT_EVENT': ['START'], 'SECURITY_ALERT': ['START'],
        'AUDIT_EVENT': ['STG_AUDIT_EVENT'], 'AUDIT_DAILY_SUMMARY': ['AUDIT_EVENT']}
    assert not any('ARCHIVE' in n for n in tasks)
    for name, task in tasks.items():
        sql = pc_dag.create_sql(folder, task, tasks)
        assert 'SCHEDULE' not in sql and 'WAREHOUSE=SFX_D1110_TRANSFORM_WH' in sql
        assert 'PC_FX_UNT9' not in sql
        if name != 'START':
            assert 'SFX_D1110_AFTER.PC_AUDIT.' + name in task['sql']
            assert task['sql'].startswith('EXECUTE IMMEDIATE $$') and 'SELECT COUNT' not in task['sql']
    assert 'create or replace transient table SFX_D1110_AFTER.PC_AUDIT.STG_AUDIT_EVENT' in tasks['STG_AUDIT_EVENT']['sql']
    for name in MERGES.values():
        sql = tasks[name]['sql']
        assert sql.index('CREATE OR REPLACE TEMPORARY VIEW') < sql.index('merge into') < sql.index('DROP VIEW')


def test_rejects_wrong_target_and_scope(tmp_path):
    run = fake_run(tmp_path)
    with pytest.raises(ValueError):
        pc_dag_audit.generate(run, 'PC_FX_UNT9_AUDIT_WF', 'PC_CONTENT')
    (run / 's_m_SFX_AUDIT_EVENT/run.sql').write_text(f'merge into {FX}OTHER using x on 1=1')
    with pytest.raises(ValueError):
        pc_dag_audit.generate(run, 'PC_FX_UNT9_AUDIT_WF', 'PC_AUDIT')


def test_rejects_select_only_body(tmp_path):
    run = fake_run(tmp_path)
    (run / 's_m_SFX_SECURITY_ALERT/run.sql').write_text(f'select count(*) from {FX}SECURITY_ALERT')
    with pytest.raises(ValueError):
        pc_dag_audit.generate(run, 'PC_FX_UNT9_AUDIT_WF', 'PC_AUDIT')
