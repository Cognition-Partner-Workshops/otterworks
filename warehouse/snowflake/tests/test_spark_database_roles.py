"""Database-owner deployment must model the same scoped Spark privileges."""

import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[3]))
from warehouse.run_config import render as _run_render

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_database_roles_are_scoped_and_inherited():
    sql = _run_render((ROOT / 'migrations/V011__spark_database_roles.sql').read_text())
    statements = {s.strip() + ';' for s in sql.split(';') if s.strip()}
    transformer = _run_render('__RUN_DATABASE__.__RUN_DATABASE___TRANSFORMER')
    analyst = _run_render('__RUN_DATABASE__.__RUN_DATABASE___ANALYST')
    for schema in ('SPARK_RAW_BILLING', 'SPARK_RAW_DOCUMENTS', 'SPARK_RAW_USERS', 'SPARK_RAW_AUDIT', 'MART_SPARK'):
        provision = _run_render((ROOT / 'migrations/V010__spark_schemas.sql').read_text())
        assert f'CREATE SCHEMA IF NOT EXISTS {schema} WITH MANAGED ACCESS ' in provision
    for role in (transformer, analyst):
        assert _run_render(f"CREATE DATABASE ROLE IF NOT EXISTS {role} COMMENT='__RUN_TOKEN__ spark access';") in statements
        assert _run_render(f'GRANT DATABASE ROLE {role} TO ROLE __RUN_DATABASE___ROLE;') in statements
    for area in ('BILLING', 'DOCUMENTS', 'USERS', 'AUDIT'):
        schema = _run_render('__RUN_DATABASE__.SPARK_RAW_') + area
        assert f'GRANT USAGE ON SCHEMA {schema} TO DATABASE ROLE {transformer};' in statements
        for objects in ('ALL TABLES', 'FUTURE TABLES'):
            assert f'GRANT SELECT ON {objects} IN SCHEMA {schema} TO DATABASE ROLE {transformer};' in statements
    assert _run_render(f'GRANT USAGE, CREATE TABLE, CREATE VIEW, CREATE FUNCTION ON SCHEMA __RUN_DATABASE__.MART_SPARK TO DATABASE ROLE {transformer};') in statements
    assert _run_render(f'GRANT APPLY ON TAG __RUN_DATABASE__.GOVERNANCE.SFX_RUN TO DATABASE ROLE {transformer};') in statements
    assert _run_render(f'GRANT USAGE ON SCHEMA __RUN_DATABASE__.GOVERNANCE TO DATABASE ROLE {transformer};') in statements
    assert _run_render(f'GRANT USAGE ON SCHEMA __RUN_DATABASE__.MART_SPARK TO DATABASE ROLE {analyst};') in statements
    for objects in ('ALL TABLES', 'FUTURE TABLES', 'ALL VIEWS', 'FUTURE VIEWS'):
        assert _run_render(f'GRANT SELECT ON {objects} IN SCHEMA __RUN_DATABASE__.MART_SPARK TO DATABASE ROLE {analyst};') in statements
    for statement in statements:
        assert not re.search(r'\b(?:ACCOUNT|WAREHOUSE|PUBLIC|OWNERSHIP|WITH GRANT OPTION)\b', statement)
        if ' TO DATABASE ROLE ' in statement:
            assert statement.endswith((' TO DATABASE ROLE ' + transformer + ';',
                                       ' TO DATABASE ROLE ' + analyst + ';'))
        if statement.endswith(' TO DATABASE ROLE ' + analyst + ';'):
            assert statement.startswith((_run_render('GRANT USAGE ON SCHEMA __RUN_DATABASE__.MART_SPARK '),
                                         'GRANT SELECT ON '))
            assert _run_render('__RUN_DATABASE__.MART_SPARK') in statement
