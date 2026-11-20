"""Run the legacy billing workflow on a local clone and evaluate shipped dbt SQL."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import duckdb
from jinja2 import Environment, StrictUndefined
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
import sqlglot
from sqlglot import exp

from warehouse.run_config import RunConfig, render
from .ladder import local_compare
from .identifiers import quote, relation

ROOT = Path(__file__).resolve().parents[3]
TABLES = ('STG_CUSTOMER_ACCOUNT', 'CUSTOMER_ACCOUNT', 'STG_INVOICE_HDR',
          'INVOICE_HDR', 'INVOICE_LINE', 'GL_JOURNAL_LINE', 'PAYMENT')


class Relation(str):
    database = 'LOCAL'

    @property
    def schema(self):
        return self.split('.')[0]


def model_query(path, config, business_date):
    def capture(**kwargs):
        config.update(kwargs)
        return ''
    # Repository SQL templates, not HTML; escaping would corrupt SQL operators.
    # nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2, python.jinja2.security.audit.missing-autoescape-disabled.missing-autoescape-disabled, python.jinja2.security.audit.autoescape-disabled-false.incorrect-autoescape-disabled
    text = Environment(undefined=StrictUndefined, autoescape=False).from_string(render(path.read_text())).render(
        config=capture, ref=lambda name: 'PC_BILLING.'+name.split('__')[1].upper(),
        var=lambda name, default: business_date if name == 'load_date' else default,
        is_incremental=lambda: False)
    text = re.sub(r'@\w+\.PC_SRC\.LANDING_STAGE/(\w+)/\s*\(file_format\s*=>.*?\)',
                  r'PC_FILES.\1', text, flags=re.S)
    text = re.sub(r'\$(\d+)', r'C\1', text)
    query = sqlglot.parse_one(text, read='snowflake')
    for table in query.find_all(exp.Table):
        table.set('catalog', None)
    for node in list(query.find_all(exp.StrToDate)):
        if isinstance(node.args.get('format'), exp.Literal):
            node.set('format', exp.Literal.string(node.args['format'].this.replace('YYYY-MM-DD', '%Y-%m-%d')))
    return query.sql(dialect='duckdb')


def materialize(before, after, dsn, namespace, snapshot, business_date='20261109'):
    settings = conninfo_to_dict(dsn)
    if settings.get('host') not in ('127.0.0.1', 'localhost'):
        raise ValueError('PowerCenter board clone is local PostgreSQL only')
    database = RunConfig.from_env().token+'_pc_board'
    parent = ROOT/'migration/dw-exit/.runs'/namespace/'pc'
    parent.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix='proof-', dir=parent))
    admin = dict(settings, dbname='postgres')
    source_name = settings.get('dbname', 'teradata')
    ready, errors, evidence = set(), {}, {}
    names = {'SFX_BILLING.'+table for table in TABLES} | {'SFX_BILLING.GL_ACCOUNT'}
    with psycopg.connect(**admin, autocommit=True) as control:
        # Fixed TABLES/schema names, quoted metadata columns or psycopg Identifier; row values are bound.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        control.execute(sql.SQL('CREATE DATABASE {} TEMPLATE {}').format(sql.Identifier(database), sql.Identifier(source_name)))
    initial = legacy = None
    try:
        clone = psycopg.conninfo.make_conninfo(**dict(settings, dbname=database))
        initial, _, initial_errors = snapshot(clone, names)
        if initial_errors:
            raise ValueError(str(initial_errors))
        env = dict(os.environ, TD_DB=database, TD_HOST=settings['host'],
                   TD_PORT=settings['port'], TD_USER=settings.get('user', 'postgres'),
                   LANDING_DIR=str(ROOT/'warehouse/landing'), PMROOTDIR=str(output), MAPPINGS='all')
        command = [sys.executable, '-m', 'runner', 'startworkflow', '-f', 'SFX_BILLING', 'wf_SFX_BILLING_DAILY']
        with (output/'runner.log').open('w') as log:
            subprocess.run(command, cwd=ROOT/'etl/informatica', env=env, stdout=log,
                           stderr=subprocess.STDOUT, check=True)
        legacy, _, legacy_errors = snapshot(clone, names)
        if legacy_errors:
            raise ValueError(str(legacy_errors))
        for connection, schema in ((before, 'SFX_PC_BILLING'), (after, 'PC_BILLING')):
            # Fixed TABLES/schema names, quoted metadata columns or psycopg Identifier; row values are bound.
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            connection.execute('CREATE SCHEMA IF NOT EXISTS '+quote(schema))
        # Fixed TABLES/schema names, quoted metadata columns or psycopg Identifier; row values are bound.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        after.execute('CREATE SCHEMA PC_FILES')
        # Fixed TABLES/schema names, quoted metadata columns or psycopg Identifier; row values are bound.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        after.execute('CREATE SCHEMA PC_SRC')
        for table in ('CUSTOMER_ACCOUNT', 'INVOICE_HDR', 'INVOICE_LINE', 'PAYMENT'):
            path = ROOT/'warehouse/landing/billing'/table/(business_date+'.psv')
            count = len(path.read_text().splitlines()[0].split('|'))
            columns = {f'C{i}': 'VARCHAR' for i in range(1, count+1)}
            after.read_csv(str(path), delimiter='|', header=False, columns=columns, na_values='').create('PC_FILES.RAW_'+table)
            # Fixed TABLES/schema names, quoted metadata columns or psycopg Identifier; row values are bound.
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query, python.lang.security.audit.formatted-sql-query.formatted-sql-query
            after.execute(f'CREATE TABLE PC_FILES.{table} AS SELECT *, row_number() over () METADATA$FILE_ROW_NUMBER FROM PC_FILES.RAW_{table}')
        # Fixed TABLES/schema names, quoted metadata columns or psycopg Identifier; row values are bound.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        definitions = initial.execute('DESCRIBE SFX_BILLING.GL_ACCOUNT').fetchall()
        # Fixed TABLES/schema names, quoted metadata columns or psycopg Identifier; row values are bound.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        after.execute('CREATE TABLE PC_SRC.GL_ACCOUNT ('+', '.join(quote(c[0])+' '+c[1] for c in definitions)+')')
        # Fixed TABLES/schema names, quoted metadata columns or psycopg Identifier; row values are bound.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        rows = initial.execute('SELECT * FROM SFX_BILLING.GL_ACCOUNT').fetchall()
        if rows:
            after.executemany('INSERT INTO PC_SRC.GL_ACCOUNT VALUES ('+','.join('?' for _ in definitions)+')', rows)
        for table in TABLES:
            target = 'PC_BILLING.'+table
            try:
                model = ROOT/'warehouse/dbt/models/pc/billing'/('pc_billing__'+table.lower()+'.sql')
                config = {}
                query = model_query(model, config, business_date)
                # Fixed TABLES/schema names, quoted metadata columns or psycopg Identifier; row values are bound.
                # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                after.execute('CREATE TABLE PC_BILLING.MODEL_'+table+' AS '+query)
                # Fixed TABLES/schema names, quoted metadata columns or psycopg Identifier; row values are bound.
                # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                definitions = legacy.execute('DESCRIBE SFX_BILLING.'+table).fetchall()
                columns = [c[0] for c in definitions]
                # Fixed TABLES/schema names, quoted metadata columns or psycopg Identifier; row values are bound.
                # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                model_columns = [c[0].upper() for c in after.execute('DESCRIBE PC_BILLING.MODEL_'+table).fetchall()]
                if model_columns != columns:
                    raise ValueError(f'Model columns {model_columns} differ from runner target {columns}')
                for connection, schema, source in ((before, 'SFX_PC_BILLING', legacy), (after, 'PC_BILLING', initial)):
                    # Fixed TABLES/schema names, quoted metadata columns or psycopg Identifier; row values are bound.
                    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query, python.lang.security.audit.formatted-sql-query.formatted-sql-query
                    connection.execute(f'CREATE TABLE {schema}.{table} ('+', '.join(quote(c[0])+' '+c[1] for c in definitions)+')')
                    # Fixed TABLES/schema names, quoted metadata columns or psycopg Identifier; row values are bound.
                    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                    rows = source.execute('SELECT * FROM SFX_BILLING.'+table).fetchall()
                    if rows:
                        connection.executemany(f'INSERT INTO {schema}.{table} VALUES ('+','.join('?' for _ in columns)+')', rows)
                if config.get('materialized') == 'table':
                    # Fixed TABLES/schema names, quoted metadata columns or psycopg Identifier; row values are bound.
                    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                    after.execute('DELETE FROM '+target)
                else:
                    key = quote(config['unique_key'])
                    for hook in ([config['pre_hook']] if isinstance(config.get('pre_hook'), str) else config.get('pre_hook', [])):
                        if hook.upper().startswith('CREATE FILE FORMAT '):
                            continue
                        # Checked-in SQL hook, never browser HTML.
                        # nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2, python.jinja2.security.audit.missing-autoescape-disabled.missing-autoescape-disabled, python.jinja2.security.audit.autoescape-disabled-false.incorrect-autoescape-disabled
                        text = Environment(undefined=StrictUndefined, autoescape=False).from_string(hook).render(
                            this=Relation(target), ref=lambda name: 'PC_BILLING.'+name.split('__')[1].upper(),
                            is_incremental=lambda: True)
                        if text.strip():
                            statement = sqlglot.parse_one(text, read='snowflake')
                            for table_node in statement.find_all(exp.Table):
                                table_node.set('catalog', None)
                            if isinstance(statement, exp.Create):
                                statement.set('properties', None)
                            after.execute(statement.sql(dialect='duckdb'))
                    # Fixed TABLES/schema names, quoted metadata columns or psycopg Identifier; row values are bound.
                    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query, python.lang.security.audit.formatted-sql-query.formatted-sql-query
                    after.execute(f'DELETE FROM {target} WHERE {key} IN (SELECT {key} FROM PC_BILLING.MODEL_{table})')
                # Fixed TABLES/schema names, quoted metadata columns or psycopg Identifier; row values are bound.
                # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query, python.lang.security.audit.formatted-sql-query.formatted-sql-query
                after.execute(f'INSERT INTO {target} SELECT * FROM PC_BILLING.MODEL_{table}')
                ready.add(target)
                evidence[table] = {'model': str(model.relative_to(ROOT)), 'legacy_log': str((output/'runner.log').relative_to(ROOT)),
                                   'result': local_compare(before, after, 'SFX_PC_BILLING.'+table, target)}
            except (duckdb.Error, ValueError, OSError) as error:
                errors[target] = 'PowerCenter dbt parity: '+str(error).splitlines()[0]
    except (psycopg.Error, ValueError, subprocess.CalledProcessError) as error:
        errors.update({'PC_BILLING.'+table: 'PowerCenter proof failed: '+str(error) for table in TABLES})
    finally:
        if initial is not None:
            initial.close()
        if legacy is not None:
            legacy.close()
        with psycopg.connect(**admin, autocommit=True) as control:
            # Fixed TABLES/schema names, quoted metadata columns or psycopg Identifier; row values are bound.
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            control.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(database)))
    return ready, errors, evidence
