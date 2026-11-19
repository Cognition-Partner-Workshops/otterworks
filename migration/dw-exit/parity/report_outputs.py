"""Evaluate legacy exports on PostgreSQL and shipped resultset SQL on DuckDB."""
import re
from pathlib import Path

import duckdb
import psycopg
import sqlglot
from sqlglot import exp

from warehouse.run_config import render
from .local_billing import statements
from .semantics import numeric_type

ROOT = Path(__file__).resolve().parents[3]
OUTPUTS = {'M_SUBSCRIPTION_PLANS_OUTPUT', 'M_CURRENCY_TOTALS_OUTPUT', 'GL_TRIAL_BALANCE_OUTPUT'}
SUBJECT_OUTPUTS = {'billing': OUTPUTS, 'users': {'M_TEAM_COUNTS_OUTPUT'}}


def source_queries(subject='billing'):
    queries = {}
    for path in sorted((ROOT/'warehouse/teradata/macros').glob('*.sql')):
        match = re.search(r'REPLACE MACRO SFX_'+subject.upper()+r'\.(M_\w+).*?\bAS\s*\((.*)\);', path.read_text(), re.S | re.I)
        if match:
            queries[match[1]+'_OUTPUT'] = match[2].strip().rstrip(';')
    if subject != 'billing':
        return queries
    text = (ROOT/'warehouse/teradata/scripts/billing/12_invoice_monthly.bteq').read_text()
    match = re.search(r'gl_trial_balance\.psv\s*\n(SELECT.*?);', text, re.S | re.I)
    if not match:
        raise ValueError('Missing legacy trial balance export')
    queries['GL_TRIAL_BALANCE_OUTPUT'] = match[1]
    return queries


def target_queries(subject='billing'):
    text = render((ROOT/'migration/dw-exit'/subject/'20_routines.sql').read_text())
    queries = {}
    for name, body in re.findall(r'CREATE OR REPLACE PROCEDURE\s+\S+\.(M_\w+).*?\$\$(.*?)\$\$;', text, re.S | re.I):
        match = re.search(r'LET res RESULTSET\s*:=\s*\((.*?)\);\s*RETURN TABLE', body, re.S | re.I)
        if not match:
            raise ValueError('Unsupported resultset wrapper: '+name)
        query = sqlglot.parse_one(match[1], read='snowflake')
        for table in query.find_all(exp.Table):
            table.set('catalog', None)
        queries[name+'_OUTPUT'] = query.sql(dialect='duckdb')
    return queries


def postgres_query(query):
    parsed = sqlglot.parse_one(query, read='teradata')
    for node in list(parsed.find_all(exp.Anonymous)):
        if node.name.upper() == 'ZEROIFNULL':
            node.replace(exp.Coalesce(this=node.expressions[0].copy(), expressions=[exp.Literal.number(0)]))
    return parsed.sql(dialect='postgres')


def materialize(before, after, dsn, ready, business_date, subject='billing'):
    errors = {}
    schema = subject.upper()
    with psycopg.connect(dsn) as source:
        for name, query in source_queries(subject).items():
            target = schema+'.'+name
            try:
                with source.cursor() as cursor:
                    cursor.execute(postgres_query(query))
                    rows = cursor.fetchall()
                    columns = []
                    for i, column in enumerate(cursor.description):
                        kind = {20:'BIGINT', 23:'INTEGER', 25:'VARCHAR', 1042:'VARCHAR', 1043:'VARCHAR'}.get(column.type_code)
                        if column.type_code == 1700:
                            kind = numeric_type([row[i] for row in rows], None, None)
                        if not kind:
                            raise ValueError('Unsupported report result type: '+str(column.type_code))
                        columns.append('"'+column.name.upper()+'" '+kind)
                    # Report names are fixed subject contracts; types use the allowlist above and column names are metadata.
                    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                    before.execute('CREATE TABLE SFX_'+schema+'.'+name+' ('+', '.join(columns)+')')
                    if rows:
                        before.executemany('INSERT INTO SFX_'+schema+'.'+name+' VALUES ('+','.join('?' for _ in columns)+')', rows)
            except (psycopg.Error, ValueError) as error:
                source.rollback()
                errors[target] = 'source report failed: '+str(error)
    for name, query in target_queries(subject).items():
        target = schema+'.'+name
        try:
            after.execute('CREATE TABLE '+target+' AS '+query)
            if target not in errors:
                ready.add(target)
        except (ValueError, duckdb.Error) as error:
            errors[target] = 'converted report failed: '+str(error)
    if subject != 'billing':
        return errors
    for statement in statements(ROOT/'migration/dw-exit/billing/35_reports.sql', business_date):
        after.execute(statement.sql(dialect='duckdb'))
    if 'BILLING.GL_TRIAL_BALANCE_OUTPUT' not in errors:
        ready.add('BILLING.GL_TRIAL_BALANCE_OUTPUT')
    return errors
