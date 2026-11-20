"""Evaluate legacy exports and translate shared audit/users resultsets locally."""
import re
import datetime
from pathlib import Path

import duckdb
import psycopg
import sqlglot
from sqlglot import exp

from warehouse.run_config import render
from .semantics import numeric_type
from .identifiers import quote
from .local_billing import statements
from warehouse.teradata.bteq.runner import Runner

ROOT = Path(__file__).resolve().parents[3]
OUTPUTS = {'M_SUBSCRIPTION_PLANS_OUTPUT', 'M_CURRENCY_TOTALS_OUTPUT', 'GL_TRIAL_BALANCE_OUTPUT',
           'INVOICE_PERIODS_OUTPUT', 'PERIOD_CLOSE_OUTPUT'}
SUBJECT_OUTPUTS = {'users': {'M_TEAM_COUNTS_OUTPUT'}, 'billing': OUTPUTS}


def source_queries(subject='billing'):
    queries = {}
    for path in sorted((ROOT/'warehouse/teradata/macros').glob('*.sql')):
        match = re.search(r'REPLACE MACRO SFX_'+subject.upper()+r'\.(M_\w+).*?\bAS\s*\((.*)\);', path.read_text(), re.S | re.I)
        if match:
            queries[match[1]+'_OUTPUT'] = match[2].strip().rstrip(';')
    if subject == 'billing':
        text = (ROOT/'warehouse/teradata/scripts/billing/12_invoice_monthly.bteq').read_text()
        match = re.search(r'gl_trial_balance\.psv\s*\n(SELECT.*?);', text, re.S | re.I)
        if not match:
            raise ValueError('Missing legacy trial balance export')
        queries['GL_TRIAL_BALANCE_OUTPUT'] = match[1]
        text = (ROOT/'warehouse/teradata/scripts/billing/13_period_close.bteq').read_text()
        for filename in ('invoice_periods', 'period_close'):
            match = re.search(filename+r'\.psv\s*\n(SELECT.*?);', text, re.S | re.I)
            if not match:
                raise ValueError('Missing legacy export: '+filename)
            queries[filename.upper()+'_OUTPUT'] = match[1]
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
    if subject not in SUBJECT_OUTPUTS:
        raise ValueError('Unsupported report subject')
    schema = subject.upper()
    day = datetime.datetime.strptime(business_date, '%Y%m%d').date()
    end = day.replace(day=1) - datetime.timedelta(days=1)
    variables = dict(BUSINESS_DATE=business_date,
                     PERIOD_START_INT=str(int(end.replace(day=1).strftime('%Y%m%d'))-19000000),
                     PERIOD_END_INT=str(int(end.strftime('%Y%m%d'))-19000000))
    with psycopg.connect(dsn) as source:
        translator = Runner(connection=source)
        for name, query in source_queries(subject).items():
            target = schema+'.'+name
            try:
                with source.cursor() as cursor:
                    if name in ('INVOICE_PERIODS_OUTPUT', 'PERIOD_CLOSE_OUTPUT'):
                        query = re.sub(r'\$\{(\w+)\}', lambda m: variables[m[1]], query)
                        query, _ = translator.translate(query)
                    else:
                        query = postgres_query(query)
                    cursor.execute(query)
                    rows = cursor.fetchall()
                    columns = []
                    for i, column in enumerate(cursor.description):
                        kind = {20:'BIGINT', 23:'INTEGER', 25:'VARCHAR', 1042:'VARCHAR', 1043:'VARCHAR', 1082:'DATE'}.get(column.type_code)
                        if column.type_code == 1700:
                            kind = numeric_type([row[i] for row in rows], None, None)
                        if not kind:
                            raise ValueError('Unsupported report result type: '+str(column.type_code))
                        columns.append(quote(column.name.upper())+' '+kind)
                    # Subject is allowlisted; names come from repo macros, columns quoted and types mapped.
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
            # Query and resultset name come from checked-in SQL translated by sqlglot.
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            after.execute('CREATE TABLE '+target+' AS '+query)
            if target not in errors:
                ready.add(target)
        except (ValueError, duckdb.Error) as error:
            errors[target] = 'converted report failed: '+str(error)
    if subject == 'billing':
        for statement in statements(ROOT/'migration/dw-exit/billing/35_reports.sql', business_date):
            after.execute(statement.sql(dialect='duckdb'))
        for name in OUTPUTS - set(target_queries(subject)):
            if 'BILLING.'+name not in errors:
                ready.add('BILLING.'+name)
    return errors
