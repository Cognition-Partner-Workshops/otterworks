"""Run the shipped audit conversion, keeping batch and PowerCenter evidence separate."""
import hashlib
from pathlib import Path
import re

import duckdb
import psycopg
import sqlglot
from sqlglot import exp

from warehouse.run_config import render
from .connection import validate_date
from .report_outputs import postgres_query
from .ladder import identifier

ROOT = Path(__file__).resolve().parents[3]
SQL = ROOT / 'migration/dw-exit/audit'
PC_TABLES = ('STG_AUDIT_EVENT', 'AUDIT_EVENT', 'AUDIT_DAILY_SUMMARY', 'SECURITY_ALERT')
STAGES = ('10_load.sql', '35_reports.sql', '30_views.sql', '40_reconciliation.sql', '45_finish.sql')


def portable(text, business_date):
    business_date = validate_date(business_date)
    text = render(text).replace('${BUSINESS_DATE}', business_date)
    text = re.sub(r'\bCOLLATE\s+\x27en-ci-rtrim\x27', '', text, flags=re.I)
    text = re.sub(r'\w+\.AUDIT\.SUMMARY_SEQ\.NEXTVAL', "NEXTVAL('AUDIT.SUMMARY_SEQ')", text, flags=re.I)
    for statement in sqlglot.parse(text, read='snowflake'):
        if statement is None:
            continue
        if not isinstance(statement, (exp.Create, exp.Insert, exp.Delete, exp.Update, exp.Merge, exp.Select)):
            raise ValueError('Unsupported audit statement: ' + type(statement).__name__)
        for table in statement.find_all(exp.Table):
            table.set('catalog', None)
        for node in reversed(list(statement.walk())):
            if isinstance(node, exp.Anonymous) and node.name.upper() == 'TO_DATE':
                value, fmt = node.expressions
                if not isinstance(fmt, exp.Literal) or fmt.this != 'YYYYMMDD':
                    raise ValueError('Unsupported audit date format')
                node.replace(exp.StrToDate(this=value.copy(), format=exp.Literal.string('%Y%m%d')))
            elif isinstance(node, exp.ToChar):
                if node.args.get('format'):
                    raise ValueError('Unsupported audit TO_CHAR format')
                node.replace(exp.Cast(this=node.this.copy(), to=exp.DataType.build('VARCHAR')))
            elif isinstance(node, exp.TimeToStr):
                raise ValueError('Unsupported audit TO_CHAR format')
        if isinstance(statement, exp.Create):
            statement.set('properties', None)
        yield statement.sql(dialect='duckdb')


def procedures():
    result = {}
    for filename in ('20_routines.sql', '50_powercenter.sql', '52_sessions.sql', '55_workflow.sql'):
        for name, body in re.findall(r'CREATE OR REPLACE PROCEDURE\s+\S+\.(\w+)\([^)]*\).*?\$\$(.*?)\$\$;',
                                     (SQL / filename).read_text(), re.S | re.I):
            result[name.upper()] = body
    return result


def execute(connection, text, business_date, stack=()):
    """Lower only the small shipped Scripting grammar; unknown constructs fail closed."""
    validate_date(business_date)
    calls = procedures()
    for fragment in text.split(';'):
        fragment = fragment.strip()
        if not fragment:
            continue
        call = re.fullmatch(r'CALL\s+\S+\.(\w+)\((.*?)\)', fragment, re.S | re.I)
        if call:
            name = call[1].upper()
            if name in stack or name not in calls:
                raise ValueError('Unknown or recursive audit call: ' + name)
            args = call[2].strip()
            if args not in ('', "'${BUSINESS_DATE}'", "'" + business_date + "'"):
                raise ValueError('Unsupported audit call arguments')
            body = calls[name].split('BEGIN', 1)[1]
            resultset = re.fullmatch(r'\s*LET res RESULTSET\s*:=\s*\((.*?)\);\s*RETURN TABLE\(res\);\s*END;?\s*', body, re.S | re.I)
            if resultset:
                query = resultset[1].replace(':p_day', "'" + business_date + "'")
                execute(connection, query, business_date, stack + (name,))
                continue
            body = re.sub(r'run_day\s*:=\s*TO_DATE\(p_day,\s*\x27YYYYMMDD\x27\);', '', body, flags=re.I)
            body = re.sub(r'n\s*:=\s*SQLROWCOUNT;', '', body, flags=re.I)
            body = re.sub(r'RETURN\s+(?:n|\x27loaded\x27);\s*END;?\s*$', '', body, flags=re.I)
            body = body.replace(':run_day', "TO_DATE('" + business_date + "', 'YYYYMMDD')")
            execute(connection, body, business_date, stack + (name,))
        else:
            for query in portable(fragment, business_date):
                connection.execute(query)


def landing(connection, business_date, landing_dir):
    text = (SQL / '05_landing.sql').read_text()
    evidence = {}
    for table, feed in re.findall(r'COPY INTO __RUN_DATABASE__\.AUDIT\.(STG_\w+)\s+FROM @__RUN_DATABASE__\.AUDIT\.LANDING/audit/(\w+)/', text):
        path = landing_dir / 'audit' / feed / (validate_date(business_date) + '.psv')
        evidence[table] = {'file': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                           'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        if path.stat().st_size:
            # Internal manifest relations and shipped audit SQL only; column types are DuckDB metadata and landing paths are bound.
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            connection.execute('INSERT INTO AUDIT.' + table +
                               " SELECT * FROM read_csv(?, header=false, delim='|', all_varchar=true, nullstr='')", [str(path)])
    if len(evidence) != 9:
        raise ValueError('Expected nine non-retire audit COPY statements')
    return evidence


def copy_relation(before, after, source, target):
    source = '.'.join(identifier(part) for part in source.split('.'))
    target = '.'.join(identifier(part) for part in target.split('.'))
    # Internal manifest relations and shipped audit SQL only; column types are DuckDB metadata and landing paths are bound.
    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
    definitions = before.execute('DESCRIBE ' + source).fetchall()
    # Internal manifest relations and shipped audit SQL only; column types are DuckDB metadata and landing paths are bound.
    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
    after.execute('CREATE TABLE ' + target + ' (' + ', '.join(identifier(c[0]) + ' ' + c[1] for c in definitions) + ')')
    # Internal manifest relations and shipped audit SQL only; column types are DuckDB metadata and landing paths are bound.
    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
    rows = before.execute('SELECT * FROM ' + source).fetchall()
    if rows:
        after.executemany('INSERT INTO ' + target + ' VALUES (' + ','.join('?' for _ in definitions) + ')', rows)


def report(before, after, dsn, business_date, ready):
    source = (ROOT / 'warehouse/teradata/macros/recon_totals.sql').read_text()
    query = re.search(r'\bAS\s*\((.*)\);', source, re.S | re.I)[1].strip().rstrip(';')
    query = query.replace(':p_day', "'" + validate_date(business_date) + "'")
    with psycopg.connect(dsn) as connection:
        rows = connection.execute(postgres_query(query)).fetchall()
    name = 'M_RECON_TOTALS_OUTPUT'
    # Internal manifest relations and shipped audit SQL only; column types are DuckDB metadata and landing paths are bound.
    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
    before.execute('CREATE TABLE SFX_AUDIT.' + name + ' (RECON_ID BIGINT, SOURCE_COUNT BIGINT, TARGET_COUNT BIGINT, DIFFERENCE_COUNT BIGINT)')
    if rows:
        before.executemany('INSERT INTO SFX_AUDIT.' + name + ' VALUES (?,?,?,?)', rows)
    body = procedures()['M_RECON_TOTALS']
    query = re.search(r'LET res RESULTSET\s*:=\s*\((.*?)\);', body, re.S | re.I)[1]
    query = query.replace(':p_day', "'" + business_date + "'")
    # Internal manifest relations and shipped audit SQL only; column types are DuckDB metadata and landing paths are bound.
    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
    after.execute('CREATE TABLE AUDIT.' + name + ' AS ' + next(portable(query, business_date)))
    ready.add('AUDIT.' + name)


def materialize(before, after, source_ready, dsn, ready, business_date='20261109', landing_dir=None):
    errors, evidence = {}, {}
    try:
        after.execute('CREATE SCHEMA IF NOT EXISTS AUDIT')
        execute(after, (SQL / '00_tables.sql').read_text(), business_date)
        evidence['landing'] = landing(after, business_date, landing_dir or ROOT / 'warehouse/landing')
        evidence['external_inputs'] = []
        for schema in ('USERS', 'DOCUMENTS'):
            # Internal manifest relations and shipped audit SQL only; column types are DuckDB metadata and landing paths are bound.
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            after.execute('CREATE SCHEMA IF NOT EXISTS ' + schema)
            for source in sorted(source_ready):
                if source.startswith('SFX_' + schema + '.'):
                    target = source.removeprefix('SFX_')
                    if not after.execute('SELECT COUNT(*) FROM information_schema.tables WHERE upper(table_schema)=? AND upper(table_name)=?', target.split('.')).fetchone()[0]:
                        copy_relation(before, after, source, target)
                    evidence['external_inputs'].append(source)
        evidence['billing_inputs'] = 'existing converted BILLING relations; not copied from source'
        for filename in STAGES:
            execute(after, (SQL / filename).read_text(), business_date)
        for source in source_ready:
            if source.startswith('SFX_AUDIT.') and 'ARCHIVE' not in source:
                ready.add(source.removeprefix('SFX_'))
        report(before, after, dsn, business_date, ready)
    except Exception as error:
        for source in source_ready:
            if source.startswith('SFX_AUDIT.') and 'ARCHIVE' not in source:
                target = source.removeprefix('SFX_')
                ready.discard(target)
                errors[target] = 'audit execution failed: ' + type(error).__name__ + ': ' + str(error)
        errors['AUDIT.M_RECON_TOTALS_OUTPUT'] = 'audit report unavailable after execution failure'
    return errors, evidence
