"""Compare frozen pre-PC SQL state and actual post-PC runner output locally."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT/'migration/dw-exit'), str(ROOT/'migration/dw-exit/tools'), str(ROOT/'warehouse/teradata')]

import duckdb
import psycopg
import yaml

from bteq import Runner
from parity.ladder import identifier, local_compare
from parity.local_billing import statements
from parity.local_documents import CONVERSIONS, compare, execute, load_landing, merge_pc, render_pc, resultset
from parity.object_board import source_snapshot
from warehouse.run_config import RunConfig


def copy_table(source, destination, old, new):
    columns = source.execute('DESCRIBE '+old).fetchall()
    destination.execute('CREATE TABLE '+new+' ('+', '.join(identifier(c[0])+' '+c[1] for c in columns)+')')
    rows = source.execute('SELECT * FROM '+old).fetchall()
    if rows:
        destination.executemany('INSERT INTO '+new+' VALUES ('+','.join('?' for _ in columns)+')', rows)


def measure_pc(pre, actual, landing, day):
    after = duckdb.connect()
    results = {}
    try:
        after.execute('CREATE SCHEMA PC_CONTENT')
        after.execute('CREATE SCHEMA PC_SRC')
        for name in ('STG_DOCUMENT','DOCUMENT','DOC_SHARE'):
            copy_table(pre, after, 'SFX_DOCUMENTS.'+name, 'PC_CONTENT.'+name)
        for name in ('APP_USER','ROLE_GRANT'):
            copy_table(pre, after, 'SFX_USERS.'+name, 'PC_CONTENT.'+name)
        copy_table(pre, after, 'SFX_USERS.ROLE_GRANT', 'PC_SRC.ROLE_GRANT')
        for name in ('DOCUMENT','DOC_SHARE'):
            columns = pre.execute('DESCRIBE SFX_DOCUMENTS.STG_'+name).fetchall()
            after.read_csv(str(landing/'documents'/name/(day+'.psv')), delimiter='|', header=False,
                           columns={c[0]:'VARCHAR' for c in columns}, na_values='', quotechar='"').create('PC_SRC.'+name)
        for name,key in (('STG_DOCUMENT','DOCUMENT_ID'),('DOCUMENT','DOCUMENT_ID'),('DOC_SHARE','SHARE_ID')):
            path = ROOT/'warehouse/dbt/models/pc/content'/('pc_content__'+name.lower()+'.sql')
            merge_pc(after, name, render_pc(path), key)
            measured = local_compare(actual, after, 'SFX_DOCUMENTS.'+name, 'PC_CONTENT.'+name, sample_size=10000)
            measured['candidate'] = str(path.relative_to(ROOT))
            results[name] = measured
        return results
    finally:
        after.close()


def shared_storage(pre, day, snapshot_storage=False):
    before, after = duckdb.connect(), duckdb.connect()
    try:
        before.execute('CREATE SCHEMA SFX_BILLING')
        after.execute('CREATE SCHEMA BILLING')
        for name in ('USAGE_DAILY','INVOICE_LINE','SUBSCRIPTION','INVOICE_HDR'):
            copy_table(pre, after, 'SFX_BILLING.'+name, 'BILLING.'+name)
        old = 'SFX_DOCUMENTS.STG_STORAGE_USAGE_DAILY' if snapshot_storage else 'SFX_DOCUMENTS.STORAGE_USAGE_DAILY'
        copy_table(pre, after, old, 'BILLING.STORAGE_USAGE_INPUT')
        for statement in statements(ROOT/'migration/dw-exit/billing/15_storage.sql',day):
            after.execute(statement.sql(dialect='duckdb'))
        connection = psycopg.connect('host=127.0.0.1 port=54722 dbname=teradata user=postgres')
        with Runner(connection=connection, output=io.StringIO()) as runner:
            import calendar
            import datetime
            date = datetime.datetime.strptime(day,'%Y%m%d').date()
            first = date.replace(day=1)
            end = first+datetime.timedelta(days=calendar.monthrange(first.year,first.month)[1])
            runner.variables.update(BUSINESS_DATE=day, MONTH_START=first.strftime('%Y%m%d'), MONTH_END=end.strftime('%Y%m%d'))
            connection.execute('BEGIN')
            try:
                script = (ROOT/'warehouse/teradata/scripts/documents/10_storage_monthly.bteq').read_text()
                script = '\n'.join(line for line in script.splitlines() if not line.startswith('.EXPORT'))
                if runner.run(script) != 0:
                    raise ValueError('Legacy storage boundary replay failed')
                for name in ('USAGE_DAILY','INVOICE_LINE'):
                    columns = pre.execute('DESCRIBE SFX_BILLING.'+name).fetchall()
                    before.execute('CREATE TABLE SFX_BILLING.'+name+' ('+', '.join(identifier(c[0])+' '+c[1] for c in columns)+')')
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


def prove(pre_path, landing, namespace, day):
    config = RunConfig.from_env()
    if config.token != 'sfx1119' or namespace != config.before_namespace:
        raise ValueError('Documents proof is restricted to sfx1119 before namespace')
    pre = duckdb.connect()
    after = duckdb.connect()
    actual = None
    try:
        pre.execute("IMPORT DATABASE '"+str(pre_path.resolve()).replace("'","''")+"'")
        ready, errors = execute(after, pre, business_date=day)
        if errors:
            raise ValueError(errors)
        resultset(pre, after, day)
        contract = json.loads((CONVERSIONS.parent/'parity/documents.json').read_text())
        sql_results = compare(pre, after, [c for c in contract if '.DOCUMENTS.' in c['after']])
        load_landing(after, landing, day)
        tpt_results = {c['name']:local_compare(pre,after,'SFX_DOCUMENTS.'+c['name'],'DOCUMENTS.'+c['name'],sample_size=10000)
                       for c in contract if c['name'].startswith('STG_')}
        actual, _, errors = source_snapshot('host=127.0.0.1 port=54722 dbname=teradata user=postgres',
                                            {'SFX_DOCUMENTS.'+n for n in ('STG_DOCUMENT','DOCUMENT','DOC_SHARE')})
        if errors:
            raise ValueError(errors)
        pc_results = measure_pc(pre, actual, landing, day)
        boundary = shared_storage(pre,day)
        downstream = shared_storage(pre,day,snapshot_storage=True)
        decisions = json.loads((CONVERSIONS/'decisions.json').read_text())
        blocked = {r for d in decisions for r in d['blocks']}
        manifest = yaml.safe_load((CONVERSIONS.parent/'manifest.yaml').read_text())
        object_rows = []
        for obj in manifest['objects']:
            if obj['subject_area'] != 'documents' or obj['system'] == 'spark':
                continue
            if obj['target_type'] == 'retire':
                continue
            if obj['system'] == 'powercenter':
                name = obj['name'].removeprefix('s_').removeprefix('m_SFX_')
                measured = {name:pc_results[name]}
                blockers = [d['object'] for d in decisions if 'powercenter.'+obj['name'] in d['blocks']]
            else:
                outputs = obj['output_relations'] or ['SFX_DOCUMENTS.M_STORAGE_TOTALS_OUTPUT']
                measured = {r.split('.')[-1]:sql_results[r.split('.')[-1]] for r in outputs if r.startswith('SFX_DOCUMENTS.')}
                if obj['kind'] == 'tpt':
                    measured = {r.split('.')[-1]:tpt_results[r.split('.')[-1]] for r in outputs}
                blockers = sorted(set(outputs)&blocked)
                if obj['name'] == '10_storage_monthly':
                    measured = downstream
                    blockers += ['Shared billing/15_storage.sql; upstream SET decision pending; see boundary proof']
            object_rows.append({k:obj[k] for k in ('name','target','target_type')} | {
                'status':'green' if measured and not blockers and all(v['passed'] for v in measured.values()) else 'red',
                'relations':{k:{'row_count':v['row_count'],'hash_delta':v['keyed_row_hash']['difference']} for k,v in measured.items()},
                'blockers':blockers})
        return {'run_token':config.token, 'namespace':namespace, 'business_date':day,
                'target':'duckdb', 'snowflake':'not attempted',
                'source':'frozen post-BTEQ/pre-PC snapshot; actual post-PC PostgreSQL outputs',
                'landing_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(landing.rglob(day+'.psv'))},
                'pc_logs_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted((ROOT/'etl/informatica/infa_shared'/namespace/'SessLogs').glob('s_m_SFX_*DOCUMENT.log'))+sorted((ROOT/'etl/informatica/infa_shared'/namespace/'SessLogs').glob('s_m_SFX_DOC_SHARE.log'))},
                'sql_relations':sql_results, 'tpt_relations':tpt_results, 'pc_relations':pc_results, 'objects':object_rows,
                'shared_billing_boundary':boundary, 'shared_billing_with_candidate_storage':downstream,
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
    parser.add_argument('--namespace',default='sfx-1119-before')
    parser.add_argument('--business-date',default='20261109')
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    payload = prove(args.pre_pc,args.landing,args.namespace,args.business_date)
    args.output.write_text(json.dumps(payload,indent=2,default=str)+'\n')
    for leg in ('sql_relations','pc_relations'):
        for name,result in payload[leg].items():
            print(leg,name,'green' if result['passed'] else 'red',result['row_count'],'hash_delta='+str(result['keyed_row_hash']['difference']))
    print('Object status:',{s:sum(o['status']==s for o in payload['objects']) for s in ('green','red')})


if __name__ == '__main__':
    main()
