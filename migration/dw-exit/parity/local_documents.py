"""Local-only documents candidate execution; unresolved semantics remain red."""
from pathlib import Path
import csv
import re

import duckdb
import sqlglot
from sqlglot import exp

from .local_billing import lower_statements, statements
from .connection import validate_date
from .ladder import identifier, local_compare

ROOT = Path(__file__).resolve().parents[3]
CONVERSIONS = ROOT / 'migration/dw-exit/documents'
STAGES = ('00_tables.sql', '10_load.sql', '20_views.sql')


def storage_statements(business_date):
    day = validate_date(business_date)
    text = (CONVERSIONS/'12_storage_monthly.sql').read_text()
    body = text.split('BEGIN\n', 1)[1].split('    res := ', 1)[0]
    return lower_statements(body.replace(':p_day', f"TO_DATE('{day}', 'YYYYMMDD')"))


def execute(after, before, conversion_dir=CONVERSIONS, business_date='20261109'):
    ready, errors = set(), {}
    after.execute('CREATE SCHEMA IF NOT EXISTS DOCUMENTS')
    after.execute('CREATE SCHEMA IF NOT EXISTS COMPAT')
    after.execute('BEGIN')
    try:
        for filename in STAGES:
            for statement in statements(conversion_dir / filename, business_date):
                for node in list(statement.find_all(exp.Collate)):
                    node.replace(exp.Collate(this=node.this.copy(), expression=exp.Var(this='NOCASE')))
                for node in statement.find_all(exp.CollateColumnConstraint):
                    if node.this.name != 'en-ci-rtrim':
                        raise ValueError('Unsupported documents collation')
                    node.set('this', exp.Var(this='NOCASE'))
                after.execute(statement.sql(dialect='duckdb', comments=False))
            if filename == '00_tables.sql':
                names = [r[0] for r in after.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='DOCUMENTS' AND table_name LIKE 'STG_%'").fetchall()]
                for table in names:
                    name = identifier(table)
                    # identifier() validates/quotes the table; row values are bound below.
                    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                    rows = before.execute('SELECT * FROM SFX_DOCUMENTS.'+name).fetchall()
                    if rows:
                        after.executemany('INSERT INTO DOCUMENTS.'+name+' VALUES ('+','.join('?' for _ in rows[0])+')', rows)
        ready = {'DOCUMENTS.'+r[0] for r in after.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='DOCUMENTS'").fetchall()}
        after.execute('COMMIT')
    except (ValueError, duckdb.Error, OSError, sqlglot.errors.SqlglotError) as error:
        after.execute('ROLLBACK')
        ready.clear()
        errors['*'] = type(error).__name__+': '+str(error)
    return ready, errors


def report_query(path, business_date, source=False):
    day = validate_date(business_date)
    text = path.read_text()
    pattern = r'AS\s*\(\s*(SELECT.*?)\);' if source else r'res\s*:=\s*\(\s*(SELECT.*?)\);\s*RETURN TABLE'
    match = re.search(pattern, text, re.S | re.I)
    if not match:
        raise ValueError('Missing storage resultset wrapper')
    query = match[1].strip().rstrip(';')
    query = query.replace('__RUN_DATABASE__.', '')
    first = day[:4]+'-'+day[4:6]+'-01'
    query = query.replace(':p_start', "DATE '"+first+"'")
    query = query.replace(':p_end', "(DATE '"+first+"' + INTERVAL '1 month')")
    if ':' in query:
        raise ValueError('Unbound storage report parameter')
    return sqlglot.parse_one(query, read='teradata' if source else 'snowflake').sql(dialect='duckdb')


def resultset(before, after, business_date='20261109', conversion_dir=CONVERSIONS):
    source = ROOT / 'warehouse/teradata/macros/storage_totals.sql'
    queries = [report_query(source, business_date, source=True),
               report_query(conversion_dir/'35_reports.sql', business_date)]
    before.execute('BEGIN')
    after.execute('BEGIN')
    try:
        # Queries are parsed repository SQL with validate_date()-checked report parameters.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        before.execute('CREATE OR REPLACE TABLE SFX_DOCUMENTS.M_STORAGE_TOTALS_OUTPUT AS '+queries[0])
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        after.execute('CREATE OR REPLACE TABLE DOCUMENTS.M_STORAGE_TOTALS_OUTPUT AS '+queries[1])
    except (ValueError, duckdb.Error):
        before.execute('ROLLBACK')
        after.execute('ROLLBACK')
        raise
    before.execute('COMMIT')
    after.execute('COMMIT')


def load_landing(connection, landing, business_date='20261109', conversion_dir=CONVERSIONS):
    day = validate_date(business_date)
    text = (conversion_dir/'05_tpt.sql').read_text()
    copies = re.findall(r'COPY INTO __RUN_DATABASE__\.DOCUMENTS\.(\w+)\s+FROM \(SELECT (.*?)\s+FROM @[^\n]+/documents/(\w+)/\)', text, re.S)
    if len(copies) != 9:
        raise ValueError('Expected nine documents TPT copies')
    for table, projection, folder in copies:
        connection.execute('BEGIN')
        try:
            target = 'DOCUMENTS.'+identifier(table)
            # Validated target; RAW_INPUT column names are generated indices, not PSV content.
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            columns = connection.execute('DESCRIBE '+target).fetchall()
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            connection.execute('CREATE OR REPLACE TEMP TABLE RAW_INPUT ('+
                               ','.join('C'+str(i+1)+' VARCHAR' for i in range(len(columns)))+')')
            with (landing/'documents'/folder/(day+'.psv')).open(newline='') as handle:
                rows = list(csv.reader(handle, delimiter='|'))
            if any(len(row) != len(columns) for row in rows):
                raise ValueError('TPT input field count differs from target: '+table)
            if rows:
                connection.executemany('INSERT INTO RAW_INPUT VALUES ('+','.join('?' for _ in columns)+')', rows)
            projection = re.sub(r'\$(\d+)', r'C\1', projection)
            query = sqlglot.parse_one('SELECT '+projection+' FROM RAW_INPUT', read='snowflake')
            # Projection is shipped COPY SQL; PSV values were bound into RAW_INPUT.
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            connection.execute('DELETE FROM '+target)
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            connection.execute('INSERT INTO '+target+' '+query.sql(dialect='duckdb'))
            connection.execute('COMMIT')
        except (ValueError, duckdb.Error, OSError, sqlglot.errors.SqlglotError):
            connection.execute('ROLLBACK')
            raise


def compare(before, after, contract):
    results = {}
    for item in contract:
        name = item['name']
        result = local_compare(before, after, 'SFX_DOCUMENTS.'+name, 'DOCUMENTS.'+name, sample_size=10000)
        if result['keyed_row_hash']['keys'] != item['keys']:
            raise ValueError('Local ladder key differs from contract: '+name)
        results[name] = result
    return results


def render_pc(path):
    text = re.sub(r'\{\{\s*config\(.*?\)\s*\}\}', '', path.read_text(), flags=re.S)
    text = re.sub(r"\{\{\s*source\('pc_content_src',\s*'(\w+)'\)\s*\}\}", r'PC_SRC.\1', text)
    text = re.sub(r"\{\{\s*source\('documents_user_lookups',\s*'(\w+)'\)\s*\}\}", r'USERS.\1', text)
    text = re.sub(r"\{\{\s*source\('documents_converted',\s*'(\w+)'\)\s*\}\}", r'DOCUMENTS.\1', text)
    text = re.sub(r"\{\{\s*ref\('pc_content__(\w+)'\)\s*\}\}", lambda m: 'PC_CONTENT.'+m[1].upper(), text)
    if '{{' in text or '{%' in text:
        raise ValueError('Unsupported documents dbt template')
    return sqlglot.parse_one(text, read='snowflake').sql(dialect='duckdb')


def merge_pc(connection, table, query, key):
    target = 'PC_CONTENT.'+identifier(table)
    key = identifier(key)
    connection.execute('BEGIN')
    try:
        # Query is rendered repository dbt SQL; target and key pass identifier().
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        connection.execute('CREATE OR REPLACE TEMP TABLE PC_CANDIDATE AS '+query)
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        if connection.execute('SELECT COUNT(*) FROM (SELECT '+key+' FROM PC_CANDIDATE GROUP BY '+key+' HAVING COUNT(*)>1 OR '+key+' IS NULL)').fetchone()[0]:
            raise ValueError('Ambiguous/null PowerCenter candidate key')
        if table == 'STG_DOCUMENT':
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            connection.execute('DELETE FROM '+target)
        else:
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            connection.execute('DELETE FROM '+target+' WHERE '+key+' IN (SELECT '+key+' FROM PC_CANDIDATE)')
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        connection.execute('INSERT INTO '+target+' SELECT * FROM PC_CANDIDATE')
        connection.execute('COMMIT')
    except (ValueError, duckdb.Error):
        connection.execute('ROLLBACK')
        raise
