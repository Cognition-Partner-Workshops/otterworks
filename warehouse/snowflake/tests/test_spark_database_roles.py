"""Database-owner deployment must model the same scoped Spark privileges."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_database_roles_are_scoped_and_inherited():
    sql = (ROOT / 'migrations/V011__spark_database_roles.sql').read_text()
    statements = {s.strip() + ';' for s in sql.split(';') if s.strip()}
    transformer = 'SFX_D1110_AFTER.SFX_D1110_TRANSFORMER'
    analyst = 'SFX_D1110_AFTER.SFX_D1110_ANALYST'
    for schema in ('SPARK_RAW_BILLING', 'SPARK_RAW_DOCUMENTS', 'SPARK_RAW_USERS', 'SPARK_RAW_AUDIT', 'MART_SPARK'):
        provision = (ROOT / 'migrations/V010__spark_schemas.sql').read_text()
        assert f'CREATE SCHEMA IF NOT EXISTS {schema} WITH MANAGED ACCESS ' in provision
    for role in (transformer, analyst):
        assert f"CREATE DATABASE ROLE IF NOT EXISTS {role} COMMENT='sfx-d1110 spark access';" in statements
        assert f'GRANT DATABASE ROLE {role} TO ROLE SFX_D1110_ROLE;' in statements
    for area in ('BILLING', 'DOCUMENTS', 'USERS', 'AUDIT'):
        schema = 'SFX_D1110_AFTER.SPARK_RAW_' + area
        assert f'GRANT USAGE ON SCHEMA {schema} TO DATABASE ROLE {transformer};' in statements
        for objects in ('ALL TABLES', 'FUTURE TABLES'):
            assert f'GRANT SELECT ON {objects} IN SCHEMA {schema} TO DATABASE ROLE {transformer};' in statements
    assert f'GRANT USAGE, CREATE TABLE, CREATE VIEW, CREATE FUNCTION ON SCHEMA SFX_D1110_AFTER.MART_SPARK TO DATABASE ROLE {transformer};' in statements
    assert f'GRANT APPLY ON TAG SFX_D1110_AFTER.GOVERNANCE.SFX_RUN TO DATABASE ROLE {transformer};' in statements
    assert f'GRANT USAGE ON SCHEMA SFX_D1110_AFTER.GOVERNANCE TO DATABASE ROLE {transformer};' in statements
    assert f'GRANT USAGE ON SCHEMA SFX_D1110_AFTER.MART_SPARK TO DATABASE ROLE {analyst};' in statements
    for objects in ('ALL TABLES', 'FUTURE TABLES', 'ALL VIEWS', 'FUTURE VIEWS'):
        assert f'GRANT SELECT ON {objects} IN SCHEMA SFX_D1110_AFTER.MART_SPARK TO DATABASE ROLE {analyst};' in statements
    for statement in statements:
        assert not re.search(r'\b(?:ACCOUNT|WAREHOUSE|PUBLIC|OWNERSHIP|WITH GRANT OPTION)\b', statement)
        if ' TO DATABASE ROLE ' in statement:
            assert statement.endswith((' TO DATABASE ROLE ' + transformer + ';',
                                       ' TO DATABASE ROLE ' + analyst + ';'))
        if statement.endswith(' TO DATABASE ROLE ' + analyst + ';'):
            assert statement.startswith(('GRANT USAGE ON SCHEMA SFX_D1110_AFTER.MART_SPARK ',
                                         'GRANT SELECT ON '))
            assert 'SFX_D1110_AFTER.MART_SPARK' in statement
