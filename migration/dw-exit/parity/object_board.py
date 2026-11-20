"""Measure declared outputs without changing migration or retirement state."""
import argparse
from collections import Counter
import hashlib
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
sys.path.insert(0, str(ROOT / 'migration/dw-exit'))
from parity import local_audit, powercenter_audit, spark_audit
from parity.ladder import local_compare
from parity.provenance import provenance, audit_markdown
from parity.owner_decisions import approved_retirements, approved_summary_ids, apply_retirement
from audit_outputs import outputs as audit_outputs, artifacts as audit_artifacts

SNOWFLAKE_REASON = 'Snowflake login down for run sfg1120; no live capture/prove'


def relation_contract(objects):
    return [dict(obj, output_relations=audit_outputs(obj),
                 **({'output_artifacts': audit_artifacts(obj)} if audit_artifacts(obj) else {}))
            if obj['subject_area'] == 'audit' else dict(obj) for obj in objects]

from parity import dbc_retire


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def relation(name):
    parts = name.split('.')
    if len(parts) != 2:
        raise ValueError('Expected schema.relation')
    return '.'.join(map(quote, parts))


def canonical(value):
    return json.dumps(value, default=str, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def measure(connection, name):
    # Relation and column identifiers are double-quoted, not SQL value parameters.
    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
    cursor = connection.execute('SELECT * FROM ' + relation(name))
    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
    profiles = {}
    for column in columns:
        c = quote(column)
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        values = connection.execute(f'SELECT COUNT(*)-COUNT({c}), MIN({c}), MAX({c}), COUNT(DISTINCT {c}) FROM {relation(name)}').fetchone()
        profiles[column] = dict(zip(('nulls', 'min', 'max', 'distinct'), values))
    return columns, rows, profiles


def compare(before, after, source, target, sample_size=5):
    bcols, brows, bp = measure(before, source)
    acols, arows, ap = measure(after, target)
    if not bcols or bcols != acols:
        raise ValueError('Output column names/order differ')
    def digests(rows):
        return Counter((canonical(row[:1]), hashlib.sha256(canonical(row).encode()).hexdigest()) for row in rows)
    bh, ah = digests(brows), digests(arows)
    def checksum(values):
        return hashlib.sha256(canonical(sorted((key,digest,count) for (key,digest),count in values.items())).encode()).hexdigest()
    delta = (bh-ah) + (ah-bh)
    mismatched_keys = {key for key, digest in delta}
    samples = []
    for key in sorted(mismatched_keys)[:sample_size]:
        samples.append({'key': json.loads(key),
                        'before': sorted((r for r in brows if canonical(r[:1]) == key), key=canonical)[:sample_size],
                        'after': sorted((r for r in arows if canonical(r[:1]) == key), key=canonical)[:sample_size]})
    return {'row_count': {'before': len(brows), 'after': len(arows)},
            'column_profile': {'before': bp, 'after': ap},
            'keyed_row_hash': {'keys': bcols[:1], 'difference': sum(delta.values()),
                               'before': checksum(bh), 'after': checksum(ah),
                               'key_policy': 'first declared column; full-row digest preserves multiplicity'},
            'sampled_differences': samples,
            'passed': len(brows) == len(arows) and canonical(bp) == canonical(ap) and not delta}


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
                    definitions = []
                    for column, dtype, precision, scale in cols:
                        kind = {'smallint': 'SMALLINT', 'integer': 'INTEGER', 'bigint': 'BIGINT',
                                'date': 'DATE', 'timestamp without time zone': 'TIMESTAMP',
                                'timestamp with time zone': 'TIMESTAMPTZ', 'boolean': 'BOOLEAN',
                                'real': 'FLOAT', 'double precision': 'DOUBLE', 'bytea': 'BLOB'}.get(dtype, 'VARCHAR')
                        if dtype == 'numeric':
                            kind = f'DECIMAL({precision or 38},{scale or 0})'
                        definitions.append(quote(column.upper())+' '+kind)
                    source_schema, source_table = name.split('.')
                    # Identifiers are quoted; column types come from the fixed mapping above.
                    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                    connection.execute('CREATE SCHEMA IF NOT EXISTS '+quote(source_schema))
                    # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                    connection.execute(f'CREATE TABLE {relation(name)} ({", ".join(definitions)})')
                    # psycopg Identifier quotes both catalog-derived identifiers.
                    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                    cursor.execute(sql.SQL('SELECT * FROM {}.{}').format(sql.Identifier(schema),sql.Identifier(table)))
                    rows = cursor.fetchall()
                    if rows:
                        connection.executemany(f'INSERT INTO {relation(name)} VALUES ({", ".join("?" for _ in cols)})', rows)
                    ready.add(name)
                except (duckdb.Error, psycopg.Error, ValueError) as error:
                    errors[name] = 'source snapshot: '+type(error).__name__
                    source.rollback()
    return connection, ready, errors


def materialize(before, names, conversion_dir):
    after = duckdb.connect()
    ready, errors = set(), {}
    after.execute('CREATE SCHEMA BILLING')
    for name in sorted(names):
        if not name.startswith('SFX_BILLING.'):
            continue
        table = name.split('.')[1]
        if table.startswith('V_'):
            continue
        target = 'BILLING.'+table
        # DuckDB metadata and identifiers are local; relation()/quote() escape identifiers.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        definitions = before.execute('DESCRIBE '+relation(name)).fetchall()
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        after.execute(f'CREATE TABLE {relation(target)} ({", ".join(quote(c[0])+" "+c[1] for c in definitions)})')
        if table.startswith('STG_'):
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            rows = before.execute('SELECT * FROM '+relation(name)).fetchall()
            if rows:
                after.executemany(f'INSERT INTO {relation(target)} VALUES ({", ".join("?" for _ in definitions)})', rows)
            ready.add(target)
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


def base_build_board(manifest, before=None, after=None, available=None, errors=None, target='duckdb', counters=None):
    if target not in ('duckdb', 'snowflake'):
        raise ValueError('Unsupported parity target')
    objects = manifest['objects']
    result = wave_board(objects, counters or {})
    result.update(run_token=RunConfig.from_env().token, target=target, rows=[])
    result['measurement_contract'] = {'source': 'PostgreSQL Teradata emulator snapshot',
        'local_target': 'DuckDB', 'conversions': ['billing/initial/10_load.sql','billing/initial/30_views.sql'],
        'non_relational_objects': 'declared output relations', 'migration_state': 'BEFORE'}
    available, errors = set(available or ()), errors or {}
    dbc = dbc_retire.materialize() if target == 'duckdb' and any(o['subject_area'] == 'dbc' for o in objects) else None
    dbc_callers = dbc_retire.callers() if dbc is not None else []
    dbc_references = dbc_retire.callers(('warehouse', 'scripts')) if dbc is not None else []
    for obj in objects:
        row = {key:obj[key] for key in ('id','name','kind','wave','owner','subject_area','licence_dependency')}
        row.update(status='red', migration_status='not_started', licence_dependency_count=int(obj['licence_dependency'] != 'none'),
                   row_count=None, column_profile=None, keyed_row_hash=None, sampled_differences=None, reason=None)
        if obj['subject_area'] == 'dbc' and dbc is not None:
            row.update(dbc_retire.measure(obj, dbc, dbc_callers))
            row['retire_evidence']['tooling_references'] = dbc_references
        elif obj['system'] == 'spark':
            if obj.get('source') and (ROOT / obj['source']).is_file():
                row.update(source=obj['source'], source_ref=obj.get('source_ref'))
                row['reason'] = 'Spark source available; output not materialized locally'
            else:
                row['reason'] = 'source on Spark baseline PR'
        elif target == 'snowflake':
            row['reason'] = 'Snowflake target selected; execution disabled'
        elif not obj.get('output_relations'):
            row['reason'] = 'no declared output relation'
        else:
            measured = {}
            for source in obj['output_relations']:
                destination = source.removeprefix('SFX_')
                if destination not in available:
                    row['reason'] = errors.get(destination, errors.get('*', 'output not materialized: '+destination))
                    break
                try:
                    measured[source] = compare(before, after, source, destination)
                except (duckdb.Error, ValueError) as error:
                    row['reason'] = 'measurement failed: '+str(error).splitlines()[0]
                    break
            if row['reason'] is None:
                row['row_count'] = {side:sum(r['row_count'][side] for r in measured.values()) for side in ('before','after')}
                for field in ('column_profile','keyed_row_hash','sampled_differences'):
                    row[field] = {name:values[field] for name,values in measured.items()}
                row['status'] = 'green' if all(r['passed'] for r in measured.values()) else 'red'
                if row['status'] == 'red':
                    row['reason'] = 'measured parity mismatch'
        if obj['subject_area'] == 'dbc':
            row.update(snowflake='red', snowflake_reason='Snowflake login down; no connection attempted (sfg1120)')
        if obj['subject_area'] in ('billing', 'documents', 'users', 'content'):
            row.update(status='red', local_duckdb='red',
                       reason='held back at combine pending fixes/owner decisions')
        result['rows'].append(row)
    if dbc is not None:
        dbc.close()
    total = sum(r['licence_dependency_count'] for r in result['rows'])
    result['summary'] = dict(rows=len(objects), red=sum(r['status']=='red' for r in result['rows']),
        green=sum(r['status']=='green' for r in result['rows']), measured=sum(r['row_count'] is not None for r in result['rows']),
        migrated=0, licence_remaining=total, licence_total=total,
        licence_by_system=dict(Counter(r['licence_dependency'] for r in result['rows'] if r['licence_dependency']!='none')))
    return result



def build_board(manifest, before=None, after=None, available=None, errors=None, target='duckdb',
                counters=None, audit_before=None, audit_after=None, audit_available=None,
                audit_errors=None, audit_pc_results=None):
    result = base_build_board(manifest, before, after, available, errors, target, counters)
    contracts = {o['id']:o for o in relation_contract(manifest['objects'])}
    decisions = approved_retirements()
    for row in result['rows']:
        if row['subject_area'] != 'audit':
            continue
        obj = contracts[row['id']]
        row.update(status='red', reason=None, row_count=None, column_profile=None,
                   keyed_row_hash=None, sampled_differences=None, provenance=provenance(obj),
                   owner_source=obj.get('owner_source'), snowflake='red',
                   snowflake_reason=SNOWFLAKE_REASON)
        measured = {}
        if target != 'duckdb':
            row['reason'] = 'Snowflake target selected; execution disabled'
        elif obj['target_type'] == 'retire':
            row['reason'] = 'retirement proposed; not converted or retired'
            apply_retirement(row, obj, decisions)
        elif obj['system'] == 'powercenter':
            measured = {name:(audit_pc_results or {}).get('measurements',{}).get(name)
                        for name in obj['output_relations']}
            if not measured or not all(measured.values()):
                measured = {}
                row['reason'] = 'PowerCenter audit proof unavailable'
        elif audit_before is None:
            row['reason'] = 'Audit local proof unavailable'
        else:
            for source in obj['output_relations']:
                destination = source.removeprefix('SFX_')
                if destination not in (audit_available or set()):
                    row['reason'] = (audit_errors or {}).get(destination, 'output not materialized: '+destination)
                    break
                try:
                    measured[source] = local_compare(audit_before, audit_after, source, destination)
                except (duckdb.Error, ValueError) as error:
                    row['reason'] = 'measurement failed: '+str(error).splitlines()[0]
                    break
        if measured and row['reason'] is None:
            row['row_count'] = {side:sum(m['row_count'][side] for m in measured.values())
                                for side in ('before','after')}
            for field in ('column_profile','keyed_row_hash','sampled_differences','comparison_rules'):
                row[field] = {name:m[field] for name,m in measured.items()}
            row['status'] = 'green' if all(m['passed'] for m in measured.values()) else 'red'
            row['reason'] = None if row['status'] == 'green' else next(
                (m['reason'] for m in measured.values() if m.get('reason')), 'measured parity mismatch')
            if obj['system'] == 'powercenter' and 'SFX_AUDIT.AUDIT_DAILY_SUMMARY' in measured:
                raw = (audit_pc_results or {}).get('raw_summary_measurement')
                row['raw_summary_measurement'] = raw
                if raw and not raw['passed'] and row['status'] == 'green' and approved_summary_ids() and audit_pc_results.get('summary_non_identity_multiset_matches') is True:
                    row.update(status='approved_deviation', measurement_status='red',
                               decision_state='approved', reason='Owner-approved stable summary IDs by date, customer key NULLS FIRST; raw legacy comparison retained',
                               owner_decision_evidence={'decision_id':'audit-summary-stable-ids',
                                   'contract':audit_pc_results['summary_id_contract'],
                                   'non_identity_multiset_matches':audit_pc_results['summary_non_identity_multiset_matches']})
                elif raw and not raw['passed']:
                    row.update(status='red', reason='Summary ID deviation lacks valid owner approval')
        row['local_duckdb'] = row['status'] if target == 'duckdb' else 'red'
    for state in ('red','green','retired','approved_deviation'):
        result['summary'][state] = sum(r['status']==state for r in result['rows'])
    result['summary']['measured'] = sum(r['row_count'] is not None for r in result['rows'])
    audit = [r for r in result['rows'] if r['subject_area']=='audit']
    result['summary']['audit'] = dict(total=len(audit),
        local_green=sum(r['status']=='green' for r in audit),
        local_red=sum(r['status']=='red' for r in audit),
        local_retired=sum(r['status']=='retired' for r in audit),
        local_approved_deviation=sum(r['status']=='approved_deviation' for r in audit),
        snowflake='red', snowflake_reason=SNOWFLAKE_REASON)
    result['measurement_contract']['audit'] = {'conversions':[
        'audit/'+name for name in ('00_tables.sql','05_landing.sql',*local_audit.STAGES,
                                  '20_routines.sql','50_powercenter.sql','52_sessions.sql','55_workflow.sql')],
        'batch_source':'fresh Teradata chain snapshot',
        'powercenter_source':'fresh isolated rollback-only legacy mappings on same landing PSVs',
        'cross_area_inputs':'read-only source snapshots; not converted by this audit proof'}
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest',type=Path,default=ROOT/'migration/dw-exit/manifest.yaml')
    parser.add_argument('--output',type=Path,default=ROOT/'migration/dw-exit/board/board.json')
    parser.add_argument('--target',choices=['duckdb','snowflake'],default=os.environ.get('PARITY_TARGET','duckdb'))
    args = parser.parse_args()
    manifest = yaml.safe_load(args.manifest.read_text())
    from assess import build
    counters = build()['counters']
    before = after = audit_after = None
    audit_ready, audit_errors, pc_evidence = set(), {}, {}
    audit_evidence, spark_evidence = {}, {}
    ready, errors = set(), {}
    try:
        if args.target == 'duckdb' and manifest['objects']:
            names = {r for obj in manifest['objects'] for r in obj.get('output_relations',[])}
            ns = os.environ.get('NS',RunConfig.from_env().before_namespace)
            port = os.environ.get('TD_PG_PORT',str(54500+zlib.crc32(ns.encode())%1000))
            dsn = os.environ.get('BOARD_SOURCE_DSN',f'host=127.0.0.1 port={port} dbname=teradata user=postgres')
            before, source_ready, source_errors = source_snapshot(dsn,names)
            after, ready, errors = materialize(before,source_ready,ROOT/'migration/dw-exit/billing/initial')
            errors.update(source_errors)
            audit_after = duckdb.connect()
            audit_errors, audit_evidence = local_audit.materialize(before,audit_after,source_ready,dsn,audit_ready,
                os.environ.get('BUSINESS_DATE','20261109'))
            spark_ready, spark_errors, spark_evidence = spark_audit.materialize(
                before,audit_after,relation_contract(manifest['objects']),ns)
            audit_ready.update(spark_ready)
            audit_errors.update(spark_errors)
            pc_errors, pc_evidence = powercenter_audit.materialize(
                before,audit_after,dsn,audit_ready,os.environ.get('BUSINESS_DATE','20261109'))
            audit_errors.update(pc_errors)
        payload = build_board(manifest,before,after,ready,errors,target=args.target,counters=counters,
            audit_before=before,audit_after=audit_after,audit_available=audit_ready,
            audit_errors=audit_errors,audit_pc_results=pc_evidence)
        payload.update(audit_evidence=audit_evidence,audit_powercenter_evidence=pc_evidence,
                       audit_spark_evidence=spark_evidence)
        args.output.write_text(json.dumps(payload,indent=2,default=str)+'\n')
        readme = args.output.parent / 'README.md'
        if readme.exists():
            text = readme.read_text().split('## Audit parity provenance')[0].split('## DBC parity provenance')[0]
            readme.write_text(text.rstrip()+'\n\n'+audit_markdown(payload['rows'])+'\n'+dbc_retire.markdown(payload['rows']))
        print(json.dumps(payload['summary'],sort_keys=True))
    finally:
        if before is not None:
            before.close()
        if after is not None:
            after.close()
        if audit_after is not None:
            audit_after.close()


if __name__ == '__main__':
    main()
