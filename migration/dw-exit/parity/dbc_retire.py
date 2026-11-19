"""Offline catalog retirement proof; ACCOUNT_USAGE population is an assumption, not live evidence."""
import csv
import ast
from collections import Counter
import os
import io
import re
import subprocess
import zlib
from pathlib import Path

import duckdb
import sqlglot
import psycopg

from parity.ladder import local_compare, canonical
from parity.provenance import link
from warehouse.run_config import RunConfig

ROOT = Path(__file__).resolve().parents[3]
DBQL = Path('warehouse/teradata/dbql')
SQL = Path('migration/dw-exit/dbc/10_account_usage.sql')
BEFORE = 'a48ea0e29c31ca5a5445e22074a99a0549d7d6b3'


def records(path, snapshot=False):
    text = subprocess.check_output(['git', 'show', f'{BEFORE}:{path}'], cwd=ROOT).decode() if snapshot else (ROOT/path).read_text()
    return list(csv.DictReader(io.StringIO(text)))


def reads(name, snapshot=False):
    queries = {r['QueryID']: r for r in records(DBQL/'qrylog.csv', snapshot)}
    return [queries[r['QueryID']] for r in records(DBQL/'objectusage.csv', snapshot)
            if r['ObjectDatabaseName']+'.'+r['ObjectTableName'] == name and r['UsageType']=='READ'
            and '2026-08-12' <= queries[r['QueryID']]['StartTime'][:10] <= '2026-11-09']


def callers():
    hits = []
    for folder in ('services', 'etl'):
        for path in sorted((ROOT/folder).rglob('*')):
            if path.is_file() and not any(p in path.parts for p in ('.data', 'node_modules', '.venv', '__pycache__')):
                try:
                    for number, line in enumerate(path.read_text().splitlines(), 1):
                        if re.search(r'\bDBC\s*\.', line, re.I):
                            hits.append({'file': str(path.relative_to(ROOT)), 'line': number, 'text': line})
                except (UnicodeError, OSError):
                    continue
    return hits


def evidence(obj, external):
    current, baseline = reads(obj['name']), reads(obj['name'], True)
    inventory = next(r for r in records(Path('migration/dw-exit/inventory.csv')) if r['name']==obj['name'])
    catalog = [r for r in records(DBQL/'tablesv.csv') if r['DatabaseName']+'.'+r['TableName']==obj['name']]
    setup = bool(current) and all(r['UserName']=='svc_report_recon' and r['StartTime'][:10]=='2026-08-12'
        and re.fullmatch(r'SELECT\s+COUNT\(\*\)\s+AS\s+ROW_COUNT\s+FROM\s+DBC\.(?:DBC_QRYLOG|DBC_QRYLOGOBJECTS|DBC_TABLESV|QRYLOGV|QRYLOGOBJECTSV|TABLESV);?', r['QueryText'], re.I) for r in current)
    return {'passed': bool(catalog) and obj['kind']=='catalog' and setup and not external
            and len(current)==len(baseline)==int(inventory['dbql_reads_90d'])
            and inventory['last_read']==max((r['StartTime'] for r in baseline), default=''),
            'catalog': catalog, 'window_reads': len(current), 'readers': sorted({r['UserName'] for r in current}),
            'dates': sorted({r['StartTime'][:10] for r in current}), 'queries': current,
            'inventory_reads': int(inventory['dbql_reads_90d']), 'inventory_last_read': inventory['last_read'],
            'before_state': BEFORE, 'before_queries': baseline,
            'last_read_matches_snapshot': inventory['last_read']==max((r['StartTime'] for r in baseline), default=''),
            'current_last_read': max((r['StartTime'] for r in current), default=''), 'external_callers': external}


def materialize():
    db = duckdb.connect()
    db.execute('CREATE SCHEMA DBC; CREATE SCHEMA COMPAT; CREATE SCHEMA ACCOUNT_USAGE')
    for filename, table in [('qrylog','DBC_QRYLOG'), ('objectusage','DBC_QRYLOGOBJECTS'), ('tablesv','DBC_TABLESV')]:
        db.execute(f"CREATE TABLE DBC.{table} AS SELECT * FROM read_csv_auto(?, sample_size=-1)", [str(ROOT/DBQL/(filename+'.csv'))])
    for view, table in [('QRYLOGV','DBC_QRYLOG'),('QRYLOGOBJECTSV','DBC_QRYLOGOBJECTS'),('TABLESV','DBC_TABLESV')]:
        db.execute(f'CREATE VIEW DBC.{view} AS SELECT * FROM DBC.{table}')
    db.execute('''CREATE TABLE ACCOUNT_USAGE.QUERY_HISTORY AS SELECT QueryID AS QUERY_ID,
        UserName AS USER_NAME, DefaultDatabase AS DATABASE_NAME, AppID AS QUERY_TAG,
        StartTime AS START_TIME, FirstRespTime AS END_TIME, StatementType AS QUERY_TYPE,
        QueryText AS QUERY_TEXT, NumResultRows AS ROWS_PRODUCED,
        CAST(NULLIF(ErrorCode,0) AS VARCHAR) AS ERROR_CODE FROM DBC.DBC_QRYLOG''')
    db.execute('''CREATE TABLE ACCOUNT_USAGE.ACCESS_HISTORY AS SELECT QueryID AS QUERY_ID,
        to_json(list(struct_pack(objectName := 'LEGACY.'||ObjectDatabaseName||'.'||ObjectTableName,
        objectDomain := CASE WHEN ObjectType='V' THEN 'View' ELSE 'Table' END))
        FILTER (WHERE UsageType='READ')) AS DIRECT_OBJECTS_ACCESSED,
        to_json(list(struct_pack(objectName := 'LEGACY.'||ObjectDatabaseName||'.'||ObjectTableName,
        objectDomain := CASE WHEN ObjectType='V' THEN 'View' ELSE 'Table' END))
        FILTER (WHERE UsageType='WRITE')) AS OBJECTS_MODIFIED
        FROM DBC.DBC_QRYLOGOBJECTS GROUP BY QueryID''')
    db.execute('''CREATE TABLE ACCOUNT_USAGE.TABLES AS SELECT DatabaseName AS TABLE_SCHEMA,
        TableName AS TABLE_NAME, CASE WHEN TableKind='V' THEN 'VIEW' ELSE 'BASE TABLE' END AS TABLE_TYPE,
        CreateTimeStamp AS CREATED, NULL AS DELETED FROM DBC.DBC_TABLESV WHERE TableKind IN ('T','V')''')
    shipped = re.sub(r'LATERAL FLATTEN\(INPUT => (h\.\w+)\) f', r'LATERAL json_each(\1) f', (ROOT/SQL).read_text())
    shipped = re.sub(r'f.value:(\w+)::VARCHAR', r"json_extract_string(f.value, '$.\1')", shipped)
    for statement in sqlglot.parse(shipped, read='snowflake'):
        for table in statement.find_all(sqlglot.exp.Table):
            table.set('catalog', None)
        db.execute(statement.sql(dialect='duckdb'))
    consumer = (ROOT/DBQL/'consumer_reads.bteq').read_text()
    old = re.search(r'SELECT\b.*?;', consumer, re.S)[0]
    db.execute('CREATE VIEW DBC.CONSUMER AS '+old)
    db.execute('CREATE VIEW COMPAT.CONSUMER AS '+(ROOT/'migration/dw-exit/dbc/20_consumer_reads.sql').read_text())
    return db


def emulator(db, name):
    ns = os.environ.get('NS', RunConfig.from_env().before_namespace)
    port = str(54500+zlib.crc32(ns.encode())%1000)
    dsn = os.environ.get('BOARD_SOURCE_DSN', f"host=127.0.0.1 port={os.environ.get('TD_PG_PORT', port)} dbname=teradata user=postgres connect_timeout=3")
    try:
        with psycopg.connect(dsn) as source:
            with source.cursor() as cursor:
                cursor.execute('SELECT * FROM '+name)
                values = cursor.fetchall()
                schema, table = name.split('.')
                cursor.execute('''SELECT q.username, q.starttime, q.querytext FROM dbc.qrylogobjectsv o
                    JOIN dbc.qrylogv q ON o.queryid=q.queryid
                    WHERE UPPER(o.objectdatabasename)=%s AND UPPER(o.objecttablename)=%s
                    AND o.usagetype='READ' AND q.starttime >= TIMESTAMP '2026-08-12'
                    AND q.starttime < TIMESTAMP '2026-11-10' ''', (schema, table))
                observed_reads = cursor.fetchall()
                cursor.execute('SELECT * FROM dbc.tablesv WHERE UPPER(databasename)=%s AND UPPER(tablename)=%s', (schema, table))
                catalog = cursor.fetchall()
        csv_values = db.execute('SELECT * FROM '+name).fetchall()
        return {'status': 'green' if Counter(map(canonical, values))==Counter(map(canonical, csv_values)) else 'red',
                'rows': len(values), 'csv_rows': len(csv_values), 'scope': 'full relation, including runtime tooling writes',
                'window_reads': len(observed_reads), 'read_evidence': observed_reads, 'catalog': catalog}
    except psycopg.Error as error:
        return {'status': 'red', 'reason': type(error).__name__}


def mapped_compare(db, family):
    if family=='CONSUMER':
        columns = ['UserName','AppID','READ_QUERIES','READS_PER_DAY']
        predicate = ''
        excluded = ['ClientID; this ladder projects existing groups, not a regrouped query']
    elif family in ('DBC_QRYLOG','QRYLOGV'):
        columns = ['QueryID','UserName','DefaultDatabase','AppID','StartTime','FirstRespTime','StatementType','QueryText','NumResultRows']
        predicate = ''
        excluded = ['ProcID','CollectTimeStamp','ClientID','StatementGroup','AMPCPUTime','TotalIOCount','ErrorCode']
    elif family in ('DBC_QRYLOGOBJECTS','QRYLOGOBJECTSV'):
        columns = ['QueryID','ObjectDatabaseName','ObjectTableName','ObjectType','UsageType']
        predicate = " WHERE UsageType IN ('READ','WRITE') AND ObjectType IN ('T','V')"
        excluded = ['EXECUTE usages and M/P kinds: no established equivalent']
    else:
        columns = ['DatabaseName','TableName','TableKind','CreateTimeStamp']
        predicate = " WHERE TableKind IN ('T','V')"
        excluded = ['AccessCount','LastAccessTimeStamp','M/P catalog rows']
    for schema in ('DBC','COMPAT'):
        db.execute(f'CREATE OR REPLACE VIEW {schema}.MAPPED AS SELECT '+','.join(columns)+f' FROM {schema}.{family}'+predicate)
    return {'label': 'target-equivalent columns only; explicit supported row scope, not full-shape parity',
            'columns': columns, 'row_scope': predicate or 'all rows', 'excluded_decisions': excluded,
            **local_compare(db, db, 'DBC.MAPPED', 'COMPAT.MAPPED')}


def measure(obj, db, external):
    proof = evidence(obj, external)
    comparison = local_compare(db, db, obj['name'], 'COMPAT.'+obj['name'].split('.')[1])
    family = obj['name'].split('.')[1]
    if family in ('DBC_TABLESV','TABLESV'):
        decision = {'old_behaviour': 'generate.py increments access for every usage (READ/WRITE/EXECUTE), and defaults never-accessed last timestamp to 2026-07-01 17:30:00',
                    'new_behaviour': 'read/write access aggregate; never-accessed timestamp NULL; TABLES lacks procedure/macro coverage',
                    'question': 'Approve read/write-only counts, NULL never-accessed timestamp and reduced catalog scope, or specify a replacement contract?'}
    elif family in ('DBC_QRYLOG','QRYLOGV'):
        decision = {'old_behaviour': 'DBQL preserves ProcID, collect timestamp, ClientID, CPU, IO and statement group',
                    'new_behaviour': 'ACCOUNT_USAGE has no equivalent fields; NULL for unavailable metrics, QUERY_TAG assumed AppID, END_TIME used for collect/first response',
                    'question': 'Which legacy fields may be dropped or redefined? Error code namespace equivalence also needs live validation.'}
    else:
        decision = {'old_behaviour': 'ObjectUsage includes READ, WRITE and EXECUTE and T/V/M/P kinds',
                    'new_behaviour': 'DIRECT_OBJECTS_ACCESSED reads plus OBJECTS_MODIFIED writes; EXECUTE and M/P attribution not established by these arrays or QUERY_HISTORY',
                    'question': 'Approve excluding legacy macro/procedure EXECUTE lineage, or supply an authoritative target attribution contract?'}
    return {**{k: comparison[k] for k in ('row_count','column_profile','keyed_row_hash','sampled_differences')},
            'status': 'green' if proof['passed'] and comparison['passed'] else 'red',
            'reason': None if proof['passed'] and comparison['passed'] else ('Owner decision: '+decision['question'] if proof['passed'] else 'Retirement evidence failed; '+decision['question']),
            'local_duckdb': 'green' if proof['passed'] and comparison['passed'] else 'red',
            'snowflake': 'red', 'snowflake_reason': 'Role lacks grant; live ACCOUNT_USAGE unverified; no connection attempted',
            'retire_evidence': proof, 'owner_decision': decision,
            'mapped_columns_parity': mapped_compare(db, family),
            'full_shape_mismatched_columns': [c for c,p in comparison['column_profile']['before'].items()
                                              if canonical(p)!=canonical(comparison['column_profile']['after'][c])],
            'emulator': emulator(db, obj['name']),
            'consumer_parity': local_compare(db, db, 'DBC.CONSUMER', 'COMPAT.CONSUMER'),
            'consumer_mapped_columns_parity': mapped_compare(db, 'CONSUMER'),
            'emulation_assumption': 'QUERY_HISTORY, ACCESS_HISTORY and TABLES synthesized from identical DBQL CSVs, not Snowflake data; QUERY_TAG=AppID assumed'}


def markdown(rows):
    def anchor(path, start=1, end=None):
        entry = link(path, start, end)
        url = entry['url'].replace('devin/sfx1119-billing-parity/', 'devin/sfx1119-dbc-parity/')
        return f"[{path}:{entry['start_line']}–{entry['end_line']}]({url})"
    def function(path, name):
        node = next(n for n in ast.parse((ROOT/path).read_text()).body if isinstance(n, ast.FunctionDef) and n.name==name)
        return anchor(path, node.lineno, node.end_lineno)
    def statement(path, name):
        text = (ROOT/path).read_text()
        match = re.search(r'CREATE (?:OR REPLACE )?(?:MULTISET TABLE|VIEW) '+re.escape(name)+r'\b.*?;', text, re.S | re.I)
        return anchor(path, text.count('\n',0,match.start())+1, text.count('\n',0,match.end())+1)
    code = Path('migration/dw-exit/parity/dbc_retire.py')
    ladder = Path('migration/dw-exit/parity/ladder.py')
    metrics = function(ladder, 'local_compare')+'<br>'+function(ladder, 'local_measure')
    details = []
    lines = ['\n## DBC parity provenance', '',
             'Local ACCOUNT_USAGE shapes are assumed from identical DBQL CSVs; live ACCOUNT_USAGE is unverified (role lacks grant; no connection attempted). Retirement requires owner sign-off.',
             'Mapped-columns ladders exclude the named decision columns **and explicitly labelled unsupported row kinds**; their green result is not full-shape parity.', '',
             '| Object | local_duckdb / snowflake | Full rows old/new; hash delta | Mapped rows old/new; hash delta | Retirement reads | Exact source / replacement / evidence / ladder |',
             '|---|---|---|---|---|---|']
    for row in rows:
        if row['subject_area']!='dbc':
            continue
        counts, mapped = row['row_count'], row['mapped_columns_parity']
        family = row['name'].split('.')[1]
        base = {'QRYLOGV':'DBC_QRYLOG','QRYLOGOBJECTSV':'DBC_QRYLOGOBJECTS','TABLESV':'DBC_TABLESV'}.get(family, family)
        filename = {'DBC_QRYLOG':'qrylog.csv','DBC_QRYLOGOBJECTS':'objectusage.csv','DBC_TABLESV':'tablesv.csv'}[base]
        sources = [anchor(DBQL/filename, 2), statement(DBQL/'schema.sql', row['name']), statement(SQL, 'COMPAT.'+family)]
        if base!=family:
            sources += [statement(DBQL/'schema.sql', 'DBC.'+base), statement(SQL, 'COMPAT.'+base)]
        table_lines = (ROOT/DBQL/'tablesv.csv').read_text().splitlines()
        number = next(i for i,line in enumerate(table_lines,1) if line.startswith(row['name'].replace('.',',')+','))
        sources += [anchor(DBQL/'tablesv.csv', number, number), function(code,'materialize'), function(code,'evidence'), function(code,'reads'), function(code,'mapped_compare'), function(code,'measure'), metrics]
        inventory = Path('migration/dw-exit/inventory.csv')
        reader = csv.DictReader(io.StringIO((ROOT/inventory).read_text()))
        for item in reader:
            if item['name']==row['name']:
                sources.append(anchor(inventory,reader.line_num,reader.line_num))
        query_ids = {q['QueryID'] for q in row['retire_evidence']['queries']}
        reader = csv.DictReader(io.StringIO((ROOT/DBQL/'qrylog.csv').read_text()))
        for query in reader:
            if query['QueryID'] in query_ids:
                sources.append(anchor(DBQL/'qrylog.csv',reader.line_num,reader.line_num))
        full_text = f"{counts['before']}/{counts['after']}; {row['keyed_row_hash']['difference']}"
        mapped_text = f"{mapped['row_count']['before']}/{mapped['row_count']['after']}; {mapped['keyed_row_hash']['difference']}"
        lines.append(f"| {row['name']} | {row['local_duckdb']} / red | {full_text} | {mapped_text} | {row['retire_evidence']['window_reads']} | {'<br>'.join(sources)} |")
        details += ['', '### '+row['name'], '', row['reason'] or 'Full parity passed.',
                  'Mapped scope: `'+mapped['row_scope']+'`; columns: `'+', '.join(mapped['columns'])+'`.',
                  'Excluded decisions: '+', '.join(mapped['excluded_decisions'])+'.', '']
    lines += details
    lines += ['Consumer query: '+anchor(DBQL/'consumer_reads.bteq',4,11)+' → '+anchor(Path('migration/dw-exit/dbc/20_consumer_reads.sql'))+'; '+metrics+'.',
              'Known TablesV generator semantics: '+anchor(DBQL/'generate.py',202,210)+'.']
    return '\n'.join(lines)+'\n'
