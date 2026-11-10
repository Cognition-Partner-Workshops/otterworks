import json
from pathlib import Path

import pytest
import yaml

from parity.inventory import inventory, landing_sources
from parity.harness import COMMENT, control_ddl, merge_sql, source_plan, tag, ESTATE
from sfx_conn import query_tag
from parity.harness import owner_effort, require_owner


def test_control_location(monkeypatch):
    from parity.harness import control_table
    monkeypatch.delenv('PC_CONTROL_SCHEMA', raising=False)
    monkeypatch.delenv('PC_CONTROL_TABLE', raising=False)
    assert control_table() == 'SFX_D1110_AFTER.MIGRATION_CONTROL.MAPPINGS'
    for setting in ('PC_CONTROL_SCHEMA', 'PC_CONTROL_TABLE'):
        for value in ('', 'bad; DROP TABLE x'):
            with monkeypatch.context() as patch:
                patch.setenv(setting, value)
                with pytest.raises(ValueError, match=setting):
                    control_table()


def test_setup_control_ddl(monkeypatch):
    from parity import harness
    statements = []

    class Cursor:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def cursor(self):
            return self
        def execute(self, sql, params=None):
            statements.append(sql)
        def fetchone(self):
            return (0,)

    monkeypatch.setenv('PC_CONTROL_SCHEMA', 'MIGRATION_CONTROL')
    monkeypatch.setenv('PC_CONTROL_TABLE', 'MAPPINGS')
    monkeypatch.setattr(harness, 'connection', lambda *args: Cursor())
    harness.setup()
    control = [sql for sql in statements if 'SFX_D1110_AFTER.MIGRATION_CONTROL' in sql]
    assert len(control) == 22
    assert control[0] == harness.control_ddl()
    assert control[1] == ('ALTER TABLE SFX_D1110_AFTER.MIGRATION_CONTROL.MAPPINGS '
                          'ADD COLUMN IF NOT EXISTS OWNER_EFFORT VARCHAR')
    assert all(sql == harness.merge_sql() for sql in control[2:])


def test_inventory():
    rows = inventory()
    assert len(rows) == 20
    assert len({r['target_table'] for r in rows}) == 20
    assert {r['folder'] for r in rows} == {'SFX_BILLING', 'SFX_CONTENT', 'SFX_AUDIT'}
    for row in rows:
        assert row['session'] == 's_' + row['mapping']
        assert row['workflow'] == 'wf_' + row['folder'] + '_DAILY'
        assert row['patterns'] and row['source_objects']
        assert row['key_columns'] or row['target_table'].startswith('STG_')
        assert row['dbt_model'].endswith('__' + row['target_table'].lower())


def test_override_and_exclusion_reason(tmp_path):
    path = tmp_path / 'sfx_billing.yml'
    path.write_text(yaml.safe_dump({'m_SFX_PAYMENT': {
        'key_columns': ['PAYMENT_ID'], 'exclude_columns': {'METHOD_CD': 'not comparable'},
        'dbt_model': 'custom_payment'}}))
    row = next(r for r in inventory(overrides=tmp_path) if r['mapping'] == 'm_SFX_PAYMENT')
    assert row['dbt_model'] == 'custom_payment'
    assert row['exclude_columns'] == {'METHOD_CD': 'not comparable'}
    path.write_text('m_SFX_PAYMENT:\n  exclude_columns:\n    METHOD_CD: ""\n')
    with pytest.raises(ValueError, match='explicit reasons'):
        inventory(overrides=tmp_path)


def test_empty_repository(tmp_path):
    assert inventory(repository=tmp_path) == []


def test_sql_and_tags():
    assert f"COMMENT = '{COMMENT}'" in control_ddl()
    sql = merge_sql()
    assert 'WHEN MATCHED AND t.owner_effort IS NULL' in sql
    assert 'UPDATE SET t.owner_effort=s.owner_effort' in sql
    assert 't.status=' not in sql
    assert "WHEN NOT MATCHED THEN INSERT" in sql
    value = json.loads(query_tag('load', 'parity_setup', tag('setup', 'm_SFX_PAYMENT')))
    assert {k: value[k] for k in ('run', 'act', 'step', 'mapping')} == {
        'run': 'sfx-d1110', 'act': 'scale', 'step': 'setup', 'mapping': 'm_SFX_PAYMENT'}


def test_source_resolution(tmp_path):
    plan = source_plan(ESTATE / 'tests/fixture/landing')
    assert len(plan) == len(landing_sources())
    assert {'PAYMENT', 'AUDIT_EVENT', 'APP_USER'} <= {p[0] for p in plan}
    assert all(p[2].name == '20261109.psv' for p in plan)
    assert 'GL_ACCOUNT' not in {p[0] for p in plan}
    with pytest.raises(FileNotFoundError):
        source_plan(tmp_path)


def test_owners():
    rows = inventory()
    assert sum(owner_effort(r) == 'act3-workflow' for r in rows) == 12
    assert sum(owner_effort(r) == 'migrations-page' for r in rows) == 8
    class Cursor:
        def execute(self, sql, params):
            assert params == ('m_SFX_PAYMENT',)
        def fetchall(self):
            return [('act3-workflow',)]
    require_owner(Cursor(), 'm_SFX_PAYMENT')
    with pytest.raises(ValueError, match='ownership mismatch'):
        require_owner(Cursor(), 'm_SFX_PAYMENT', 'migrations-page')
