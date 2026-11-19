"""Measure the documents subject area: legacy outputs against shipped conversions on the same inputs."""
import csv
import os
from pathlib import Path
import re
import zlib

import duckdb
import psycopg
import sqlglot
from sqlglot import exp

from warehouse.run_config import render
from .connection import validate_date
from .semantics import columns as source_columns
from . import spark_billing

ROOT = Path(__file__).resolve().parents[3]
CONVERSION = Path('migration/dw-exit/documents')
RETIRED = ('SEARCH_INDEX_LOG', 'STG_SEARCH_INDEX_LOG', 'V_SEARCH_HISTORY')
PC_MODELS = ('stg_app_user', 'app_user', 'stg_document', 'document', 'doc_share')

# Objects that stay red until the named owner answers; measurement is still recorded.
OWNER_DECISIONS = {
    'set_table_dedupe': ('SET-table exact-duplicate dedupe on SFX_DOCUMENTS.STORAGE_USAGE_DAILY is undecided',
        {'SFX_DOCUMENTS.STORAGE_USAGE_DAILY', '05_load_sessions', '10_storage_monthly', 'SFX_DOCUMENTS.M_STORAGE_TOTALS'}),
    'version_tie_break': ('Tie-break for equal latest VERSION_TS in 02_current_versions is undecided',
        {'02_current_versions', 'SFX_DOCUMENTS.DOC_VERSION', 'SFX_DOCUMENTS.V_DOCUMENT_VERSIONS', 'SFX_DOCUMENTS.V_WORKSPACE_STORAGE'}),
    'role_precedence': ('Role precedence for users with multiple grants in m_SFX_DOC_SHARE (PowerCenter "Use First Value") is undecided',
        {'m_SFX_DOC_SHARE', 's_m_SFX_DOC_SHARE'}),
}


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def ddl_columns(relation):
    schema, table = relation.split('.')
    for path in sorted((ROOT/'warehouse/teradata/ddl').rglob('*.sql')):
        match = re.search(r'TABLE\s+'+schema+r'\.'+table+r'\s*,.*?\((.*?)\n\)', path.read_text(), re.S)
        if match:
            return [line.split()[0] for line in match[1].strip().splitlines()]
    raise ValueError('No source DDL for '+relation)


def duck(statement):
    for table in statement.find_all(exp.Table):
        table.set('catalog', None)
    if isinstance(statement, exp.Create):
        statement.set('properties', None)
    return statement.sql(dialect='duckdb', comments=False)


def sections(path, pattern):
    """Yield (label, first line, last line, text) for each marked block of a conversion file."""
    text = (ROOT/path).read_text()
    marks = list(re.finditer(pattern, text, re.M))
    for index, mark in enumerate(marks):
        end = marks[index+1].start() if index+1 < len(marks) else len(text)
        body = text[mark.start():end].rstrip()
        start = text.count('\n', 0, mark.start())+1
        yield mark[1], start, start+body.count('\n'), body


def span(path, start=1, end=None):
    return (Path(path).as_posix(), start, end or len((ROOT/path).read_text().splitlines()))


def load_psv(connection, target, path, names):
    if not Path(path).stat().st_size:
        connection.execute('CREATE TABLE '+target+' ('+', '.join(quote(n)+' VARCHAR' for n in names)+')')
        return
    connection.read_csv(str(path), delimiter='|', header=False, names=names, all_varchar=True,
                        na_values='', quotechar='"', escapechar='"').create(target)


def teradata(before, after, dsn, business_date, results, by_name):
    for schema in ('RAW_DOCUMENTS', 'DOCUMENTS', 'COMPAT', 'OPS'):
        after.execute('CREATE SCHEMA '+schema)
    tables = [row[0] for row in before.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='SFX_DOCUMENTS'").fetchall()]
    tables = sorted(t for t in tables if not t.startswith('V_') and t not in RETIRED and not t.endswith('_OUTPUT'))
    for table in tables:
        rules = source_columns('SFX_DOCUMENTS.'+table)
        definitions = before.execute('DESCRIBE SFX_DOCUMENTS.'+quote(table)).fetchall()
        after.execute('CREATE TABLE DOCUMENTS.'+quote(table)+' ('+', '.join(
            quote(c[0])+' '+c[1]+(' COLLATE NOCASE' if rules.get(c[0], {}).get('case_insensitive') else '') for c in definitions)+')')
    landing = Path(os.environ.get('LANDING_DIR', ROOT/'warehouse/landing'))/'documents'
    for table in tables:
        if table.startswith('STG_'):
            load_psv(after, 'RAW_DOCUMENTS.'+table[4:], landing/table[4:]/(business_date+'.psv'), ddl_columns('SFX_DOCUMENTS.'+table))
    stage = {label: (start, end, body) for label, start, end, body in sections(CONVERSION/'05_stage.sql', r'^-- (documents_\w+)\.tpt$')}
    loads = {label: (start, end, body) for label, start, end, body in sections(CONVERSION/'10_load.sql', r'^-- (\d\d_\w+)\.bteq$')}
    failed = {}

    def run(label, text):
        try:
            for statement in sqlglot.parse(render(text), read='snowflake'):
                if statement is not None:
                    after.execute(duck(statement))
        except (duckdb.Error, sqlglot.errors.SqlglotError) as error:
            failed[label] = 'conversion failed: '+str(error).splitlines()[0]

    for label, (_, _, body) in stage.items():
        run(label, body)
    for label, (_, _, body) in loads.items():
        run(label, re.search(r'\$\$\s*BEGIN(.*?)RETURN ', body, re.S)[1])
    views = {label: (start, end, body) for label, start, end, body in
             sections(CONVERSION/'30_views.sql', r'^CREATE OR REPLACE VIEW \S+\.SFX_DOCUMENTS__(\w+)$')}
    for label, (_, _, body) in views.items():
        run(label, body)
    routines = {label.strip('"'): (start, end, body) for label, start, end, body in
                sections(CONVERSION/'20_routines.sql', r'^CREATE OR REPLACE PROCEDURE \S+\.OPS\.("?\w+"?)')}
    start_day = business_date[:6]+'01'
    macro_source = re.search(r'AS \((.*?);\s*\);', (ROOT/'warehouse/teradata/macros/storage_totals.sql').read_text(), re.S)[1]
    window = {'p_start': f"DATE '{start_day[:4]}-{start_day[4:6]}-01'", 'p_end': f"(DATE '{start_day[:4]}-{start_day[4:6]}-01' + INTERVAL '1 month')"}
    try:
        with psycopg.connect(dsn) as source, source.cursor() as cursor:
            cursor.execute(re.sub(r':(p_start|p_end)', lambda m: window[m[1]], macro_source))
            rows = cursor.fetchall()
        before.execute('CREATE TABLE SFX_DOCUMENTS.M_STORAGE_TOTALS_OUTPUT (CUSTOMER_ID BIGINT, BYTES_USED BIGINT, OBJECT_COUNT BIGINT)')
        if rows:
            before.executemany('INSERT INTO SFX_DOCUMENTS.M_STORAGE_TOTALS_OUTPUT VALUES (?,?,?)', rows)
        query = re.search(r'RESULTSET := \((.*?)\);\s*RETURN TABLE', routines['SFX_DOCUMENTS_M_STORAGE_TOTALS'][2], re.S)[1]
        query = re.sub(r':(P_START|P_END)', lambda m: window[m[1].lower()], render(query))
        after.execute('CREATE TABLE OPS.M_STORAGE_TOTALS_OUTPUT AS '+duck(sqlglot.parse_one(query, read='snowflake')))
    except (psycopg.Error, duckdb.Error, sqlglot.errors.SqlglotError) as error:
        failed['macro'] = 'macro measurement failed: '+str(error).splitlines()[0]

    def producer(table):
        for label, (start, end, body) in loads.items():
            if re.search(r'INSERT INTO \S+\.DOCUMENTS\.'+table+r'\b', body):
                return label, span(CONVERSION/'10_load.sql', start, end)
        return None, None

    ddl = {label: span(CONVERSION/'00_tables.sql', start, end) for label, start, end, _ in
           sections(CONVERSION/'00_tables.sql', r'^CREATE OR REPLACE TABLE \S+\.DOCUMENTS\.(\w+) \($')}
    for obj in by_name.values():
        name, kind = obj['name'], obj['kind']
        table = name.split('.')[-1]
        if obj['target_type'] == 'retire' or obj['system'] != 'teradata':
            continue
        entry = {'pairs': [], 'converted': [], 'reason': None}
        if kind == 'table':
            entry['pairs'] = [('SFX_DOCUMENTS.'+table, 'DOCUMENTS.'+table)]
            entry['converted'] = [ddl[table]]
            label = 'documents_'+table[4:].lower() if table.startswith('STG_') else producer(table)[0]
            entry['converted'].append(span(CONVERSION/'05_stage.sql', *stage[label][:2]) if table.startswith('STG_') else producer(table)[1])
            entry['reason'] = failed.get(label)
        elif kind == 'tpt':
            table = name.removeprefix('documents_').upper()
            entry['pairs'] = [('SFX_DOCUMENTS.STG_'+table, 'DOCUMENTS.STG_'+table)]
            entry['converted'] = [span(CONVERSION/'05_stage.sql', *stage[name][:2]), span('warehouse/snowflake/migrations/V003__loaders_and_tasks.sql', 48, 93)]
            entry['reason'] = failed.get(name)
        elif kind == 'bteq' and name in loads:
            entry['pairs'] = [(r, r.replace('SFX_DOCUMENTS.', 'DOCUMENTS.')) for r in obj['output_relations']]
            entry['converted'] = [span(CONVERSION/'10_load.sql', *loads[name][:2])]
            entry['reason'] = failed.get(name)
        elif kind == 'bteq':
            entry['pairs'] = [(r, r.removeprefix('SFX_')) for r in obj['output_relations']]+[('SFX_DOCUMENTS.M_STORAGE_TOTALS_OUTPUT', 'OPS.M_STORAGE_TOTALS_OUTPUT')]
            entry['converted'] = [span(CONVERSION/'20_routines.sql', *routines['10_STORAGE_MONTHLY'][:2]), span('migration/dw-exit/billing/15_storage.sql')]
            entry['reason'] = failed.get('macro')
        elif kind == 'macro':
            entry['pairs'] = [('SFX_DOCUMENTS.M_STORAGE_TOTALS_OUTPUT', 'OPS.M_STORAGE_TOTALS_OUTPUT')]
            entry['converted'] = [span(CONVERSION/'20_routines.sql', *routines['SFX_DOCUMENTS_M_STORAGE_TOTALS'][:2])]
            entry['reason'] = failed.get('macro')
        elif kind == 'view':
            entry['pairs'] = [('SFX_DOCUMENTS.'+table, 'COMPAT.SFX_DOCUMENTS__'+table)]
            entry['converted'] = [span(CONVERSION/'30_views.sql', *views[table][:2])]
            entry['reason'] = failed.get(table)
        results[obj['id']] = entry


def render_pc(name):
    text = (ROOT/'warehouse/dbt/models/pc/content'/('pc_content__'+name+'.sql')).read_text()
    text = re.sub(r'\{\{\s*config\(.*?\)\s*\}\}', '', text, flags=re.S)
    text = re.sub(r"\{\{\s*source\('pc_content_src',\s*'(\w+)'\)\s*\}\}", r'PC_SRC.\1', text)
    text = re.sub(r"\{\{\s*ref\('pc_content__(\w+)'\)\s*\}\}", lambda m: 'PC_CONTENT.'+m[1].upper(), text)
    if '{{' in text or '{%' in text:
        raise ValueError('Unsupported dbt template in pc_content__'+name)
    return sqlglot.parse_one(text, read='snowflake').sql(dialect='duckdb', comments=False)


def powercenter(before, after, business_date, results, by_name):
    """PowerCenter outputs come from the runner's own warehouse database, never the Teradata snapshot."""
    ns = os.environ.get('PC_NS', 'sfx1119_docs')
    dsn = os.environ.get('PC_SOURCE_DSN', f'host=127.0.0.1 port={55500+zlib.crc32(ns.encode())%1000} dbname=teradata user=postgres')
    reason, padded = None, set()
    try:
        before.execute('CREATE SCHEMA PC_BEFORE')
        with psycopg.connect(dsn, connect_timeout=5) as source, source.cursor() as cursor:
            for table in ('STG_DOCUMENT', 'DOCUMENT', 'DOC_SHARE'):
                cursor.execute('SELECT * FROM sfx_documents.'+table.lower())
                rows = cursor.fetchall()
                names = [c.name.upper() for c in cursor.description]
                padded.update(c.name.upper() for c in cursor.description if c.type_code == 1042)
                kinds = [{20:'BIGINT', 23:'INTEGER', 1082:'DATE', 1114:'TIMESTAMP'}.get(c.type_code, 'VARCHAR') for c in cursor.description]
                before.execute('CREATE TABLE PC_BEFORE.'+table+' ('+', '.join(quote(n)+' '+k for n, k in zip(names, kinds))+')')
                if rows:
                    before.executemany('INSERT INTO PC_BEFORE.'+table+' VALUES ('+','.join('?' for _ in names)+')', rows)
        landing = Path(os.environ.get('LANDING_DIR', ROOT/'warehouse/landing'))
        after.execute('CREATE SCHEMA PC_SRC')
        after.execute('CREATE SCHEMA PC_CONTENT')
        for area, table in (('users', 'APP_USER'), ('users', 'ROLE_GRANT'), ('documents', 'DOCUMENT'), ('documents', 'DOC_SHARE')):
            load_psv(after, 'PC_SRC.'+table, landing/area/table/(business_date+'.psv'), ddl_columns('SFX_'+area.upper()+'.STG_'+table))
        for name in PC_MODELS:
            after.execute('CREATE TABLE PC_CONTENT.'+name.upper()+' AS '+render_pc(name))
    except (psycopg.Error, duckdb.Error, ValueError, OSError, sqlglot.errors.SqlglotError) as error:
        reason = 'PowerCenter leg not measured: '+str(error).splitlines()[0]
    models = {'m_SFX_STG_DOCUMENT': 'stg_document', 'm_SFX_DOCUMENT': 'document', 'm_SFX_DOC_SHARE': 'doc_share'}
    for obj in by_name.values():
        if obj['system'] != 'powercenter':
            continue
        model = models[obj['name'].removeprefix('s_')]
        results[obj['id']] = {'pairs': [('PC_BEFORE.'+model.upper(), 'PC_CONTENT.'+model.upper())], 'reason': reason, 'padded': sorted(padded),
            'converted': [span('warehouse/dbt/models/pc/content/pc_content__'+model+'.sql')]}


def spark(before, after, objects, namespace, results):
    ready, errors, evidence = spark_billing.materialize(before, after, objects, namespace, area='documents')
    for obj in objects:
        if obj['system'] != 'spark' or obj['subject_area'] != 'documents':
            continue
        name = obj['name']
        target = 'SPARK.'+name.upper()
        paths = sorted((ROOT/'warehouse/dbt/models/spark'/name).glob('*.sql'))+[p for p in [ROOT/'warehouse/snowpark'/(name+'.py')] if p.is_file()]
        results[obj['id']] = {'pairs': [('SFX_SPARK.'+name.upper(), target)] if target in ready else [],
            'reason': errors.get(target), 'converted': [span(p.relative_to(ROOT)) for p in paths], 'evidence': evidence.get(name)}


def retirement(objects, results):
    """Query-log confirmation: any logged read of a retire object blocks the retirement."""
    usage = list(csv.DictReader((ROOT/'warehouse/teradata/dbql/objectusage.csv').open()))
    queries = {row['QueryID']: row for row in csv.DictReader((ROOT/'warehouse/teradata/dbql/qrylog.csv').open())}
    times = sorted(row['StartTime'] for row in queries.values())
    for obj in objects:
        if obj['subject_area'] != 'documents' or obj['target_type'] != 'retire':
            continue
        relations = {r.split('.')[-1] for r in obj['output_relations']} if obj['kind'] != 'tpt' else set()
        reads = [queries[row['QueryID']] for row in usage if row['ObjectDatabaseName'] == 'SFX_DOCUMENTS'
                 and row['ObjectTableName'] in relations and row['QueryID'] in queries]
        if obj['kind'] == 'tpt':
            reads = [q for q in queries.values() if obj['name'] in q['QueryText'] or q['AppID'] == 'TPT' and 'SEARCH_INDEX_LOG' in q['QueryText']]
        results[obj['id']] = {'pairs': [], 'converted': [], 'retire': {
            'query_log': 'warehouse/teradata/dbql/qrylog.csv + objectusage.csv', 'window': [times[0], times[-1]], 'reads': len(reads),
            'readers': [{k: q[k] for k in ('QueryID', 'UserName', 'ClientID', 'AppID', 'StartTime', 'QueryText')} for q in reads]},
            'reason': ('retirement blocked: '+str(len(reads))+' logged read(s) by '+', '.join(sorted({q['UserName'] for q in reads}))) if reads
                      else 'query log shows no reads; retirement awaits owner approval, object is not dropped'}


def materialize(before, after, objects, dsn, namespace, business_date):
    business_date = validate_date(business_date)
    mine = [obj for obj in objects if obj['subject_area'] == 'documents']
    by_name = {obj['id']: obj for obj in mine}
    results = {}
    teradata(before, after, dsn, business_date, results, by_name)
    powercenter(before, after, business_date, results, by_name)
    spark(before, after, objects, namespace, results)
    retirement(objects, results)
    for key, (text, names) in OWNER_DECISIONS.items():
        for obj in mine:
            if obj['name'] in names:
                results[obj['id']]['owner_decision'] = {'id': key, 'question': text}
    return results
