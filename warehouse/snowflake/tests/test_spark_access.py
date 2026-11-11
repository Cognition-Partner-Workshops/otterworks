"""The Spark fixture must load and publish without database CREATE SCHEMA."""
import importlib.util
from pathlib import Path
import re
import ast
import yaml
from unittest.mock import MagicMock

import pytest

import spark_landing

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('spark_roles', ROOT / 'roles/dry_run.py')
roles = importlib.util.module_from_spec(spec)
spec.loader.exec_module(roles)
RAW = {'SPARK_RAW_' + area.upper() for area in spark_landing.TABLES}


def test_spark_replacements_keep_consumer_grants():
    project = yaml.safe_load((ROOT.parent / 'dbt/dbt_project.yml').read_text())
    assert project['models']['sfx_warehouse']['spark'].get('+copy_grants') is True
    for path in (ROOT.parent / 'snowpark').glob('*.py'):
        if path.stem not in {'team_graph_components', 'users_risk_score', 'security_alert_anomaly',
                             'users_login_useragent_parse', 'doc_version_diff_stats'}:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'save_as_table':
                options = {kw.arg: kw.value for kw in node.keywords}
                if isinstance(options.get('mode'), ast.Constant) and options['mode'].value == 'overwrite':
                    value = options.get('copy_grants')
                    assert isinstance(value, ast.Constant) and value.value is True, path


def test_spark_schemas_and_scoped_grants():
    sql = '\n'.join(path.read_text() for path in (ROOT / 'migrations').glob('V*.sql'))
    schemas = set(re.findall(r'CREATE SCHEMA IF NOT EXISTS (\w+)', sql))
    assert RAW | {'MART_SPARK'} <= schemas
    plan = {statement for _, _, statement in roles.validate(roles.statements())}
    for schema in RAW:
        target = 'SFX_D1110_AFTER.' + schema
        assert f'GRANT USAGE, CREATE TABLE ON SCHEMA {target} TO ROLE SFX_D1110_LOADER;' in plan
        for scope in ('ALL', 'FUTURE'):
            assert f'GRANT SELECT, INSERT, DELETE ON {scope} TABLES IN SCHEMA {target} TO ROLE SFX_D1110_LOADER;' in plan
        for reader in ('TRANSFORMER', 'SNOWPARK'):
            assert f'GRANT USAGE ON SCHEMA {target} TO ROLE SFX_D1110_{reader};' in plan
            for scope in ('ALL', 'FUTURE'):
                assert f'GRANT SELECT ON {scope} TABLES IN SCHEMA {target} TO ROLE SFX_D1110_{reader};' in plan
    target = 'SFX_D1110_AFTER.MART_SPARK'
    for writer in ('TRANSFORMER', 'SNOWPARK'):
        assert f'GRANT USAGE, CREATE TABLE, CREATE VIEW, CREATE FUNCTION ON SCHEMA {target} TO ROLE SFX_D1110_{writer};' in plan
        assert f'GRANT USAGE ON SCHEMA SFX_D1110_AFTER.GOVERNANCE TO ROLE SFX_D1110_{writer};' in plan
        assert f'GRANT APPLY ON TAG SFX_D1110_AFTER.GOVERNANCE.SFX_RUN TO ROLE SFX_D1110_{writer};' in plan
    for reader in ('PARITY', 'ANALYST'):
        assert f'GRANT USAGE ON SCHEMA {target} TO ROLE SFX_D1110_{reader};' in plan
        for scope in ('ALL', 'FUTURE'):
            for kind in ('TABLES', 'VIEWS'):
                assert f'GRANT SELECT ON {scope} {kind} IN SCHEMA {target} TO ROLE SFX_D1110_{reader};' in plan
    assert not any('CREATE SCHEMA ON DATABASE' in statement for statement in plan)


def test_loader_does_not_create_schema(tmp_path, monkeypatch):
    connection = MagicMock()
    cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [(name,) for name, _ in spark_landing.SCHEMAS['PLAN_CATALOG']]
    cursor.fetchone.return_value = (1,)
    def execute(sql):
        if 'CREATE SCHEMA' in sql:
            raise PermissionError('loader has no CREATE SCHEMA')
    cursor.execute.side_effect = execute
    monkeypatch.setattr(spark_landing, 'connect', lambda *args, **kwargs: connection)
    monkeypatch.setattr(spark_landing, 'TABLES', {'billing': ['PLAN_CATALOG']})
    monkeypatch.setattr(spark_landing, 'inspect_files', lambda *args: ([], 1, 'digest'))
    assert spark_landing.load(tmp_path) == [('SPARK_RAW_BILLING.PLAN_CATALOG', 1, 1)]


@pytest.mark.parametrize('sql', [
    'GRANT APPLY ON TAG OTHER_DB.GOVERNANCE.SFX_RUN TO ROLE SFX_D1110_TRANSFORMER;',
    'GRANT APPLY ON TAG SFX_D1110_AFTER.GOVERNANCE.OTHER TO ROLE SFX_D1110_TRANSFORMER;',
    'GRANT APPLY ON TAG SFX_D1110_AFTER.GOVERNANCE.SFX_RUN TO ROLE SFX_D1110_ANALYST;',
    'GRANT INSERT ON ALL TABLES IN SCHEMA SFX_D1110_AFTER.MART_SPARK TO ROLE SFX_D1110_ANALYST;',
])
def test_spark_grants_remain_scoped(sql):
    with pytest.raises(ValueError):
        roles.validate([('bad.sql', 1, sql)])
