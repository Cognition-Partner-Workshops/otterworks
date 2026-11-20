"""Compare actual legacy lake outputs with conversions fed the same Spark landing files."""
import importlib.util
from pathlib import Path
import re

import duckdb
import sqlglot
from sqlglot import exp

ROOT = Path(__file__).resolve().parents[3]


def schemas():
    path = ROOT/'etl/spark/jobs/py/common/schemas.py'
    spec = importlib.util.spec_from_file_location('spark_schemas', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SCHEMAS


def render_model(text):
    text = re.sub(r'\{\{\s*config\(.*?\)\s*\}\}', '', text, flags=re.S)
    text = re.sub(r'\{%\s*if is_incremental\(\)\s*%\}.*?\{%\s*endif\s*%\}', '', text, flags=re.S)
    text = re.sub(r"\{\{\s*source\('spark_users',\s*'(\w+)'\)\s*\}\}", r'SPARK_INPUT.\1', text)
    if '{{' in text or '{%' in text:
        raise ValueError('Unsupported dbt template')
    query = sqlglot.parse_one(text, read='snowflake')
    for node in list(query.find_all(exp.ToChar)):
        fmt = node.args.get('format')
        if not isinstance(fmt, exp.Literal) or fmt.this != 'YYYY-MM':
            raise ValueError('Unsupported Spark model date format')
        node.replace(exp.TimeToStr(this=node.this.copy(), format=exp.Literal.string('%Y-%m')))
    return query.sql(dialect='duckdb')


def uppercase_columns(connection, table):
    columns = [c[0] for c in connection.execute('DESCRIBE '+table).fetchall()]
    for column in columns:
        if column != column.upper():
            connection.execute('ALTER TABLE '+table+' RENAME COLUMN "'+column+'" TO "'+column.upper()+'"')
