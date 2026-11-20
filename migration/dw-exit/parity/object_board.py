"""Measure declared outputs without changing migration or retirement state."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys
import zlib

import duckdb
import psycopg
from psycopg import sql
import sqlglot
from sqlglot import exp
import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'migration/dw-exit/tools'))
sys.path.insert(0, str(ROOT / 'migration/dw-exit'))
from warehouse.run_config import RunConfig
from assess import board as wave_board
from parity.local_billing import execute
from parity.semantics import columns as source_columns, numeric_type
from parity.ladder import local_compare as compare
from parity.provenance import provenance, markdown, compact_markdown, content_provenance, billing_markdown
from parity import report_outputs, spark_billing, dbc_retire, documents_board
from parity import local_audit, powercenter_audit, spark_audit
from parity import spark_users, pc_users, retirement_users
from parity.subjects import SUBJECTS
from audit_outputs import outputs as audit_outputs
from audit_outputs import artifacts as audit_artifacts
from parity import local_content
from parity.owner_decisions import apply_confirmation, apply_deviation, pending_confirmations, approved_retirements, apply_retirement


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def relation(name):
    parts = name.split('.')
    if len(parts) != 2:
        raise ValueError('Expected schema.relation')
    return '.'.join(map(quote, parts))


def source_snapshot(dsn, names):
    connection = duckdb.connect()
    ready, errors = set(), {}
    with psycopg.connect(dsn) as source:
        with source.cursor() as cursor:
            cursor.execute("SELECT table_schema,table_name,column_name,data_type,numeric_precision,numeric_scale FROM information_schema.columns WHERE table_schema LIKE 'sfx_%' ORDER BY table_schema,table_name,ordinal_position")
            columns = {}
            for schema, table, column, dtype, precision, scale in cursor:
                columns.setdefault((schema, table), []).append((column, dtype, precision, scale))
            index = {(s+'.'+t).upper(): (s,t,cols) for (s,t),cols in columns.items()}
            for name in sorted(names):
                if name not in index:
                    errors[name] = 'source output unavailable'
                    continue
                schema, table, cols = index[name]
                try:
                    cursor.execute(sql.SQL('SELECT * FROM {}.{}').format(sql.Identifier(schema),sql.Identifier(table)))
                    rows = cursor.fetchall()
                    definitions = []
                    for column_index, (column, dtype, precision, scale) in enumerate(cols):
                        kind = {'smallint': 'SMALLINT', 'integer': 'INTEGER', 'bigint': 'BIGINT',
                                'date': 'DATE', 'timestamp without time zone': 'TIMESTAMP',
                                'timestamp with time zone': 'TIMESTAMPTZ', 'boolean': 'BOOLEAN',
                                'real': 'FLOAT', 'double precision': 'DOUBLE', 'bytea': 'BLOB'}.get(dtype, 'VARCHAR')
                        if dtype == 'numeric':
                            kind = numeric_type([row[column_index] for row in rows], precision, scale)
                        definitions.append(quote(column.upper())+' '+kind)
                    source_schema, source_table = name.split('.')
                    # Identifiers are quoted; column types come from the fixed mapping above.
                    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                    connection.execute('CREATE SCHEMA IF NOT EXISTS '+quote(source_schema))
                    # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                    connection.execute(f'CREATE TABLE {relation(name)} ({", ".join(definitions)})')
                    # psycopg Identifier quotes both catalog-derived identifiers.
                    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                    if rows:
                        connection.executemany(f'INSERT INTO {relation(name)} VALUES ({", ".join("?" for _ in cols)})', rows)
                    ready.add(name)
                except (duckdb.Error, psycopg.Error, ValueError) as error:
                    errors[name] = 'source snapshot: '+type(error).__name__
                    source.rollback()
    return connection, ready, errors


def materialize(before, names, conversion_dir, business_date='20261109', subject='billing', after=None):
    if subject not in SUBJECTS:
        raise ValueError('Unsupported local subject')
    after = after if after is not None else duckdb.connect()
    ready, errors = set(), {}
    schema = subject.upper()
    # Subject schema is an internal execution-contract key, not source row data.
    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
    after.execute('CREATE SCHEMA '+schema)
    if (conversion_dir / '15_storage.sql').exists():
        rows = before.execute('SELECT * FROM SFX_DOCUMENTS.STORAGE_USAGE_DAILY').fetchall()
        definitions = before.execute('DESCRIBE SFX_DOCUMENTS.STORAGE_USAGE_DAILY').fetchall()
        after.execute('CREATE TABLE BILLING.STORAGE_USAGE_INPUT ('+', '.join(quote(c[0])+' '+c[1] for c in definitions)+')')
        if rows:
            after.executemany('INSERT INTO BILLING.STORAGE_USAGE_INPUT VALUES ('+', '.join('?' for _ in definitions)+')', rows)
    for name in sorted(names):
        if not name.startswith('SFX_'+schema+'.'):
            continue
        table = name.split('.')[1]
        if table.startswith('V_'):
            continue
        target = schema+'.'+table
        # DuckDB metadata and identifiers are local; relation()/quote() escape identifiers.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        definitions = before.execute('DESCRIBE '+relation(name)).fetchall()
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        rules = source_columns(name)
        after.execute(f'CREATE TABLE {relation(target)} ({", ".join(quote(c[0])+" "+c[1]+(" COLLATE NOCASE" if rules.get(c[0], {}).get("case_insensitive") else "") for c in definitions)})')
        if table.startswith('STG_'):
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            rows = before.execute('SELECT * FROM '+relation(name)).fetchall()
            if rows:
                after.executemany(f'INSERT INTO {relation(target)} VALUES ({", ".join("?" for _ in definitions)})', rows)
            ready.add(target)
    if (conversion_dir / '20_routines.sql').exists():
        errors.update(execute(after, conversion_dir, ready, business_date, subject))
        return after, ready, errors
    for filename in ('10_load.sql', '30_views.sql'):
        text = RunConfig.from_env().render((conversion_dir / filename).read_text())
        try:
            statements = sqlglot.parse(text, read='snowflake')
        except sqlglot.errors.ParseError:
            errors['*'] = 'conversion parse failed: '+filename
            continue
        for statement in statements:
            if statement is None:
                continue
            for table in statement.find_all(exp.Table):
                table.set('catalog', None)
            if isinstance(statement, exp.Create):
                target = statement.this.sql(dialect='duckdb', comments=False)
                query = statement.expression
                if not isinstance(query, exp.Query):
                    continue
                references = {(t.db+'.'+t.name).upper() for t in query.find_all(exp.Table)}
                if not references <= ready:
                    errors[target] = 'conversion input not materialized'
                    continue
                statement.set('properties', None)
            elif isinstance(statement, (exp.Insert, exp.Delete)):
                target = statement.this.sql(dialect='duckdb', comments=False)
                references = {(t.db+'.'+t.name).upper() for t in statement.expression.find_all(exp.Table)} if isinstance(statement, exp.Insert) else set()
                if not references <= ready:
                    errors[target] = 'conversion input not materialized'
                    continue
            else:
                continue
            try:
                after.execute(statement.sql(dialect='duckdb', comments=False))
                if not isinstance(statement, exp.Delete):
                    ready.add(target)
            except duckdb.Error as error:
                ready.discard(target)
                errors[target] = 'conversion failed: '+str(error).splitlines()[0]
    return after, ready, errors


def relation_contract(objects):
    rows = []
    for obj in objects:
        row = dict(obj)
        if obj['subject_area'] == 'audit':
            row['output_relations'] = audit_outputs(obj)
            if audit_artifacts(obj):
                row['output_artifacts'] = audit_artifacts(obj)
        elif obj['subject_area'] == 'users' and obj['system'] == 'spark':
            row['output_relations'] = ['SFX_SPARK.'+obj['name'].upper()]
        elif obj['name'] == 'SFX_USERS.M_TEAM_COUNTS':
            row['output_relations'] = ['SFX_USERS.M_TEAM_COUNTS_OUTPUT']
        elif obj['name'] == '10_activity_daily':
            row['output_relations'] = ['SFX_USERS.USER_ACTIVITY_DAILY','SFX_USERS.M_TEAM_COUNTS_OUTPUT']
        rows.append(row)
    return rows


def build_board(manifest, before=None, after=None, available=None, errors=None, target='duckdb', counters=None, preflight=None, subject_evidence=None, pc_results=None, content_available=None, audit_pc_results=None):
    if target not in ('duckdb', 'snowflake'):
        raise ValueError('Unsupported parity target')
    if preflight is not None and (preflight.get('run_token') != RunConfig.from_env().token
            or preflight.get('database') != RunConfig.from_env().database
            or preflight.get('status') != 'red' or not preflight.get('reason')
            or preflight.get('capture_run') is not False or preflight.get('prove_run') is not False):
        raise ValueError('Expected a denied, unexecuted preflight for the current run scope')
    snowflake_reason = preflight['reason'] if preflight else 'No live Snowflake evidence; capture/prove not run'
    objects = relation_contract(manifest['objects'])
    confirmations = pending_confirmations()
    retirements = approved_retirements()
    result = wave_board(objects, counters or {})
    result.update(run_token=RunConfig.from_env().token, target=target, rows=[])
    result['measurement_contract'] = {'source': 'PostgreSQL Teradata emulator snapshot',
        'local_target': 'DuckDB', 'conversions': ['billing/'+s for s in ('10_load.sql','15_storage.sql','20_routines.sql','30_views.sql','40_close.sql')]
            + ['audit/'+s for s in ('00_tables.sql','05_landing.sql',*local_audit.STAGES,'20_routines.sql','50_powercenter.sql','52_sessions.sql','55_workflow.sql')],
        'non_relational_objects': 'declared output relations', 'migration_state': 'BEFORE'}
    result['measurement_contract']['conversions'].extend('users/'+s for s in SUBJECTS['users']['stages'])
    result['measurement_contract']['content'] = {'source': 'actual PowerCenter wf_SFX_CONTENT_DAILY execution',
        'conversion': 'content/workflow.sql', 'scope': 'content workflow only; not standalone mapping proof'}
    available, errors = set(available or ()), errors or {}
    dbc = dbc_retire.materialize() if target == 'duckdb' and any(o['subject_area']=='dbc' for o in objects) else None
    dbc_callers = dbc_retire.callers() if dbc is not None else []
    retire_evidence = retirement_users.verify() if any(o['subject_area'] == 'users' and o['target_type'] == 'retire' for o in objects) else None
    for obj in objects:
        row = {key:obj[key] for key in ('id','name','kind','wave','owner','subject_area','licence_dependency')}
        row.update(status='red', migration_status='not_started', licence_dependency_count=int(obj['licence_dependency'] != 'none'),
                   row_count=None, column_profile=None, keyed_row_hash=None, sampled_differences=None, reason=None)
        if obj['subject_area'] in ('billing','documents','audit','users'):
            row['provenance'] = provenance(obj)
        elif obj['subject_area'] == 'content':
            row['provenance'] = content_provenance(obj)
        if obj['subject_area']=='documents':
            detail = (subject_evidence or {}).get('documents',{}).get(obj['name']) if target=='duckdb' else None
            if detail:
                row.update(status=detail['status'],reason=detail['reason'])
                measured = detail['measurements']
                apply_deviation(row, measured, detail.get('decisions',[]))
                if measured:
                    row['row_count'] = {side:sum(r['row_count'][side] for r in measured.values()) for side in ('before','after')}
                    for field in ('column_profile','keyed_row_hash','sampled_differences','comparison_rules'):
                        row[field] = {name:values[field] for name,values in measured.items()}
                row['metric_evidence'] = detail.get('metric_evidence',{})
            else:
                row['reason'] = 'Documents proof unavailable' if target=='duckdb' else 'Snowflake target selected; execution disabled'
            row.update(local_duckdb=row['status'] if target=='duckdb' else 'red',snowflake='red',
                       snowflake_reason=snowflake_reason,snowflake_preflight=preflight)
            if target == 'duckdb':
                apply_confirmation(row, confirmations)
            result['rows'].append(row)
            continue
        if obj['subject_area'] == 'dbc' and dbc is not None:
            row.update(dbc_retire.measure(obj, dbc, dbc_callers))
        elif obj['system'] == 'spark' and not any(name.startswith('SFX_SPARK.') for name in obj.get('output_relations', [])):
            if obj.get('source') and (ROOT / obj['source']).is_file():
                row.update(source=obj['source'], source_ref=obj.get('source_ref'))
                row['reason'] = 'Spark source available; output not materialized locally'
            else:
                row['reason'] = 'source on Spark baseline PR'
        elif obj.get('target_type') == 'retire' and obj['subject_area'] == 'audit':
            row['reason'] = 'retirement proposed; not converted or retired'
            if target == 'duckdb':
                apply_retirement(row, obj, retirements)
        elif target == 'snowflake':
            row['reason'] = 'Snowflake target selected; execution disabled'
        elif not obj.get('output_relations'):
            row['reason'] = 'no declared output relation'
        else:
            measured = {}
            row_available = available | set(content_available or ()) if obj['subject_area'] == 'content' else available
            for source in obj['output_relations']:
                destination = source.removeprefix('SFX_')
                if destination not in row_available:
                    row['reason'] = errors.get(destination, errors.get('*', 'output not materialized: '+destination))
                    break
                try:
                    measured[source] = compare(before, after, source, destination,
                                               sample_size=None if obj['subject_area'] == 'content' else 5)
                except (duckdb.Error, ValueError) as error:
                    row['reason'] = 'measurement failed: '+str(error).splitlines()[0]
                    break
            if row['reason'] is None:
                row['row_count'] = {side:sum(r['row_count'][side] for r in measured.values()) for side in ('before','after')}
                for field in ('column_profile','keyed_row_hash','sampled_differences'):
                    row[field] = {name:values[field] for name,values in measured.items()}
                row['comparison_rules'] = {name:values['comparison_rules'] for name,values in measured.items()}
                if obj['subject_area'] == 'content':
                    row['relation_results'] = measured
                row['status'] = 'green' if all(r['passed'] for r in measured.values()) else 'red'
                if row['status'] == 'red':
                    row['reason'] = 'measured parity mismatch'
                    if obj['subject_area'] == 'content':
                        differing = [name for name, values in measured.items() if not values['passed']]
                        row['reason'] = (local_content.DISPLAY_NAME_DECISION if differing == ['SFX_USERS.STG_APP_USER']
                                         else 'measured parity mismatch: '+', '.join(differing))
        mapping = obj['name'].removeprefix('s_')
        if obj['subject_area'] == 'content' and (subject_evidence or {}).get('content'):
            measured = subject_evidence['content']
            row['relation_results'] = measured
            row['status'] = 'green' if all(r['passed'] for r in measured.values()) else 'red'
            differing = [name for name,r in measured.items() if not r['passed']]
            row['reason'] = None if not differing else (local_content.DISPLAY_NAME_DECISION if differing == ['SFX_USERS.STG_APP_USER'] else 'measured parity mismatch: '+', '.join(differing))
            row['row_count'] = {side:sum(r['row_count'][side] for r in measured.values()) for side in ('before','after')}
            for field in ('column_profile','keyed_row_hash','sampled_differences','comparison_rules'):
                row[field] = {name:r[field] for name,r in measured.items()}
        if obj['subject_area'] == 'audit' and obj['system'] == 'powercenter' and obj['target_type'] != 'retire':
            measured = {name:(audit_pc_results or {}).get('measurements',{}).get(name) for name in obj['output_relations']}
            if target == 'duckdb' and measured and all(measured.values()):
                row['status'] = 'green' if all(r['passed'] for r in measured.values()) else 'red'
                row['reason'] = None if row['status'] == 'green' else 'PowerCenter audit measured parity mismatch'
                row['row_count'] = {side:sum(r['row_count'][side] for r in measured.values()) for side in ('before','after')}
                for field in ('column_profile','keyed_row_hash','sampled_differences','comparison_rules'):
                    row[field] = {name:r[field] for name,r in measured.items()}
            else:
                row.update(status='red',reason='PowerCenter audit proof unavailable',row_count=None,
                           column_profile=None,keyed_row_hash=None,sampled_differences=None)
        if target == 'duckdb' and obj['subject_area'] == 'users' and obj['kind'] in ('mapping','session') and pc_results is not None:
            proof = pc_results[mapping]
            row['bteq_relation_measurement'] = {k: row.get(k) for k in
                ('status','reason','row_count','column_profile','keyed_row_hash','sampled_differences','comparison_rules')}
            row.update(status=proof['status'],reason=proof['reason'],powercenter=proof,
                       measurement_basis='actual PowerCenter runner targets vs shipped dbt model on captured inputs')
            measurement = proof['measurement']
            for field in ('row_count','column_profile','keyed_row_hash','sampled_differences','comparison_rules'):
                row[field] = None if measurement is None else (measurement[field] if field == 'row_count' else
                    {'SFX_USERS.'+pc_users.MAPPINGS[mapping]:measurement[field]})
        if target == 'duckdb' and obj['subject_area'] == 'users' and obj['target_type'] == 'retire':
            approved = (obj['name'] in retirement_users.DEAD | retirement_users.DEPENDENTS
                        and obj['name'] in manifest.get('dead' if obj['name'] in retirement_users.DEAD else 'dead_dependents', [])
                        and retire_evidence['passed'])
            row.update(status='retire_verified' if approved else 'red', retirement_evidence=retire_evidence,
                       reason=(retire_evidence['reason'] if approved else 'Retirement evidence failed or manifest declaration disagrees')+'; '+retirement_users.CAVEAT,
                       row_count=None, column_profile=None, keyed_row_hash=None, sampled_differences=None)
        if obj['subject_area'] in ('billing','audit','users','content'):
            row.update(local_duckdb=row['status'] if target == 'duckdb' else 'red',
                       snowflake='red', snowflake_reason=snowflake_reason,
                       snowflake_preflight=preflight)
        if target == 'duckdb':
            apply_confirmation(row, confirmations)
        result['rows'].append(row)
    if dbc is not None:
        dbc.close()
    total = sum(r['licence_dependency_count'] for r in result['rows'])
    result['summary'] = dict(rows=len(objects), red=sum(r['status']=='red' for r in result['rows']),
        retire_verified=sum(r['status']=='retire_verified' for r in result['rows']),
        green=sum(r['status']=='green' for r in result['rows']), amber=sum(r['status']=='amber' for r in result['rows']), measured=sum(r['row_count'] is not None for r in result['rows']),
        approved_deviation=sum(r['status']=='approved_deviation' for r in result['rows']),
        migrated=0, licence_remaining=total, licence_total=total,
        licence_by_system=dict(Counter(r['licence_dependency'] for r in result['rows'] if r['licence_dependency']!='none')))
    billing = [row for row in result['rows'] if row['subject_area'] == 'billing']
    local_green = sum(row['local_duckdb'] == 'green' for row in billing)
    result['summary']['billing'] = dict(local_duckdb='green' if billing and local_green == len(billing) else 'red',
        local_green=local_green, local_red=len(billing)-local_green,
        snowflake='red', snowflake_reason=snowflake_reason)
    documents = [row for row in result['rows'] if row['subject_area']=='documents']
    if documents:
        counts = Counter(row['status'] for row in documents)
        result['summary']['documents'] = dict(total=len(documents),local_green=counts['green'],local_red=counts['red'],
            local_approved_deviation=counts['approved_deviation'],
            local_amber=counts['amber'], retired=counts['retired'],local_duckdb='red' if counts['red'] else 'amber' if counts['amber'] else 'approved_deviation' if counts['approved_deviation'] else 'green',snowflake='red',snowflake_reason=snowflake_reason)
    audit = [row for row in result['rows'] if row['subject_area'] == 'audit']
    audit_green = sum(row['local_duckdb'] == 'green' for row in audit)
    result['summary']['audit'] = dict(local_green=audit_green,
        local_retired=sum(row['local_duckdb'] == 'retired' for row in audit),
        local_red=sum(row['local_duckdb'] == 'red' for row in audit),
        snowflake='red', snowflake_reason=snowflake_reason)
    for subject in {'users'}:
        rows = [row for row in result['rows'] if row['subject_area'] == subject]
        green = sum(row['local_duckdb'] == 'green' for row in rows)
        retired = sum(row['local_duckdb'] == 'retire_verified' for row in rows)
        result['summary'][subject] = dict(local_duckdb='green' if rows and green == len(rows) else 'red',
            local_green=green, local_retire_verified=retired, local_red=len(rows)-green-retired,
            snowflake='red', snowflake_reason=snowflake_reason)
    content = [row for row in result['rows'] if row['subject_area'] == 'content']
    result['summary']['content'] = dict(local_green=sum(row['local_duckdb'] == 'green' for row in content),
                                      local_red=sum(row['local_duckdb'] == 'red' for row in content), snowflake='red')
    result['summary']['retired'] = sum(row['status']=='retired' for row in result['rows'])
    result['summary']['areas'] = {}
    for subject in sorted({row['subject_area'] for row in result['rows']}):
        rows = [row for row in result['rows'] if row['subject_area'] == subject]
        counts = Counter(row['status'] for row in rows)
        result['summary']['areas'][subject] = dict(total=len(rows), green=counts['green'],
            approved_deviation=counts['approved_deviation'], amber=counts['amber'],
            retire=counts['retired']+counts['retire_verified'], red=counts['red'])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest',type=Path,default=ROOT/'migration/dw-exit/manifest.yaml')
    parser.add_argument('--output',type=Path,default=ROOT/'migration/dw-exit/board/board.json')
    parser.add_argument('--target',choices=['duckdb','snowflake'],default=os.environ.get('PARITY_TARGET','duckdb'))
    parser.add_argument('--snowflake-preflight',type=Path,default=ROOT/'migration/dw-exit/parity/snowflake-preflight.json')
    parser.add_argument('--refresh-confirmations',action='store_true')
    args = parser.parse_args()
    if args.refresh_confirmations:
        payload = json.loads(args.output.read_text())
        for row in payload['rows']:
            apply_confirmation(row, pending_confirmations())
        payload['summary']['amber'] = sum(row['status']=='amber' for row in payload['rows'])
        for state in ('green','red'):
            payload['summary'][state] = sum(row['status']==state for row in payload['rows'])
        args.output.write_text(json.dumps(payload,indent=2,default=str)+'\n')
        print(json.dumps(payload['summary'],sort_keys=True))
        return
    manifest = yaml.safe_load(args.manifest.read_text())
    manifest['objects'] = relation_contract(manifest['objects'])
    preflight = json.loads(args.snowflake_preflight.read_text()) if args.snowflake_preflight.is_file() else None
    from assess import build
    counters = build()['counters']
    before = after = None
    ready, errors = set(), {}
    documents_evidence = None
    subject_evidence = {}
    try:
        if args.target == 'duckdb' and manifest['objects']:
            names = {r for obj in manifest['objects'] for r in obj.get('output_relations',[])
                     if not r.startswith('SFX_SPARK.') and r.split('.')[-1] not in set.union(*report_outputs.SUBJECT_OUTPUTS.values()) | {'M_RECON_TOTALS_OUTPUT'}}
            ns = os.environ.get('NS',RunConfig.from_env().before_namespace)
            port = os.environ.get('TD_PG_PORT',str(54500+zlib.crc32(ns.encode())%1000))
            dsn = os.environ.get('BOARD_SOURCE_DSN',f'host=127.0.0.1 port={port} dbname=teradata user=postgres')
            before, source_ready, source_errors = source_snapshot(dsn,names)
            after, ready, errors = materialize(before,source_ready,ROOT/'migration/dw-exit/billing',os.environ.get('BUSINESS_DATE','20261109'))
            errors.update(source_errors)
            with duckdb.connect() as content_before, duckdb.connect() as content_after:
                for source in local_content.OUTPUTS:
                    local_content.clone(before,content_before,source,source)
                content_ready,content_errors,content_evidence = local_content.materialize(
                    content_before,content_after,dsn,ns,source_snapshot,os.environ.get('BUSINESS_DATE','20261109'))
                if content_ready:
                    subject_evidence['content'] = {source:compare(content_before,content_after,source,source.removeprefix('SFX_'))
                                                   for source in local_content.OUTPUTS}
            errors.update(content_errors)
            if not errors.get('*'):
                errors.update(report_outputs.materialize(before,after,dsn,ready,os.environ.get('BUSINESS_DATE','20261109')))
            for subject in SUBJECTS.keys() - {'billing'}:
                outputs = {r for obj in manifest['objects'] if obj['subject_area'] == subject
                           and obj['target_type'] != 'retire' for r in obj.get('output_relations', [])}
                after, subject_ready, subject_errors = materialize(before, source_ready & outputs,
                    ROOT/'migration/dw-exit'/subject, os.environ.get('BUSINESS_DATE','20261109'), subject, after)
                if '*' in subject_errors:
                    errors.update({r.removeprefix('SFX_'): subject_errors['*'] for r in outputs})
                else:
                    errors.update(subject_errors)
                    errors.update(report_outputs.materialize(before,after,dsn,subject_ready,
                        os.environ.get('BUSINESS_DATE','20261109'),subject))
                ready.update(subject_ready)
            spark_ready,spark_errors,spark_evidence = spark_billing.materialize(before,after,manifest['objects'],ns)
            ready.update(spark_ready)
            errors.update(spark_errors)
            if any(o['subject_area']=='documents' for o in manifest['objects']):
                documents_evidence = documents_board.measure(manifest,ns,os.environ.get('BUSINESS_DATE','20261109'))
                subject_evidence['documents'] = documents_board.object_measurements(manifest,documents_evidence)
            audit_spark_ready, audit_spark_errors, audit_spark_evidence = spark_audit.materialize(before,after,manifest['objects'],ns)
            ready.update(audit_spark_ready)
            errors.update(audit_spark_errors)
            audit_errors, audit_evidence = local_audit.materialize(before,after,source_ready,dsn,ready,
                os.environ.get('BUSINESS_DATE','20261109'))
            errors.update(audit_errors)
            pc_errors, audit_pc_evidence = powercenter_audit.materialize(before,after,dsn,ready,
                os.environ.get('BUSINESS_DATE','20261109'))
            errors.update(pc_errors)
            users_ready,users_errors,users_evidence = spark_users.materialize(before,after,manifest['objects'],ns)
            ready.update(users_ready)
            errors.update(users_errors)
            spark_evidence.update(users_evidence)
        pc_results = None
        pc_evidence = None
        if args.target == 'duckdb' and manifest['objects'] and (pc_users.OUT/'capture.json').exists():
            try:
                pc_results, pc_evidence = pc_users.proofs(ns,ROOT/'warehouse/landing',os.environ.get('BUSINESS_DATE','20261109'))
            except (OSError,ValueError,duckdb.Error) as error:
                pc_results = {m:dict(status='red',reason='PC evidence unavailable: '+str(error),measurement=None) for m in pc_users.MAPPINGS}
        payload = build_board(manifest,before,after,ready,errors,target=args.target,counters=counters,preflight=preflight,subject_evidence=subject_evidence,pc_results=pc_results,content_available=content_ready if args.target == 'duckdb' and manifest['objects'] else None,audit_pc_results=audit_pc_evidence if args.target == 'duckdb' and manifest['objects'] else None)
        if pc_evidence is not None:
            payload['powercenter_evidence'] = pc_evidence
        if args.target == 'duckdb' and manifest['objects']:
            payload['spark_evidence'] = spark_evidence
            payload['audit_evidence'] = audit_evidence
            payload['audit_powercenter_evidence'] = audit_pc_evidence
            payload['audit_spark_evidence'] = audit_spark_evidence
            payload['content_evidence'] = content_evidence
        if documents_evidence is not None:
            payload['documents_evidence'] = {'file':'migration/dw-exit/documents/evidence.json',
                'binary_replay':'migration/dw-exit/documents/spark-replay.json'}
        args.output.write_text(json.dumps(payload,indent=2,default=str)+'\n')
        readme = args.output.parent / 'README.md'
        if readme.exists():
            text = readme.read_text().split('\n## Billing parity provenance')[0]
            readme.write_text(text.rstrip()+'\n'+markdown(payload['rows'],documents_evidence)+dbc_retire.markdown(payload['rows']))
        if documents_evidence is not None:
            from parity.provenance import documents_table
            (ROOT/'migration/dw-exit/documents/parity-table.md').write_text(documents_table(documents_evidence))
        (args.output.parent/'users-pr.md').write_text(billing_markdown(payload['rows'], 'users')+compact_markdown(payload['rows']))
        print(json.dumps(payload['summary'],sort_keys=True))
    finally:
        if before is not None:
            before.close()
        if after is not None:
            after.close()


if __name__ == '__main__':
    main()
