"""Measure audit lake and JDBC outputs against shipped dbt models, not batch tables."""
import hashlib
import os
from pathlib import Path
import re

import duckdb
import psycopg
from psycopg import sql
import sqlglot
from sqlglot import exp

from .spark_billing import schemas, uppercase_columns

ROOT = Path(__file__).resolve().parents[3]
INPUTS = {
    'audit_actor_activity_join': (('audit', 'AUDIT_EVENT'), ('users', 'USER_ACTIVITY_DAILY'), ('users', 'LOGIN_EVENT')),
    'audit_archive_resort': (('audit', 'AUDIT_EVENT_ARCHIVE'),),
    'audit_daily_summary': (('audit', 'AUDIT_EVENT'),),
    'compliance_flag_rules': (('audit', 'COMPLIANCE_FLAG'),),
    'lake_compaction_audit': (),
}
JDBC = {'audit_daily_summary': 'SPARK_AUDIT_SUMMARY', 'compliance_flag_rules': 'SPARK_COMPLIANCE_REVIEW'}


def render_model(text):
    text = re.sub(r'\{\{\s*config\(.*?\)\s*\}\}', '', text, flags=re.S)
    text = re.sub(r"\{\{\s*source\('spark_(audit|users)',\s*'(\w+)'\)\s*\}\}", r'AUDIT_SPARK_INPUT.\2', text)
    text = re.sub(r"\{\{\s*ref\('audit_daily_summary'\)\s*\}\}", 'SPARK.AUDIT_DAILY_SUMMARY', text)
    if '{{' in text or '{%' in text:
        raise ValueError('Unsupported audit dbt template')
    query = sqlglot.parse_one(text, read='snowflake')
    for node in list(query.find_all(exp.ByteLength)):
        node.replace(exp.Anonymous(this='OCTET_LENGTH', expressions=[
            exp.Anonymous(this='ENCODE', expressions=[node.this.copy()])]))
    return query.sql(dialect='duckdb')


def jdbc_snapshot(connection, dsn, table, destination):
    with psycopg.connect(dsn) as source:
        # Job/target names come from fixed INPUTS/JDBC contracts; SQL is shipped dbt and metadata types are allowlisted.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        cursor = source.execute(sql.SQL('SELECT * FROM {}.{}').format(sql.Identifier('sfx_audit'), sql.Identifier(table.lower())))
        types = {20: 'BIGINT', 21: 'SMALLINT', 23: 'INTEGER', 25: 'VARCHAR', 1043: 'VARCHAR',
                 1082: 'DATE', 1114: 'TIMESTAMP'}
        definitions = []
        for column in cursor.description:
            if column.type_code not in types:
                raise ValueError('Unsupported audit JDBC type: ' + str(column.type_code))
            definitions.append('"' + column.name.upper().replace('"', '""') + '" ' + types[column.type_code])
        rows = cursor.fetchall()
    # Job/target names come from fixed INPUTS/JDBC contracts; SQL is shipped dbt and metadata types are allowlisted.
    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
    connection.execute('CREATE TABLE ' + destination + ' (' + ','.join(definitions) + ')')
    if rows:
        connection.executemany('INSERT INTO ' + destination + ' VALUES (' + ','.join('?' for _ in definitions) + ')', rows)


def materialize(before, after, objects, namespace, dsn=None):
    runtime = ROOT / 'etl/spark/.data' / namespace
    ready, errors, evidence, loaded = set(), {}, {}, set()
    before.execute('CREATE SCHEMA IF NOT EXISTS SFX_SPARK')
    after.execute('CREATE SCHEMA IF NOT EXISTS SPARK')
    after.execute('CREATE SCHEMA IF NOT EXISTS AUDIT_SPARK_INPUT')
    definitions = schemas()
    jobs = {obj['name'] for obj in objects if obj['system'] == 'spark' and obj['subject_area'] == 'audit'}
    for name, tables in INPUTS.items():
        if name not in jobs:
            continue
        target = 'SPARK.' + name.upper()
        paths = sorted((runtime / 'lake/audit' / name).glob('*.parquet'))
        try:
            inputs = []
            for area, table in tables:
                files = sorted((runtime / 'landing' / area / table).glob('*.psv'))
                if not files:
                    raise ValueError('Missing Spark landing inputs: ' + table)
                inputs.extend(files)
                if table not in loaded:
                    columns = {column: kind.replace('TEXT', 'VARCHAR') for column, kind in definitions[table]}
                    after.read_csv([str(path) for path in files], delimiter='|', header=True, columns=columns,
                                   na_values='', quotechar='"', escapechar='"').create('AUDIT_SPARK_INPUT.' + table)
                    loaded.add(table)
            if name == 'lake_compaction_audit':
                if 'SPARK.AUDIT_DAILY_SUMMARY' not in ready:
                    raise ValueError('Converted audit_daily_summary dependency unavailable')
                inputs = sorted((runtime / 'lake/audit/audit_daily_summary').glob('*.parquet'))
            if not paths or not inputs:
                raise ValueError('Missing Spark parquet output or inputs')
            if min(path.stat().st_mtime for path in paths) < max(path.stat().st_mtime for path in inputs):
                raise ValueError('Spark output predates inputs; rerun legacy job')
            model = ROOT / 'warehouse/dbt/models/spark' / name / (name + '.sql')
            before.read_parquet([str(path) for path in paths]).create('SFX_' + target)
            # Job/target names come from fixed INPUTS/JDBC contracts; SQL is shipped dbt and metadata types are allowlisted.
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            after.execute('CREATE TABLE ' + target + ' AS ' + render_model(model.read_text()))
            uppercase_columns(before, 'SFX_' + target)
            uppercase_columns(after, target)
            ready.add(target)
            evidence[name] = {'legacy_output': 'lake/audit/' + name,
                'input_sha256': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs},
                'build': 'initial table; physical partition/file order not compared'}
        except (duckdb.Error, ValueError, OSError) as error:
            errors[target] = 'Audit Spark parity materialization failed: ' + str(error)
            continue
        if name in JDBC:
            try:
                jdbc_snapshot(before, dsn or os.environ.get('SPARK_SOURCE_DSN',
                    'host=127.0.0.1 port=55432 dbname=sfx_teradata user=etl_batch password=Fake-sfx1119-jdbc'),
                    JDBC[name], 'SFX_' + target + '_JDBC')
                # Job/target names come from fixed INPUTS/JDBC contracts; SQL is shipped dbt and metadata types are allowlisted.
                # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                after.execute('CREATE TABLE ' + target + '_JDBC AS SELECT * FROM ' + target)
                ready.add(target + '_JDBC')
                evidence[name]['jdbc_output'] = 'sfx_audit.' + JDBC[name]
            except (duckdb.Error, psycopg.Error, ValueError) as error:
                errors[target + '_JDBC'] = 'Audit JDBC output unavailable: ' + type(error).__name__
    return ready, errors, evidence
