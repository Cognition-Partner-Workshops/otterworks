"""Actual users Spark lake outputs versus the shipped dbt/Snowpark conversions."""
import ast
import hashlib
from pathlib import Path
import re

import duckdb

from . import spark_billing
from .ladder import identifier

ROOT = Path(__file__).resolve().parents[3]


def sql_template(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return ''.join(part.value if isinstance(part, ast.Constant) else '__FUNCTION__' for part in node.values)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'replace':
        return sql_template(node.func.value)
    raise ValueError('Unsupported shipped Snowpark SQL template')


def snowpark_query(connection, name, schema='SPARK_INPUT'):
    if name not in ('users_risk_score','users_login_useragent_parse','user_pref_json_flatten','team_graph_components'):
        raise ValueError('Unsupported shipped users Snowpark job')
    schema = identifier(schema)
    path = ROOT/'warehouse/snowpark'/(name+'.py')
    tree = ast.parse(path.read_text())
    run = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run'), None)
    if run is None:
        raise ValueError('Missing shipped Snowpark run function')
    sql = [sql_template(n.args[0]) for n in ast.walk(run) if isinstance(n, ast.Call)
           and isinstance(n.func, ast.Attribute) and n.func.attr == 'sql']
    bodies = [re.search(r'\$\$(.*?)\$\$', text, re.S)[1] for text in sql if '$$' in text]
    if len(bodies) != 1:
        raise ValueError('Expected one shipped Python UDF body')
    scope = {}
    # Only allowlisted repository-shipped Snowpark code/SQL is evaluated; landing values are UDF arguments, never code.
    # nosemgrep: python.lang.security.audit.exec-detected.exec-detected
    exec(compile(bodies[0], str(path), 'exec'), scope)
    definition = next(text for text in sql if '$$' in text)
    handler = re.search(r'handler\s*=\s*\x27?(\w+)', definition, re.I)[1]
    function = scope[handler]
    if isinstance(function, type):
        parameters = re.search(r'function.*?\((.*?)\)\s*returns', definition, re.S|re.I)[1]
        parameters = [identifier(p.strip().split()[0]) for p in parameters.split(',')]
        outputs = re.search(r'returns table\((.*?)\)', definition, re.S|re.I)[1]
        outputs = [p.strip().split() for p in outputs.split(',')]
        if any(kind.lower() != 'number' for _,kind in outputs):
            raise ValueError('Unsupported shipped UDTF output type')
        projection = next(text for text in sql if '$$' not in text)
        columns = re.findall(r'labels\.(\w+)::number\(38,0\) as (\w+)', projection, re.I)
        if columns != [(column,column) for column,_ in outputs]:
            raise ValueError('Unsupported shipped UDTF projection')
        table = re.search(r'"SPARK_RAW_USERS"\."(\w+)"', projection)[1]
        instance = function()
        # Only allowlisted repository-shipped Snowpark code/SQL is evaluated; landing values are UDF arguments, never code.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        for row in connection.execute('SELECT '+','.join(parameters)+' FROM '+schema+'.'+table).fetchall():
            instance.process(*row)
        # Only allowlisted repository-shipped Snowpark code/SQL is evaluated; landing values are UDF arguments, never code.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        connection.execute('CREATE OR REPLACE TABLE GRAPH_RESULT ('+','.join(identifier(column)+' BIGINT' for column,_ in outputs)+')')
        rows = list(instance.end_partition())
        if rows:
            connection.executemany('INSERT INTO GRAPH_RESULT VALUES ('+','.join('?' for _ in outputs)+')',rows)
        return 'SELECT * FROM GRAPH_RESULT'
    tables = [n.args[0].elts[-1].value for n in ast.walk(run) if isinstance(n,ast.Call)
              and isinstance(n.func,ast.Attribute) and n.func.attr == 'table']
    selects = [n for n in ast.walk(run) if isinstance(n,ast.Call)
               and isinstance(n.func,ast.Attribute) and n.func.attr == 'select']
    if len(tables) != 1 or len(selects) != 1:
        raise ValueError('Expected one shipped Snowpark input and projection')
    # Only allowlisted repository-shipped Snowpark code/SQL is evaluated; landing values are UDF arguments, never code.
    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
    kinds = {c[0]:c[1] for c in connection.execute('DESCRIBE '+schema+'.'+identifier(tables[0])).fetchall()}
    registered = False

    def udf(call, variables=None):
        nonlocal registered
        if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Name) or call.func.id != 'call_udf':
            raise ValueError('Unsupported shipped Snowpark function call')
        values,types = [],[]
        for arg in call.args[1:]:
            value = arg.args[0]
            value = variables[value.id] if isinstance(value,ast.Name) and variables else value.value
            if arg.func.id == 'col':
                values.append('"'+value+'"')
                types.append(kinds[value])
            elif arg.func.id == 'lit':
                values.append("'"+value.replace("'","''")+"'")
                types.append('VARCHAR')
            else:
                raise ValueError('Unsupported shipped UDF argument')
        if not registered:
            result = re.search(r'returns\s+(\w+)',definition,re.I)[1].lower()
            connection.create_function(name,function,types,{'varchar':'VARCHAR','float':'DOUBLE'}[result],null_handling='special')
            registered = True
        return name+'('+','.join(values)+')'

    columns = []
    for node in selects[0].args:
        if isinstance(node,ast.Constant) and isinstance(node.value,str):
            columns.append('"'+node.value+'"')
        elif isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr == 'alias':
            columns.append(udf(node.func.value)+' AS "'+node.args[0].value+'"')
        else:
            raise ValueError('Unsupported shipped Snowpark projection')
    for loop in (n for n in ast.walk(run) if isinstance(n,ast.For)):
        calls = [n for n in ast.walk(loop) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr == 'with_column']
        if len(calls) != 1 or not isinstance(loop.iter,ast.Tuple):
            raise ValueError('Unsupported shipped Snowpark column loop')
        for key in ast.literal_eval(loop.iter):
            alias = calls[0].args[0]
            if not isinstance(alias,ast.Call) or alias.func.attr != 'upper':
                raise ValueError('Unsupported shipped Snowpark column alias')
            columns.append(udf(calls[0].args[1],{loop.target.id:key})+' AS "'+key.upper()+'"')
    return 'SELECT '+','.join(columns)+' FROM '+schema+'.'+tables[0]


def materialize(before, after, objects, namespace):
    runtime = ROOT/'etl/spark/.data'/namespace
    landing = runtime/'landing/users'
    ready, errors, evidence = set(), {}, {}
    before.execute('CREATE SCHEMA IF NOT EXISTS SFX_SPARK')
    after.execute('CREATE SCHEMA IF NOT EXISTS SPARK; CREATE SCHEMA IF NOT EXISTS USERS_SPARK_INPUT')
    definitions = spark_billing.schemas()
    loaded = False
    for obj in objects:
        if obj['system'] != 'spark' or obj['subject_area'] != 'users':
            continue
        name = obj['name']
        target = 'SPARK.'+name.upper()
        try:
            paths = sorted((runtime/'lake/users'/name).glob('*.parquet'))
            inputs = sorted(landing.glob('*/*.psv'))
            if not paths or not inputs:
                raise ValueError('Missing Spark parquet output or landing inputs')
            if min(p.stat().st_mtime for p in paths) < max(p.stat().st_mtime for p in inputs):
                raise ValueError('Spark output predates landing inputs; rerun legacy job')
            if not loaded:
                for directory in sorted(landing.iterdir()):
                    if directory.is_dir():
                        columns = {column:kind.replace('TEXT','VARCHAR') for column,kind in definitions[directory.name]}
                        after.read_csv(str(directory/'*.psv'),delimiter='|',header=True,columns=columns,
                                       na_values='',quotechar='"',escapechar='"').create('USERS_SPARK_INPUT.'+directory.name)
                loaded = True
            model = ROOT/'warehouse/dbt/models/spark'/name/(name+'.sql')
            if model.is_file():
                query = spark_billing.render_model(model.read_text().replace("'spark_users'","'spark_billing'"))
                query = query.replace('SPARK_INPUT.','USERS_SPARK_INPUT.')
            else:
                query = snowpark_query(after,name,'USERS_SPARK_INPUT')
            before.read_parquet([str(p) for p in paths]).create('SFX_SPARK.'+name.upper())
            # Only allowlisted repository-shipped Snowpark code/SQL is evaluated; landing values are UDF arguments, never code.
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            after.execute('CREATE OR REPLACE TABLE '+target+' AS '+query)
            spark_billing.uppercase_columns(before,'SFX_SPARK.'+name.upper())
            spark_billing.uppercase_columns(after,target)
            ready.add(target)
            evidence[name] = dict(legacy_output=str(paths[0].parent.relative_to(ROOT)),
                landing_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
                build='initial; shipped dbt SELECT or extracted shipped Snowpark Python body/projection')
        except (duckdb.Error,ValueError,OSError,SyntaxError) as error:
            errors[target] = 'Spark parity materialization failed: '+str(error)
    return ready,errors,evidence
