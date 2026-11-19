"""Compare actual legacy lake outputs with conversions fed the same Spark landing files."""
import ast
import hashlib
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
    text = re.sub(r"\{\{\s*source\('spark_\w+',\s*'(\w+)'\)\s*\}\}", r'SPARK_INPUT.\1', text)
    if '{{' in text or '{%' in text:
        raise ValueError('Unsupported dbt template')
    query = sqlglot.parse_one(text, read='snowflake')
    for node in list(query.find_all(exp.ToChar)):
        fmt = node.args.get('format')
        if not isinstance(fmt, exp.Literal) or fmt.this != 'YYYY-MM':
            raise ValueError('Unsupported Spark model date format')
        node.replace(exp.TimeToStr(this=node.this.copy(), format=exp.Literal.string('%Y-%m')))
    return query.sql(dialect='duckdb')


def churn_query(connection):
    path = ROOT/'warehouse/snowpark/billing_churn_score.py'
    tree = ast.parse(path.read_text())
    fragments = [''.join(part.value for part in node.values if isinstance(part, ast.Constant) and isinstance(part.value, str))
                 for node in ast.walk(tree) if isinstance(node, ast.JoinedStr)]
    bodies = [re.search(r'\$\$(.*?)\$\$', text, re.S)[1] for text in fragments if re.search(r'\$\$(.*?)\$\$', text, re.S)]
    if len(bodies) != 1:
        raise ValueError('Expected one shipped Python UDF body')
    scope = {}
    exec(compile(bodies[0], str(path), 'exec'), scope)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute) and node.func.attr == 'select']
    if len(calls) != 1:
        raise ValueError('Expected one Snowpark projection')
    columns = []
    for node in calls[0].args:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            columns.append('"'+node.value+'"')
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'alias':
            udf = node.func.value
            args = [arg.args[0].value for arg in udf.args[1:]]
            connection.create_function('billing_score', scope['score'], ['VARCHAR','BIGINT'], 'DOUBLE', null_handling='special')
            columns.append('billing_score('+','.join(args)+') AS '+node.args[0].value)
        else:
            raise ValueError('Unsupported Snowpark projection')
    return 'SELECT '+', '.join(columns)+' FROM SPARK_INPUT.SUBSCRIPTION'


def uppercase_columns(connection, table):
    columns = [c[0] for c in connection.execute('DESCRIBE '+table).fetchall()]
    for column in columns:
        if column != column.upper():
            connection.execute('ALTER TABLE '+table+' RENAME COLUMN "'+column+'" TO "'+column.upper()+'"')


def materialize(before, after, objects, namespace, area='billing'):
    runtime = ROOT/'etl/spark/.data'/namespace
    landing = runtime/'landing'
    ready, errors, evidence = set(), {}, {}
    before.execute('CREATE SCHEMA IF NOT EXISTS SFX_SPARK')
    after.execute('CREATE SCHEMA IF NOT EXISTS SPARK')
    after.execute('CREATE SCHEMA IF NOT EXISTS SPARK_INPUT')
    definitions = schemas()
    loaded = {row[0] for row in after.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='SPARK_INPUT'").fetchall()}
    for obj in objects:
        if obj['system'] != 'spark' or obj['subject_area'] != area:
            continue
        name = obj['name']
        target = 'SPARK.'+name.upper()
        try:
            paths = sorted(p for p in runtime.glob('lake/*/'+name+'/**/*.parquet'))
            inputs = sorted(landing.glob('*/*/*.psv'))
            if not paths or not inputs:
                raise ValueError('Missing Spark parquet output or landing inputs')
            if min(path.stat().st_mtime for path in paths) < max(path.stat().st_mtime for path in inputs):
                raise ValueError('Spark output predates landing inputs; rerun legacy job')
            model = ROOT/'warehouse/dbt/models/spark'/name/(name+'.sql')
            if name != 'billing_churn_score' and not model.is_file():
                raise ValueError('no dbt model is shipped; a Snowpark or retained-Spark target is not runnable on DuckDB')
            for table_dir in sorted(landing.glob('*/*')):
                table = table_dir.name
                if not table_dir.is_dir() or table in loaded or table not in definitions:
                    continue
                columns = {column: kind.replace('TEXT','VARCHAR') for column, kind in definitions[table]}
                after.read_csv(str(table_dir/'*.psv'), delimiter='|', header=True, columns=columns,
                               na_values='', quotechar='"', escapechar='"').create('SPARK_INPUT.'+table)
                loaded.add(table)
            query = churn_query(after) if name == 'billing_churn_score' else render_model(model.read_text())
            before.read_parquet([str(path) for path in paths], hive_partitioning=True).create('SFX_SPARK.'+name.upper())
            after.execute('CREATE OR REPLACE TABLE '+target+' AS '+query)
            uppercase_columns(before, 'SFX_SPARK.'+name.upper())
            uppercase_columns(after, target)
            ready.add(target)
            evidence[name] = {'legacy_output': str(paths[0].parent.relative_to(ROOT)),
                'landing_sha256': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs},
                'build': 'initial; is_incremental()=false'}
        except (duckdb.Error, ValueError, OSError) as error:
            errors[target] = 'Spark parity materialization failed: '+str(error)
    return ready, errors, evidence
