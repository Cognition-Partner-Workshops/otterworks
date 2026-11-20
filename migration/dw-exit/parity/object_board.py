"""Measure declared outputs without changing migration or retirement state."""
import argparse
from collections import Counter
import hashlib
import inspect
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
from parity import dbc_retire, local_audit, powercenter_audit, spark_audit, documents_retirement, spark_documents
from parity import ladder
from parity import pc_users, spark_users, retirement_users, report_outputs, owner_decisions, snowpark_users
from parity.local_billing import execute
from parity.semantics import columns as source_columns, numeric_type
from parity.ladder import local_compare
from parity.provenance import provenance, audit_markdown, markdown, compact_markdown
from parity.owner_decisions import approved_retirements, approved_summary_ids, apply_retirement, decision_registry
from audit_outputs import outputs as audit_outputs, artifacts as audit_artifacts

TARGETS = ('duckdb', 'snowflake')
SNOWFLAKE_REASON = 'Snowflake login down for run sfg1120; no live capture/prove'
SNOWFLAKE_DISABLED = SNOWFLAKE_REASON
HELD_BACK_AREAS = frozenset(('billing', 'content'))
DOCUMENTS_DIRECTORY = ROOT/'migration/dw-exit/documents'
DOCUMENTS_EVIDENCE = ROOT/'migration/dw-exit/board/board.json'
DOCUMENTS_BRANCH = 'devin/sfg1120-integration'
DOCUMENTS_REPOSITORY = 'https://github.com/Cognition-Partner-Workshops/otterworks'
DOCUMENTS_METRICS = {'row_count': ladder.local_measure, 'column_profile': ladder.local_measure,
                     'keyed_row_hash': ladder.local_compare, 'sampled_differences': ladder.local_compare}


def relation_contract(objects):
    retained = {name for d in decision_registry() if d.get('action') == 'retain' and d.get('status') == 'approved'
                for name in d.get('board_objects', [])}
    live_documents = {
        'table': dict(target_type='dbt_model', target='stg_documents__search_index_log'),
        'tpt': dict(target_type='snowflake_scripting', target='RAW_DOCUMENTS.LOAD_DOCUMENTS'),
    }
    return [dict(obj, **live_documents[obj['kind']])
            if obj['subject_area'] == 'documents' and obj['name'] in retained else
            dict(obj, output_relations=audit_outputs(obj),
                 **({'output_artifacts': audit_artifacts(obj)} if audit_artifacts(obj) else {}))
            if obj['subject_area'] == 'audit' else dict(obj) for obj in objects]

from parity import spark_billing, pc_billing, local_documents
from parity.ladder import local_compare as compare


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
    if subject == 'users':
        return materialize_users(before, names, conversion_dir, business_date, after)
    after = duckdb.connect()
    ready, errors = set(), {}
    after.execute('CREATE SCHEMA BILLING')
    if (conversion_dir / '15_storage.sql').exists():
        _, document_errors = local_documents.execute(after, before, business_date=business_date)
        if document_errors:
            errors['*'] = 'Converted documents storage input unavailable: '+str(document_errors)
            return after, ready, errors
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
        # Column rules and literal collation come from checked-in DDL; identifiers are quoted.
        rules = source_columns(name)
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        after.execute(f'CREATE TABLE {relation(target)} ({", ".join(quote(c[0])+" "+c[1]+(" COLLATE NOCASE" if rules.get(c[0], {}).get("case_insensitive") else "") for c in definitions)})')
        if table.startswith('STG_'):
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            rows = before.execute('SELECT * FROM '+relation(name)).fetchall()
            if rows:
                after.executemany(f'INSERT INTO {relation(target)} VALUES ({", ".join("?" for _ in definitions)})', rows)
            ready.add(target)
    if (conversion_dir / '20_routines.sql').exists():
        errors.update(execute(after, conversion_dir, ready, business_date))
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


def base_build_board(manifest, before=None, after=None, available=None, errors=None, target='duckdb', counters=None, preflight=None):
    if target not in ('duckdb', 'snowflake'):
        raise ValueError('Unsupported parity target')
    snowflake_reason = 'Snowflake login down; not run'
    objects = manifest['objects']
    result = wave_board(objects, counters or {})
    result.update(run_token=RunConfig.from_env().token, target=target, rows=[])
    result['measurement_contract'] = {'source': 'PostgreSQL Teradata emulator snapshot',
        'local_target': 'DuckDB', 'conversions': ['billing/'+s for s in ('10_load.sql','15_storage.sql','20_routines.sql','30_views.sql','40_close.sql')],
        'non_relational_objects': 'declared output relations', 'migration_state': 'BEFORE'}
    available, errors = set(available or ()), errors or {}
    dbc = dbc_retire.materialize() if target == 'duckdb' and any(o['subject_area'] == 'dbc' for o in objects) else None
    dbc_callers = dbc_retire.callers() if dbc is not None else []
    dbc_references = dbc_retire.callers(('warehouse', 'scripts')) if dbc is not None else []
    for obj in objects:
        row = {key:obj[key] for key in ('id','name','kind','wave','owner','subject_area','licence_dependency')}
        row.update(status='red', migration_status='not_started', licence_dependency_count=int(obj['licence_dependency'] != 'none'),
                   row_count=None, column_profile=None, keyed_row_hash=None, sampled_differences=None, reason=None)
        if obj['subject_area'] == 'billing':
            row['provenance'] = provenance(obj)
        if obj['subject_area'] == 'dbc' and dbc is not None:
            row.update(dbc_retire.measure(obj, dbc, dbc_callers))
            row['retire_evidence']['tooling_references'] = dbc_references
        elif obj['system'] == 'spark' and not any(name.startswith('SFX_SPARK.') for name in obj.get('output_relations', [])):
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
                if obj['system'] == 'powercenter' and obj['subject_area'] == 'billing':
                    source = source.replace('SFX_BILLING.', 'SFX_PC_BILLING.')
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
                row['comparison_rules'] = {name:values['comparison_rules'] for name,values in measured.items()}
                row['status'] = 'green' if all(r['passed'] for r in measured.values()) else 'red'
                if row['status'] == 'red':
                    row['reason'] = 'measured parity mismatch'
        row.update(local_duckdb=row['status'] if target == 'duckdb' else 'red', snowflake='red', snowflake_reason=SNOWFLAKE_REASON)
        if obj['subject_area'] in HELD_BACK_AREAS:
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
    billing = [row for row in result['rows'] if row['subject_area'] == 'billing']
    local_green = sum(row['local_duckdb'] == 'green' for row in billing)
    result['summary']['billing'] = dict(local_duckdb='green' if billing and local_green == len(billing) else 'red',
        local_green=local_green, local_red=len(billing)-local_green,
        snowflake='red', snowflake_reason=snowflake_reason)
    return result



def materialize_users(before, names, conversion_dir, business_date='20261109', after=None):
    after = after if after is not None else duckdb.connect()
    ready, errors = set(), {}
    schema = 'USERS'
    after.execute('CREATE SCHEMA USERS')
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
        rules = source_columns(name)
        # Identifiers are quoted, types are local DuckDB metadata, and collation is literal SQL.
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        after.execute(f'CREATE TABLE {relation(target)} ({", ".join(quote(c[0])+" "+c[1]+(" COLLATE NOCASE" if rules.get(c[0], {}).get("case_insensitive") else "") for c in definitions)})')
        if table.startswith('STG_'):
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            rows = before.execute('SELECT * FROM '+relation(name)).fetchall()
            if rows:
                after.executemany(f'INSERT INTO {relation(target)} VALUES ({", ".join("?" for _ in definitions)})', rows)
            ready.add(target)
    if (conversion_dir / '20_routines.sql').exists():
        errors.update(execute(after, conversion_dir, ready, business_date, 'users'))
        return after, ready, errors
    return after, ready, errors


def unavailable_cell(reason=None):
    return dict(status='red', reason=reason, row_count=None, column_profile=None,
                keyed_row_hash=None, sampled_differences=None)


def parity_counts(rows):
    return {target: {status: sum(row['targets'][target]['status'] == status for row in rows)
                     for status in ('green', 'red', 'retired', 'approved_deviation', 'amber')
                     if status in ('green','red') or any(row['targets'][target]['status'] == status for row in rows)} for target in TARGETS}


def users_build_board(manifest, before=None, after=None, available=None, errors=None, target='duckdb', counters=None, pc_results=None):
    if target not in TARGETS:
        raise ValueError('Unsupported parity target')
    objects = manifest['objects']
    result = wave_board(objects, counters or {})
    result.update(run_token=RunConfig.from_env().token, rows=[])
    result['measurement_contract'] = {'source': 'PostgreSQL Teradata emulator snapshot',
        'local_target': 'DuckDB', 'conversions': ['billing/initial/10_load.sql','billing/initial/30_views.sql',
            'users/10_load.sql','users/20_routines.sql','users/30_views.sql'],
        'non_relational_objects': 'declared output relations', 'migration_state': 'BEFORE'}
    available, errors = set(available or ()), errors or {}
    retire_evidence = retirement_users.verify() if any(o['subject_area'] == 'users' and o['target_type'] == 'retire' for o in objects) else None
    for obj in objects:
        decision_proofs = []
        row = {key:obj[key] for key in ('id','name','kind','wave','owner','subject_area','licence_dependency')}
        row.update(migration_status='not_started', licence_dependency_count=int(obj['licence_dependency'] != 'none'))
        local = unavailable_cell()
        if obj['system'] == 'spark' and not any(r.startswith('SFX_SPARK.') for r in obj.get('output_relations', [])):
            if obj.get('source') and (ROOT / obj['source']).is_file():
                row.update(source=obj['source'], source_ref=obj.get('source_ref'))
                local['reason'] = 'Spark source available; output not materialized locally'
            else:
                local['reason'] = 'source on Spark baseline PR'
        elif target == 'snowflake':
            local['reason'] = 'Snowflake target selected; execution disabled'
        elif not obj.get('output_relations'):
            local['reason'] = 'no declared output relation'
        else:
            measured = {}
            for source in obj['output_relations']:
                destination = source.removeprefix('SFX_')
                if destination not in available:
                    local['reason'] = errors.get(destination, errors.get('*', 'output not materialized: '+destination))
                    break
                try:
                    measured[source] = (local_compare if obj['subject_area'] == 'users' else compare)(before, after, source, destination)
                    if source in ('SFX_USERS.APP_USER','SFX_USERS.STG_APP_USER'):
                        decision_proofs.append(owner_decisions.display_names(before,after,source,destination))
                    elif not measured[source]['passed']:
                        decision_proofs.append(dict(scope_valid=False))
                except (duckdb.Error, ValueError) as error:
                    local['reason'] = 'measurement failed: '+str(error).splitlines()[0]
                    break
            if local['reason'] is None:
                local['row_count'] = {side:sum(r['row_count'][side] for r in measured.values()) for side in ('before','after')}
                for field in ('column_profile','keyed_row_hash','sampled_differences'):
                    local[field] = {name:values[field] for name,values in measured.items()}
                local['status'] = 'green' if all(r['passed'] for r in measured.values()) else 'red'
                if local['status'] == 'red':
                    local['reason'] = 'measured parity mismatch'
        if obj['subject_area'] == 'users':
            row['provenance'] = provenance(obj)
        mapping = obj['name'].removeprefix('s_')
        if target == 'duckdb' and obj['subject_area'] == 'users' and obj['kind'] in ('mapping','session') and pc_results is not None:
            proof = pc_results[mapping]
            decision_proofs = [proof['owner_decision']] if 'owner_decision' in proof else []
            if mapping == 'm_SFX_APP_USER' and proof.get('snowpark_local'):
                decision_proofs.append(proof['snowpark_local']['input_owner_decision'])
            local['bteq_relation_measurement'] = {k: local.get(k) for k in
                ('status','reason','row_count','column_profile','keyed_row_hash','sampled_differences','comparison_rules')}
            local.update(status=proof['status'],reason=proof['reason'],powercenter=proof,
                       measurement_basis='actual PowerCenter runner targets vs '+('Snowpark local_testing handler' if proof.get('snowpark_local') else 'shipped dbt model')+' on captured inputs')
            measurement = proof['measurement']
            for field in ('row_count','column_profile','keyed_row_hash','sampled_differences','comparison_rules'):
                local[field] = None if measurement is None else (measurement[field] if field == 'row_count' else
                    {'SFX_USERS.'+pc_users.MAPPINGS[mapping]:measurement[field]})
            if mapping == 'm_SFX_APP_USER' and not proof.get('snowpark_local'):
                local.update(status='red',reason='Held on APP_USER display-name truncation decision; isolated PC/dbt proof has hash_difference=0 and does not clear the escalation' if measurement and measurement['keyed_row_hash']['difference'] == 0 else 'Held on APP_USER display-name truncation decision; see independent PC/dbt proof for current measurements')
        if target == 'duckdb' and obj['subject_area'] == 'users' and obj['target_type'] == 'retire':
            approved = (obj['name'] in retirement_users.DEAD | retirement_users.DEPENDENTS
                        and obj['name'] in manifest.get('dead' if obj['name'] in retirement_users.DEAD else 'dead_dependents', [])
                        and retire_evidence['passed'])
            local.update(status='red', retirement_evidence=retire_evidence,
                       reason=(retire_evidence['reason'] if approved else 'Retirement evidence failed or manifest declaration disagrees')+'; '+retirement_users.CAVEAT,
                       row_count=None, column_profile=None, keyed_row_hash=None, sampled_differences=None)
            if approved:
                retirement = dict(local, name=row['name'])
                apply_retirement(retirement, obj, approved_retirements())
                local.update(retirement)
                if local['status'] == 'retired':
                    local['retirement_evidence']['dbql'] = retire_evidence
                    local['reason'] += '; ' + retirement_users.CAVEAT
                else:
                    local['reason'] = 'Retirement lacks approved owner decision; ' + retirement_users.CAVEAT

        row['targets'] = {'duckdb': local, 'snowflake': unavailable_cell(SNOWFLAKE_DISABLED)}
        row.update(local)
        owner_decisions.apply(row, decision_proofs)
        if row.get('decision_state') == 'approved' and mapping == 'm_SFX_APP_USER' and not (pc_results or {}).get(mapping, {}).get('snowpark_local'):
            row.update(input_deviation_status='approved_deviation',status='red',
                       reason='Display-name input deviation approved; TRANSFORM.M_SFX_APP_USER implementation not yet proved')
        local.update({k:v for k,v in row.items() if k in ('status','reason','owner_decision_evidence','measurement_status','decision_state','input_deviation_status')})
        if obj['subject_area'] == 'users':
            row.update(local_duckdb=local['status'], snowflake='red', snowflake_reason=SNOWFLAKE_DISABLED)
        result['rows'].append(row)
    rows = result['rows']
    targets = parity_counts(rows)
    areas = {area: parity_counts([r for r in rows if r['subject_area'] == area])
             for area in sorted({r['subject_area'] for r in rows})}
    total = sum(r['licence_dependency_count'] for r in rows)
    result['summary'] = dict(rows=len(rows), **targets['duckdb'], targets=targets, by_subject_area=areas,
        measured=sum(r['targets']['duckdb']['row_count'] is not None for r in rows),
        migrated=0, licence_remaining=total, licence_total=total,
        licence_by_system=dict(Counter(r['licence_dependency'] for r in rows if r['licence_dependency']!='none')))
    users = [r for r in rows if r['subject_area'] == 'users']
    result['summary']['users'] = dict(local_green=sum(r['status'] == 'green' for r in users),
        local_approved_deviation=sum(r['status'] == 'approved_deviation' for r in users),
        local_red=sum(r['status'] == 'red' for r in users),
        local_retired=sum(r['status'] == 'retired' for r in users), snowflake='red')
    return result


def render_readme(board):
    def count_row(label, counts):
        cells = [f"{counts[target]['green']} green / {counts[target]['red']} red" +
                 (f" / {counts[target]['retired']} retired" if counts[target].get('retired') else '') +
                 (f" / {counts[target]['amber']} amber" if counts[target].get('amber') else '') +
                 (f" / {counts[target]['approved_deviation']} approved_deviation" if counts[target].get('approved_deviation') else '') for target in TARGETS]
        return '| ' + ' | '.join([label, *cells]) + ' |'

    def escape(value):
        return str(value).replace('|', r'\|')

    summary = board['summary']
    lines = ['# Migration board', '', '## Parity by subject area', '',
             'An object counts as green only when its DuckDB column is green.',
             SNOWFLAKE_DISABLED + '.', '',
             '| Subject area | DuckDB | Snowflake |', '|---|---:|---:|',
             count_row('**Total**', summary['targets'])]
    lines.extend(count_row(escape(area), counts) for area, counts in summary['by_subject_area'].items())
    lines += ['', '## Object parity', '', 'See [board.json](board.json) for reasons and measurement evidence.', '',
              '| Object | Subject area | DuckDB | Snowflake |', '|---|---|---|---|']
    for row in board['rows']:
        cells = [row['targets'][target]['status'] for target in TARGETS]
        lines.append('| ' + ' | '.join([escape(row['name']), escape(row['subject_area']), *cells]) + ' |')
    waves = list(board['waves'].values())
    lines += ['', '## Waves', '', '| Count | Wave 1 | Wave 2 | Wave 3 | Wave 4 |',
              '|---|---:|---:|---:|---:|', '| Total | ' + ' | '.join(str(w['total']) for w in waves) + ' |']
    for field in ('by_kind', 'by_target'):
        for key in sorted({k for w in waves for k in w[field]}):
            lines.append(f'| {field}: {key} | ' + ' | '.join(str(w[field].get(key, 0)) for w in waves) + ' |')
    lines += ['', '## Licence counters', '', '| Counter | Remaining | Target |', '|---|---:|---:|']
    lines.extend(f"| {k} | {v['remaining']} | {v['target']} |"
                 for k, v in board['licence_counters'].items() if 'remaining' in v)
    lines += ['', 'All objects remain not_started. Parity measurements do not migrate or retire objects.', '']
    return '\n'.join(lines)


def build_board(manifest, before=None, after=None, available=None, errors=None, target='duckdb',
                counters=None, audit_before=None, audit_after=None, audit_available=None,
                audit_errors=None, audit_pc_results=None, pc_results=None, documents_evidence=None):
    result = base_build_board(manifest, before, after, available, errors, target, counters)
    users_manifest = dict(manifest, objects=[obj for obj in manifest['objects'] if obj['subject_area'] == 'users'])
    if users_manifest['objects']:
        users = users_build_board(users_manifest, before, after, available, errors, target, counters, pc_results)
        replacements = {row['id']: row for row in users['rows']}
        result['rows'] = [replacements.get(row['id'], row) for row in result['rows']]
        result['summary']['users'] = users['summary']['users']
        for row in result['rows']:
            if row['subject_area'] in HELD_BACK_AREAS:
                row.update(status='red', local_duckdb='red', reason='held back at combine pending fixes/owner decisions')
    documents = [obj for obj in relation_contract(manifest['objects']) if obj['subject_area'] == 'documents']
    if documents:
        evidence = dict(documents_evidence or {}, decisions=json.loads((DOCUMENTS_DIRECTORY/'decisions.json').read_text()))
        if target == 'duckdb':
            evidence['retirement'] = documents_retirement.measure(documents)
        else:
            evidence = {'objects': [], 'error': 'Snowflake target selected; execution disabled'}
        replacements = {row['id']:row for row in documents_build_rows(documents, evidence)}
        result['rows'] = [replacements.get(row['id'], row) for row in result['rows']]
    result['owner_decisions'] = decision_registry()
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
                elif raw and not raw['passed'] and row['status'] == 'green':
                    row.update(status='red', reason='Summary ID deviation lacks valid owner approval')
        row['local_duckdb'] = row['status'] if target == 'duckdb' else 'red'
    documents_apply_storage(result['rows'], documents_evidence, target)
    for state in ('red','green','retired','approved_deviation','amber'):
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
    for row in result['rows']:
        local = {key: value for key, value in row.items() if key not in ('targets', 'provenance')}
        row['targets'] = {'duckdb': local, 'snowflake': unavailable_cell(SNOWFLAKE_REASON)}
        row['local_duckdb'] = row['status']
    result['summary']['targets'] = parity_counts(result['rows'])
    result['summary']['by_subject_area'] = {
        area: parity_counts([row for row in result['rows'] if row['subject_area'] == area])
        for area in sorted({row['subject_area'] for row in result['rows']})}
    return result

def documents_link(path, start=None, end=None, ref=DOCUMENTS_BRANCH):
    path = Path(path)
    if path.is_absolute():
        path = path.relative_to(ROOT)
    suffix = f'#L{start}-L{end or start}' if start else ''
    return {'file': str(path), 'start_line': start, 'end_line': end or start,
            'url': f'{DOCUMENTS_REPOSITORY}/blob/{ref}/{path}{suffix}'}


def documents_code_link(function):
    lines, start = inspect.getsourcelines(function)
    return documents_link(inspect.getsourcefile(function), start, start+len(lines)-1)


def documents_evidence_link(path, value):
    if not value:
        return documents_link(path)
    text = path.read_text()
    # Exact indentation and JSON value delimit the top-level evidence group.
    prefix = f'  {json.dumps(value)}: '
    start = text.index('\n'+prefix)+1
    offset = start+len(prefix)
    _, length = json.JSONDecoder().raw_decode(text[offset:])
    return documents_link(path,text.count('\n',0,start)+1,text.count('\n',0,offset+length)+1)


def documents_validated_history(path=DOCUMENTS_DIRECTORY/'spark-replay.json'):
    replay = json.loads(path.read_text())
    if replay['namespace'] != RunConfig.from_env().before_namespace:
        raise ValueError('Binary history belongs to another run namespace')
    if (not replay['passed'] or len(set(replay['dates']))<2
            or not all(s['measurement']['passed'] for s in replay['steps'])):
        raise ValueError('Actual two-date replay has not passed')
    for field in ('landing_sha256','output_sha256','execution_log_sha256','conversion_sha256','legacy_code_sha256'):
        paths = [ROOT/name for name in replay[field]]
        if spark_documents.checksums(paths)!=replay[field]:
            raise ValueError('Stale binary history evidence: '+field)
    runtime = ROOT/'etl/spark/.data'/replay['namespace']
    actual = {str(p.relative_to(ROOT)) for p in (runtime/'lake/documents/file_object_binary_extract').rglob('*.parquet')}
    if actual!=set(replay['output_sha256']):
        raise ValueError('Binary history partitions changed since replay')
    return replay


def materialize_documents(objects, namespace, business_date, pre_pc=None):
    from documents.prove_local import prove
    pre_pc = pre_pc or ROOT/'migration/dw-exit/.runs'/f'documents-{RunConfig.from_env().token}-pre-pc'
    try:
        evidence = prove(pre_pc,ROOT/'warehouse/landing',namespace,business_date, objects=objects)
    except (OSError, ValueError, duckdb.Error) as error:
        evidence = {'objects': [], 'error': 'Documents proof unavailable: '+str(error)}
    evidence['decisions'] = json.loads((DOCUMENTS_DIRECTORY/'decisions.json').read_text())
    with duckdb.connect() as before,duckdb.connect() as after:
        _,errors,jobs = spark_documents.materialize(before,after,objects,namespace)
    try:
        replay = documents_validated_history()
    except (ValueError,OSError) as error:
        replay = {'passed':False,'error':str(error)}
        if 'file_object_binary_extract' in jobs:
            jobs['file_object_binary_extract']['status'] = 'red'
            jobs['file_object_binary_extract']['error'] = str(error)
    evidence['spark'] = {'jobs':jobs,'errors':errors,'binary_history':replay}
    evidence['retirement'] = documents_retirement.measure(objects)
    return evidence


def documents_apply_deviation(item, measurements, decisions):
    if item['status'] != 'red' or item.get('reason'):
        return item
    failing = [measurement for measurement in measurements.values() if not measurement['passed']]
    proofs = [measurement.get('owner_decision', {}) for measurement in failing]
    approvals = {d['decision_id']:d for d in decisions
                 if 'decision_id' in d and d['status'] in ('approved','approved-pending-confirmation')}
    if proofs and all(p.get('decision_id') in approvals and p.get('scope_valid')
                      and p['approved_comparison']['passed'] for p in proofs):
        entries = [approvals[p['decision_id']] for p in proofs]
        pending = [entry['confirmation'] for entry in entries if entry['status']=='approved-pending-confirmation']
        status = 'amber' if pending else 'approved_deviation'
        item.update(status=status,local_duckdb=status,measurement_status='red',
                    reason='; '.join(dict.fromkeys(pending or [d['new_behaviour'] for d in entries])),
                    owner_decision_evidence=proofs)
    return item


def documents_apply_storage(rows, evidence, target='duckdb'):
    if target != 'duckdb' or not evidence:
        return
    decision = next(d for d in decision_registry() if d.get('decision_id') == 'documents-storage-finance-confirmation')
    if decision['status'] != 'approved-pending-confirmation':
        return
    boundary = evidence.get('shared_billing_boundary', {})
    for row in rows:
        if row['name'] not in decision['blocks']:
            continue
        if row['subject_area'] == 'billing':
            measurement = boundary.get(row['name'].split('.')[-1])
            if not measurement or not measurement['passed']:
                continue
            row.update(row_count=measurement['row_count'],
                       **{key:{row['name']:measurement[key]} for key in
                          ('column_profile','keyed_row_hash','sampled_differences')})
        elif row['status'] not in ('green', 'approved_deviation', 'amber'):
            continue
        row.update(status='amber', local_duckdb='amber', decision_state='approved-pending-confirmation',
                   reason=decision['confirmation'], owner_decision_evidence=decision,
                   storage_writer=decision['single_writer'])


def documents_object_measurements(objects, evidence):
    sql = {r['name']:r for r in evidence.get('objects', [])}
    results = {}
    for obj in objects:
        name = obj['name']
        item = {'status':'red','reason':None,'measurements':{},'group':None}
        results[name] = item
        if obj['target_type']=='retire':
            retire = evidence.get('retirement', {}).get(name, {})
            item.update(status=retire.get('status', 'red'), reason=retire.get('reason', 'Retirement proof unavailable'),
                        group='retirement', retirement=retire)
            continue
        if obj['system']=='spark':
            result = evidence.get('spark', {}).get('jobs', {}).get(name, {'status':'red', 'error':'Spark proof unavailable'})
            if 'measurement' in result:
                item['measurements']['SFX_SPARK.'+name.upper()] = result['measurement']
            for relation,side in result.get('side_outputs',{}).items():
                item['measurements'][relation] = side['measurement']
            if name=='file_object_binary_extract' and evidence.get('spark', {}).get('binary_history', {}).get('passed'):
                item['measurements']['SFX_SPARK.'+name.upper()] = evidence['spark']['binary_history']['steps'][-1]['measurement']
            item.update(status=result['status'],reason=result.get('error') or '; '.join(result.get('blockers',[])) or None,
                        group='spark')
            continue
        result = sql.get(name)
        if result is None:
            item['reason'] = evidence.get('error', 'No current documents proof; retained staging/feed is not retired')
            continue
        group = ('shared_billing_boundary' if name=='10_storage_monthly' else 'pc_sessions' if obj['kind']=='session' else
                 'pc_mappings' if obj['kind']=='mapping' else 'tpt_relations' if obj['kind']=='tpt' else 'sql_relations')
        measurements = {relation:evidence[group][relation] for relation in result['relations']}
        item.update(status=result['status'],reason='; '.join(result['blockers']) or None,group=group,measurements=measurements)
        documents_apply_deviation(item,measurements,evidence['decisions'])
        if item['status']=='red' and not item['reason']:
            item['reason'] = 'Measured parity mismatch.' if measurements else 'No local measurements.'
        if item['status']=='green' and name=='SFX_DOCUMENTS.STORAGE_USAGE_DAILY':
            item.update(status='amber',reason='Exact duplicate removal matches Teradata; finance still needs to confirm invoice impact.')
    return results


def documents_build_rows(objects, evidence, evidence_path=DOCUMENTS_EVIDENCE):
    measured = documents_object_measurements(objects,evidence)
    specs = {s['name']:s for path in ('objects.json','spark_jobs.json')
             for s in json.loads((DOCUMENTS_DIRECTORY/path).read_text())}
    rows = []
    for obj in objects:
        item = measured[obj['name']]
        measurements = item['measurements']
        spec = specs.get(obj['name'],{})
        converted = [documents_link(spec[k]) for k in ('conversion','producer','model') if k in spec]
        if obj['system']=='spark':
            converted.extend(documents_link(p) for p in sorted((ROOT/spec['model']).parent.glob('*_jdbc.sql')))
        sources = [documents_link(obj.get('source', 'migration/dw-exit/manifest.yaml'))]
        retirement = item.get('retirement')
        if retirement:
            for query in retirement.get('baseline_queries', []):
                sources.extend([documents_link(documents_retirement.DBQL/'qrylog.csv',query['qrylog_line'],ref=retirement['baseline_commit']),
                                documents_link(documents_retirement.DBQL/'objectusage.csv',query['objectusage_line'],ref=retirement['baseline_commit'])])
        row = {k:obj.get(k) for k in ('id','name','kind','wave','owner','subject_area','licence_dependency','target','target_type')}
        row.update(status=item['status'],local_duckdb=item['status'],reason=item['reason'],
                   migration_status=obj.get('status', 'not_started'),licence_dependency_count=int(obj['licence_dependency']!='none'),
                   snowflake='red',snowflake_reason=SNOWFLAKE_REASON,
                   row_count={side:sum(m['row_count'][side] for m in measurements.values())
                              for side in ('before','after')} if measurements else None,
                   relation_row_counts={relation:m['row_count'] for relation,m in measurements.items()} or None,
                   provenance={'source':sources,'converted':converted,'metrics':{k:documents_code_link(fn) for k,fn in DOCUMENTS_METRICS.items()}},
                   metric_evidence=documents_link(evidence_path))
        for metric in DOCUMENTS_METRICS.keys()-{'row_count'}:
            row[metric] = {relation:m[metric] for relation,m in measurements.items()} or None
        for key in ('retirement','owner_decision_evidence','measurement_status'):
            if key in item:
                row[key] = item[key]
        rows.append(row)
    return rows


def documents_markdown(rows, summary):
    labels = ('green','approved_deviation','amber','retired','red')
    text = ['# sfg1120 Documents — local DuckDB parity board', '',
            ', '.join(f"{summary.get(key,0)} {key.replace('_',' ')}" for key in labels)+'. **Snowflake: red.** '+SNOWFLAKE_REASON,
            '', 'Each metric links to its calculation; evidence includes per-relation profiles, SHA-256s and all fixture differences.',
            '', '| Object | Local DuckDB | Snowflake | Rows (old → new) | Columns profiled | Hash delta | Differing keys | Evidence |',
            '|---|---|---|---:|---:|---:|---:|---|']
    def anchor(label, location):
        return f"[{label}]({location['url']})"
    for row in rows:
        m = row['provenance']['metrics']
        counts = row['row_count']
        values = ['—']*4
        if counts:
            values = [
                anchor(f"{counts['before']} → {counts['after']}",m['row_count']),
                anchor(sum(len(r['before']) for r in row['column_profile'].values()),m['column_profile']),
                anchor(sum(r['difference'] for r in row['keyed_row_hash'].values()),m['keyed_row_hash']),
                anchor(sum(len(r) for r in row['sampled_differences'].values()),m['sampled_differences']),
            ]
        legacy = anchor(row['name'],row['provenance']['source'][0])
        new = row['provenance']['converted']
        evidence = [anchor('Measurements',row['metric_evidence'])]
        if new:
            evidence.append(anchor('Conversion',new[0]))
        if row.get('retirement'):
            count = row['retirement']['baseline_reads']
            evidence = [anchor(f'DBQL: {count} reads',row['metric_evidence'])]
            evidence += [anchor('Query',s) for s in row['provenance']['source'][1::2]]
        text.append('| '+' | '.join([legacy,row['status'].replace('_',' '),'red',*values,', '.join(evidence)])+' |')
    return '\n'.join(text)+'\n'


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
    documents_evidence = None
    ready, errors = set(), {}
    try:
        if args.target == 'duckdb' and manifest['objects']:
            names = {r for obj in manifest['objects'] for r in obj.get('output_relations',[])
                     if not r.startswith('SFX_SPARK.') and r != 'SFX_USERS.M_TEAM_COUNTS_OUTPUT' and r.split('.')[-1] not in report_outputs.OUTPUTS}
            ns = os.environ.get('NS',RunConfig.from_env().before_namespace)
            port = os.environ.get('TD_PG_PORT',str(54500+zlib.crc32(ns.encode())%1000))
            dsn = os.environ.get('BOARD_SOURCE_DSN',f'host=127.0.0.1 port={port} dbname=teradata user=postgres')
            before, source_ready, source_errors = source_snapshot(dsn,names)
            after, ready, errors = materialize(before,source_ready,ROOT/'migration/dw-exit/billing',os.environ.get('BUSINESS_DATE','20261109'))
            errors.update(source_errors)
            if not errors.get('*'):
                errors.update(report_outputs.materialize(before,after,dsn,ready,os.environ.get('BUSINESS_DATE','20261109')))
            spark_ready,spark_errors,billing_spark_evidence = spark_billing.materialize(before,after,manifest['objects'],ns)
            ready.update(spark_ready)
            errors.update(spark_errors)
            pc_ready, pc_errors, billing_pc_evidence = pc_billing.materialize(before, after, dsn, ns, source_snapshot)
            ready.update(pc_ready)
            errors.update(pc_errors)
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
            outputs = {r for obj in manifest['objects'] if obj['subject_area'] == 'users'
                       and obj['target_type'] != 'retire' for r in obj.get('output_relations', [])}
            after, users_ready, users_errors = materialize_users(before, source_ready & outputs,
                ROOT/'migration/dw-exit/users', os.environ.get('BUSINESS_DATE','20261109'), after)
            if '*' in users_errors:
                errors.update({r.removeprefix('SFX_'): users_errors['*'] for r in outputs})
            else:
                errors.update(users_errors)
                errors.update(report_outputs.materialize(before, after, dsn, users_ready,
                    os.environ.get('BUSINESS_DATE','20261109'), 'users'))
            ready.update(users_ready)
            users_ready, users_errors, users_spark_evidence = spark_users.materialize(before, after, manifest['objects'], ns)
            ready.update(users_ready)
            errors.update(users_errors)
        pc_results = users_pc_evidence = None
        if args.target == 'duckdb' and manifest['objects'] and (pc_users.OUT/'capture.json').exists():
            try:
                pc_results, users_pc_evidence = pc_users.proofs(ns, ROOT/'warehouse/landing', os.environ.get('BUSINESS_DATE','20261109'))
                proof = snowpark_users.proof(ns, ROOT/'warehouse/landing', os.environ.get('BUSINESS_DATE','20261109'))
                pc_results['m_SFX_APP_USER'] = dict(status=proof['status'],
                    reason=None if proof['status'] == 'green' else 'Snowpark local / actual PC mismatch',
                    measurement=proof['measurement'], owner_decision=proof['owner_decision'], snowpark_local=proof)
            except (OSError, ValueError, duckdb.Error, ImportError) as error:
                pc_results = {m:dict(status='red', reason='PC evidence unavailable: '+str(error), measurement=None) for m in pc_users.MAPPINGS}
        if args.target == 'duckdb' and any(o['subject_area'] == 'documents' for o in manifest['objects']):
            documents_evidence = materialize_documents(
                [o for o in relation_contract(manifest['objects']) if o['subject_area'] == 'documents'],
                os.environ.get('NS', RunConfig.from_env().before_namespace),
                os.environ.get('BUSINESS_DATE', '20261109'))
        payload = build_board(manifest,before,after,ready,errors,target=args.target,counters=counters,
            audit_before=before,audit_after=audit_after,audit_available=audit_ready,
            audit_errors=audit_errors,audit_pc_results=pc_evidence,pc_results=pc_results,
            documents_evidence=documents_evidence)
        payload.update(audit_evidence=audit_evidence,audit_powercenter_evidence=pc_evidence,
                       audit_spark_evidence=spark_evidence,
                       powercenter_evidence=users_pc_evidence)
        payload['documents_evidence'] = documents_evidence
        if args.target == 'duckdb' and manifest['objects']:
            payload['users_spark_evidence'] = users_spark_evidence
            payload['billing_spark_evidence'] = billing_spark_evidence
            payload['billing_powercenter_evidence'] = billing_pc_evidence
        args.output.write_text(json.dumps(payload,indent=2,default=str)+'\n')
        readme = args.output.parent / 'README.md'
        if readme.exists():
            text = readme.read_text().split('## Audit parity provenance')[0].split('## DBC parity provenance')[0].split('## Documents parity provenance')[0].split('## Billing parity provenance')[0]
            readme.write_text(text.rstrip()+'\n\n'+audit_markdown(payload['rows'])+'\n'+dbc_retire.markdown(payload['rows'])+'\n'+markdown(payload['rows'], 'billing')+'\n'+markdown(payload['rows'], 'users')+'\n## Documents parity provenance\n\n'+documents_markdown(
                [row for row in payload['rows'] if row['subject_area'] == 'documents'],
                payload['summary']['by_subject_area'].get('documents', {})))
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
