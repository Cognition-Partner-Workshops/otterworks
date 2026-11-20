"""Compare frozen pre-PC SQL state and actual post-PC runner output locally."""
import argparse
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import zlib

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT/'migration/dw-exit'), str(ROOT/'migration/dw-exit/tools'), str(ROOT/'warehouse/teradata')]

import duckdb
import psycopg
import yaml

from bteq import Runner
from parity.ladder import identifier, local_compare
from parity.local_billing import lower_statements
from parity.local_documents import CONVERSIONS, compare, execute, load_landing, merge_pc, render_pc, resultset, storage_statements
from parity.object_board import source_snapshot, relation_contract
from parity.documents_decisions import version_scope
from warehouse.run_config import RunConfig
from warehouse.snowpark import m_sfx_doc_share, m_sfx_document


def source_dsn(namespace):
    if namespace != RunConfig.from_env().before_namespace:
        raise ValueError('Documents proof requires the run-scoped before namespace')
    port = 54500 + zlib.crc32(namespace.encode()) % 1000
    return f'host=127.0.0.1 port={port} dbname=teradata user=postgres'


def snapshot(output, namespace):
    contract = json.loads((CONVERSIONS.parent/'parity/documents.json').read_text())
    names = {'SFX_DOCUMENTS.'+c['name'] for c in contract
             if '.DOCUMENTS.' in c['after'] and c['name'] != 'M_STORAGE_TOTALS_OUTPUT'}
    names.update(('SFX_USERS.APP_USER', 'SFX_USERS.ROLE_GRANT', 'SFX_BILLING.USAGE_DAILY',
                  'SFX_BILLING.INVOICE_LINE', 'SFX_BILLING.SUBSCRIPTION', 'SFX_BILLING.INVOICE_HDR'))
    connection, ready, errors = source_snapshot(source_dsn(namespace), names)
    with connection:
        if ready != names or errors:
            raise ValueError(errors)
        if output.exists():
            raise FileExistsError(f'Refusing to overwrite frozen source snapshot: {output}')
        # Operator-selected local path; SQL string quotes escaped.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        connection.execute("EXPORT DATABASE '"+str(output.resolve()).replace("'","''")+"'")


def copy_table(source, destination, old, new):
    # Callers supply fixed table names; types are local DuckDB snapshot metadata.
    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
    columns = source.execute('DESCRIBE '+old).fetchall()
    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
    destination.execute('CREATE TABLE '+new+' ('+', '.join(identifier(c[0])+' '+c[1] for c in columns)+')')
    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
    rows = source.execute('SELECT * FROM '+old).fetchall()
    if rows:
        destination.executemany('INSERT INTO '+new+' VALUES ('+','.join('?' for _ in columns)+')', rows)


def measure_pc(pre, actual, landing, day):
    after = duckdb.connect()
    results = {}
    try:
        after.execute('CREATE SCHEMA PC_CONTENT')
        after.execute('CREATE SCHEMA PC_SRC')
        after.execute('CREATE SCHEMA USERS')
        after.execute('CREATE SCHEMA DOCUMENTS')
        for name in ('STG_DOCUMENT','DOCUMENT','DOC_SHARE'):
            copy_table(pre, after, 'SFX_DOCUMENTS.'+name, 'PC_CONTENT.'+name)
            copy_table(pre, after, 'SFX_DOCUMENTS.'+name, 'DOCUMENTS.'+name)
        for name in ('APP_USER','ROLE_GRANT'):
            copy_table(pre, after, 'SFX_USERS.'+name, 'USERS.'+name)
        for name in ('DOCUMENT','DOC_SHARE'):
            # name is restricted to the fixed tuple above.
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            columns = pre.execute('DESCRIBE SFX_DOCUMENTS.STG_'+name).fetchall()
            after.read_csv(str(landing/'documents'/name/(day+'.psv')), delimiter='|', header=False,
                           columns={c[0]:'VARCHAR' for c in columns}, na_values='', quotechar='"').create('PC_SRC.'+name)
        for name,key in (('STG_DOCUMENT','DOCUMENT_ID'),('DOCUMENT','DOCUMENT_ID'),('DOC_SHARE','SHARE_ID')):
            path = ROOT/'warehouse/dbt/models/pc/content'/('pc_content__'+name.lower()+'.sql')
            merge_pc(after, name, render_pc(path), key)
            measured = local_compare(actual, after, 'SFX_DOCUMENTS.'+name, 'PC_CONTENT.'+name, sample_size=10000)
            measured['candidate'] = str(path.relative_to(ROOT))
            results[name] = measured

        class LocalSnowpark:
            def get_current_database(self):
                return RunConfig.from_env().database

            def sql(self, query):
                self.statement = next(lower_statements(query))
                return self

            def collect(self):
                return after.execute(self.statement.sql(dialect='duckdb')).fetchall()

        publishers = {'DOCUMENT':m_sfx_document, 'DOC_SHARE':m_sfx_doc_share}
        publisher_results = {}
        for name, module in publishers.items():
            module.run(LocalSnowpark())
            publisher_results[name] = local_compare(actual,after,'SFX_DOCUMENTS.'+name,'DOCUMENTS.'+name,sample_size=10000)
            # Restore the pre-session target before the independent procedure replay.
            table = identifier(name)
            # Table names are from the fixed publisher mapping; initial rows are bound by copy_table.
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            after.execute('DROP TABLE DOCUMENTS.'+table)
            copy_table(pre, after, 'SFX_DOCUMENTS.'+name, 'DOCUMENTS.'+name)
        session_results = {}
        session_sql = (CONVERSIONS/'52_sessions.sql').read_text()
        model_dir = ROOT/'warehouse/dbt/models/documents'
        for name,prefix in (('STG_DOCUMENT','stg'),('DOCUMENT','core'),('DOC_SHARE','core')):
            model = model_dir/f'{prefix}_documents__s_m_sfx_{name.lower()}.sql'
            # Query comes from the parsed repository model, not fixture data.
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            after.execute('CREATE OR REPLACE VIEW PC_CONTENT.DBT_SESSION AS '+render_pc(model))
            model_result = local_compare(actual,after,'SFX_DOCUMENTS.'+name,'PC_CONTENT.DBT_SESSION',sample_size=10000)
            procedure = f'{prefix.upper()}_DOCUMENTS__S_M_SFX_{name}'
            body = re.search(r'\.'+procedure+r'\(\).*?\$\$\s*BEGIN\s*(.*?)\s*RETURN ',session_sql,re.S)
            if not body:
                raise ValueError(f'Missing procedure body: {procedure}')
            for statement in lower_statements(body[1]):
                after.execute(statement.sql(dialect='duckdb'))
            procedure_result = local_compare(actual,after,'SFX_DOCUMENTS.'+name,'DOCUMENTS.'+name,sample_size=10000)
            session_results[name] = model_result | {'procedure':procedure_result,'passed':model_result['passed'] and procedure_result['passed']}
        staging_mapping = model_dir/'stg_documents__m_sfx_stg_document.sql'
        # Parsed repository model.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        after.execute('CREATE OR REPLACE VIEW PC_CONTENT.DBT_MAPPING AS '+render_pc(staging_mapping))
        publisher_results['STG_DOCUMENT'] = local_compare(
            actual,after,'SFX_DOCUMENTS.STG_DOCUMENT','PC_CONTENT.DBT_MAPPING',sample_size=10000)
        return results,publisher_results,session_results
    finally:
        after.close()


def shared_storage(pre, converted, day, namespace):
    before, after = duckdb.connect(), duckdb.connect()
    try:
        before.execute('CREATE SCHEMA SFX_BILLING')
        after.execute('CREATE SCHEMA BILLING')
        for name in ('USAGE_DAILY','INVOICE_LINE','SUBSCRIPTION','INVOICE_HDR'):
            copy_table(pre, after, 'SFX_BILLING.'+name, 'BILLING.'+name)
        after.execute('CREATE SCHEMA DOCUMENTS')
        copy_table(converted, after, 'DOCUMENTS.STORAGE_USAGE_DAILY', 'DOCUMENTS.STORAGE_USAGE_DAILY')
        for statement in storage_statements(day):
            after.execute(statement.sql(dialect='duckdb'))
        connection = psycopg.connect(source_dsn(namespace))
        with Runner(connection=connection, output=io.StringIO()) as runner:
            first = date(int(day[:4]), int(day[4:6]), 1)
            end = date(first.year+int(first.month==12), first.month%12+1, 1)
            runner.variables.update(BUSINESS_DATE=day, MONTH_START=first.strftime('%Y%m%d'), MONTH_END=end.strftime('%Y%m%d'))
            connection.execute('BEGIN')
            try:
                script = (ROOT/'warehouse/teradata/scripts/documents/10_storage_monthly.bteq').read_text()
                script = '\n'.join(line for line in script.splitlines() if not line.startswith('.EXPORT'))
                if runner.run(script) != 0:
                    raise ValueError('Legacy storage boundary replay failed')
                for name in ('USAGE_DAILY','INVOICE_LINE'):
                    # Fixed table names, quoted columns and DuckDB metadata types; rows are bound below.
                    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                    columns = pre.execute('DESCRIBE SFX_BILLING.'+name).fetchall()
                    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                    before.execute('CREATE TABLE SFX_BILLING.'+name+' ('+', '.join(identifier(c[0])+' '+c[1] for c in columns)+')')
                    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                    rows = connection.execute('SELECT * FROM SFX_BILLING.'+name).fetchall()
                    if rows:
                        before.executemany('INSERT INTO SFX_BILLING.'+name+' VALUES ('+','.join('?' for _ in columns)+')',rows)
            finally:
                connection.execute('ROLLBACK')
        return {name:local_compare(before,after,'SFX_BILLING.'+name,'BILLING.'+name,sample_size=10000)
                for name in ('USAGE_DAILY','INVOICE_LINE')}
    finally:
        before.close()
        after.close()


def prove(pre_path, landing, namespace, day, objects=None):
    config = RunConfig.from_env()
    dsn = source_dsn(namespace)
    logs = ROOT/'etl/informatica/infa_shared'/namespace/'SessLogs'
    session_logs = [logs/f's_m_SFX_{name}.log' for name in ('STG_DOCUMENT','DOCUMENT','DOC_SHARE')]
    if not all(log.is_file() and log.stat().st_mtime_ns >= (pre_path/'schema.sql').stat().st_mtime_ns
               for log in session_logs):
        raise ValueError('Missing or out-of-order PowerCenter logs; rerun after freezing the before snapshot')
    pre = duckdb.connect()
    after = duckdb.connect()
    actual = None
    try:
        # Local operator-supplied snapshot path; embedded SQL quotes are escaped.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        pre.execute("IMPORT DATABASE '"+str(pre_path.resolve()).replace("'","''")+"'")
        ready, errors = execute(after, pre, business_date=day)
        if errors:
            raise ValueError(errors)
        resultset(pre, after, day)
        contract = json.loads((CONVERSIONS.parent/'parity/documents.json').read_text())
        sql_results = compare(pre, after, [c for c in contract if '.DOCUMENTS.' in c['after']])
        version_scope(pre, after, sql_results)
        load_landing(after, landing, day)
        tpt_results = {c['name']:local_compare(pre,after,'SFX_DOCUMENTS.'+c['name'],'DOCUMENTS.'+c['name'],sample_size=10000)
                       for c in contract if c['name'].startswith('STG_')}
        actual, _, errors = source_snapshot(dsn,
                                            {'SFX_DOCUMENTS.'+n for n in ('STG_DOCUMENT','DOCUMENT','DOC_SHARE')})
        if errors:
            raise ValueError(errors)
        pc_results,pc_mappings,pc_sessions = measure_pc(pre, actual, landing, day)
        boundary = shared_storage(pre,after,day,namespace)
        decisions = json.loads((CONVERSIONS/'decisions.json').read_text())
        pending = [d for d in decisions if d.get('status') != 'approved']
        blocked = {r for d in pending if d.get('status') != 'approved-pending-confirmation' for r in d['blocks']}
        manifest = yaml.safe_load((CONVERSIONS.parent/'manifest.yaml').read_text())
        object_rows = []
        for obj in (objects if objects is not None else relation_contract(manifest['objects'])):
            if obj['subject_area'] != 'documents' or obj['system'] == 'spark':
                continue
            if obj['target_type'] == 'retire':
                continue
            if obj['system'] == 'powercenter':
                name = obj['name'].removeprefix('s_').removeprefix('m_SFX_')
                route = pc_sessions if obj['kind']=='session' else pc_mappings
                measured = {name:route[name]}
                blockers = [d['object'] for d in pending if 'powercenter.'+obj['name'] in d['blocks']]
            else:
                outputs = obj['output_relations'] or ['SFX_DOCUMENTS.M_STORAGE_TOTALS_OUTPUT']
                measured = {r.split('.')[-1]:sql_results[r.split('.')[-1]] for r in outputs if r.startswith('SFX_DOCUMENTS.')}
                if obj['kind'] == 'tpt':
                    measured = {r.split('.')[-1]:tpt_results[r.split('.')[-1]] for r in outputs}
                blockers = sorted(set(outputs)&blocked)
                if obj['name'] == '10_storage_monthly':
                    measured = boundary
            object_rows.append({k:obj[k] for k in ('name','target','target_type')} | {
                'status':'green' if measured and not blockers and all(v['passed'] for v in measured.values()) else 'red',
                'relations':{k:{'row_count':v['row_count'],'hash_delta':v['keyed_row_hash']['difference']} for k,v in measured.items()},
                'blockers':blockers})
        return {'run_token':config.token, 'namespace':namespace, 'business_date':day,
                'target':'duckdb', 'snowflake':'red', 'snowflake_reason':'Login unavailable; not attempted.',
                'source':'frozen post-BTEQ/pre-PC snapshot; actual post-PC PostgreSQL outputs',
                'landing_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(landing.rglob(day+'.psv'))},
                'pc_logs_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in session_logs},
                'sql_relations':sql_results, 'tpt_relations':tpt_results, 'pc_relations':pc_results,
                'pc_mappings':pc_mappings, 'pc_sessions':pc_sessions, 'objects':object_rows,
                'shared_billing_boundary':boundary,
                'decisions':decisions}
    finally:
        pre.close()
        after.close()
        if actual is not None:
            actual.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pre-pc',type=Path,required=True)
    parser.add_argument('--landing',type=Path,default=ROOT/'warehouse/landing')
    parser.add_argument('--namespace',default=RunConfig.from_env().before_namespace)
    parser.add_argument('--business-date',default='20261109')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--capture-pre-pc',action='store_true')
    args = parser.parse_args()
    if args.capture_pre_pc:
        snapshot(args.pre_pc, args.namespace)
        return
    if args.output is None:
        parser.error('--output is required unless capturing the before snapshot')
    payload = prove(args.pre_pc,args.landing,args.namespace,args.business_date)
    args.output.write_text(json.dumps(payload,indent=2,default=str)+'\n')
    for leg in ('sql_relations','pc_relations'):
        for name,result in payload[leg].items():
            print(leg,name,'green' if result['passed'] else 'red',result['row_count'],'hash_delta='+str(result['keyed_row_hash']['difference']))
    print('Object status:',{s:sum(o['status']==s for o in payload['objects']) for s in ('green','red')})


if __name__ == '__main__':
    main()
