"""Local proof of manifest-assigned documents Spark outputs, including AUDIT input."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import subprocess

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT),str(ROOT/'migration/dw-exit')]

import duckdb
import sqlglot
import yaml

from parity.ladder import identifier, local_compare
from parity.spark_billing import schemas, uppercase_columns
from warehouse.run_config import RunConfig

DOCUMENTS = ROOT/'migration/dw-exit/documents'
UDFS = ROOT/'warehouse/dbt/macros/documents_spark_udfs.sql'


def path_name(path):
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def checksums(paths):
    return {path_name(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(set(paths))}


def shipped_udfs(path=UDFS):
    text = path.read_text().replace('{% raw %}', '').replace('{% endraw %}', '')
    pattern = r'FUNCTION (\w+)\((.*?)\)\s*RETURNS (\w+).*?HANDLER = \'(\w+)\'.*?AS \$\$(.*?)\$\$;'
    functions = {}
    for name, arguments, result, handler, body in re.findall(pattern,text,re.S):
        scope = {'__name__':__name__}
        exec(compile(body,str(path),'exec'),scope)
        functions[name] = {'arguments':[a.strip().split()[-1] for a in arguments.split(',')],
                           'result':result, 'handler':scope[handler], 'body':body}
    if len(functions) != 4:
        raise ValueError('Expected four shipped documents Python UDF bodies')
    return functions


def register_udfs(connection):
    def json_handler(implementation):
        def call(content):
            return json.dumps(implementation(content))
        return call
    for name, function in shipped_udfs().items():
        handler = function['handler']
        result = function['result']
        if result == 'VARIANT':
            handler = json_handler(handler)
            result = 'JSON'
        connection.create_function(name,handler,
            ['BLOB' if t=='BINARY' else t for t in function['arguments']],
            duckdb.sqltype('DOUBLE' if result=='FLOAT' else result), null_handling='special')


def render_model(path, run_date=None):
    text = re.sub(r'^\{\{\s*config\(.*\)\s*\}\}\s*$', '', path.read_text(), flags=re.M)
    text = re.sub(r"\{\{\s*source\('spark_(?:documents|users|audit|documents_binary)',\s*'(\w+)'\)\s*\}\}", r'SPARK_INPUT.\1',text)
    text = re.sub(r"\{\{\s*ref\('(\w+)'\)\s*\}\}", lambda m:'SPARK.'+identifier('spark__'+m[1]),text)
    if run_date is not None:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',run_date):
            raise ValueError('Invalid binary partition date')
        text = text.replace('{{ documents_spark_run_date() }}',run_date)
    if '{{' in text or '{%' in text:
        raise ValueError('Unsupported documents Spark dbt template')
    return sqlglot.parse_one(text,read='snowflake').sql(dialect='duckdb')


def execute_model(connection, job, day=None, incremental=False):
    target = 'SPARK.'+identifier(job['target'])
    query = render_model(ROOT/job['model'],day)
    if incremental:
        body = UDFS.read_text().split('{% macro documents_spark_replace_partition() %}',1)[1].split('{% endmacro %}',1)[0]
        hook = body.split('{% if is_incremental() %}',1)[1].split('{% else %}',1)[0]
        hook = hook.replace('{{ this }}',target).replace('{{ documents_spark_run_date() }}',day)
        connection.execute('BEGIN')
        try:
            connection.execute(sqlglot.parse_one(hook,read='snowflake').sql(dialect='duckdb'))
            connection.execute('INSERT INTO '+target+' '+query)
            connection.execute('COMMIT')
        except Exception:
            connection.execute('ROLLBACK')
            raise
    else:
        connection.execute('CREATE TABLE '+target+' AS '+query)
    return query


def jdbc_output(before, after, namespace):
    if namespace != RunConfig.from_env().before_namespace:
        raise ValueError('Unexpected JDBC namespace')
    command = ['docker','compose','-f','docker-compose.spark.yml','-p',RunConfig.from_env().token+'-spark-'+namespace,
               'exec','-T','sfx-tdemu','psql','-U','etl_batch','-d','sfx_teradata','-Atc',
               'SELECT row_to_json(t) FROM sfx_audit.spark_alert_anomaly t']
    raw = subprocess.check_output(command,cwd=ROOT,text=True)
    rows = [json.loads(line) for line in raw.splitlines()]
    columns = ['ALERT_ID','USER_ID','SCORE','Z_SCORE']
    if any(list(row)!=columns for row in rows):
        raise ValueError('Unexpected audit JDBC column contract')
    before.execute('CREATE SCHEMA IF NOT EXISTS SFX_AUDIT')
    before.execute('CREATE TABLE SFX_AUDIT.SPARK_ALERT_ANOMALY (ALERT_ID BIGINT,USER_ID BIGINT,SCORE DOUBLE,Z_SCORE DOUBLE)')
    if rows:
        before.executemany('INSERT INTO SFX_AUDIT.SPARK_ALERT_ANOMALY VALUES (?,?,?,?)',[list(row.values()) for row in rows])
    after.execute('CREATE SCHEMA IF NOT EXISTS COMPAT')
    model = ROOT/'warehouse/dbt/models/spark/security_alert_anomaly/security_alert_anomaly_jdbc.sql'
    query = render_model(model)
    after.execute('CREATE TABLE COMPAT.SPARK_ALERT_ANOMALY AS '+query)
    result = local_compare(before,after,'SFX_AUDIT.SPARK_ALERT_ANOMALY','COMPAT.SPARK_ALERT_ANOMALY',sample_size=10000,keys=['ALERT_ID'])
    return {'measurement':result,'query':query,'source_command':command,
            'source_rows_sha256':hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(),
            'conversion_sha256':checksums([model]),'shared_with':'audit',
            'manifest_assignment':{'SFX_AUDIT.SECURITY_ALERT':'audit','SFX_AUDIT.SPARK_ALERT_ANOMALY':'not declared'}}


def files_for_job(runtime, job):
    inputs = []
    for source in job['inputs']:
        area, table = source.split('.')
        folder = runtime/'landing'/area/table
        files = sorted(p for p in folder.glob('*') if p.is_file() and not p.name.startswith(('.', '_')))
        if table != 'FILE_OBJECT_BLOBS':
            files = [p for p in files if p.suffix=='.psv']
        if not files:
            raise ValueError('Missing Spark landing input: '+source)
        inputs.extend(files)
    dependencies = []
    for name in job['dependencies']:
        files = sorted((runtime/'lake/documents'/name).rglob('*.parquet'))
        if not files:
            raise ValueError('Missing upstream Spark output: '+name)
        dependencies.extend(files)
    output = runtime/'lake'/job['area']/job['name']
    paths = sorted(output.rglob('*.parquet'))
    log = runtime/'logs'/(job['name']+'.log')
    if not paths or not log.is_file():
        raise ValueError('Missing Spark parquet output or execution log')
    text = log.read_text()
    if 'Successfully stopped SparkContext' not in text or 'Traceback (most recent call last)' in text or 'Exception in thread "main"' in text:
        raise ValueError('Legacy Spark execution did not complete successfully')
    run_date = None
    if job['name']=='file_object_binary_extract':
        dates = re.findall(r'BINARY_OUTPUT_ROWS=\d+ RUN_DATE=(\d{4}-\d{2}-\d{2})',text)
        if len(dates)!=1:
            raise ValueError('Missing/unbound binary run partition')
        run_date = dates[0]
        paths = [p for p in paths if 'run_date='+run_date in p.parts]
        if not paths:
            raise ValueError('Missing current binary partition output')
    newest = max(p.stat().st_mtime_ns for p in inputs+dependencies)
    if min(p.stat().st_mtime_ns for p in paths+[log]) < newest:
        raise ValueError('Spark output predates landing/upstream inputs; rerun legacy job')
    return inputs, dependencies, paths, log, run_date


def load_inputs(connection, runtime, job, loaded):
    definitions = schemas()
    for source in job['inputs']:
        if source in loaded:
            continue
        area,table = source.split('.')
        target = 'SPARK_INPUT.'+identifier(table)
        if table=='FILE_OBJECT_BLOBS':
            connection.execute('CREATE TABLE '+target+' (STORAGE_KEY VARCHAR,CONTENT BLOB)')
            folder = runtime/'landing'/area/table
            rows = [(str(path.relative_to(runtime/'landing')),path.read_bytes()) for path in sorted(folder.glob('*'))
                    if path.is_file() and not path.name.startswith(('.', '_'))]
            if rows:
                connection.executemany('INSERT INTO '+target+' VALUES (?,?)',rows)
        else:
            columns = {name:kind.replace('TEXT','VARCHAR') for name,kind in definitions[table]}
            connection.read_csv(str(runtime/'landing'/area/table/'*.psv'),delimiter='|',header=True,
                columns=columns,na_values='',quotechar='"',escapechar='"').create(target)
        loaded.add(source)


def materialize(before, after, objects, namespace, runtime=None):
    runtime = runtime or ROOT/'etl/spark/.data'/namespace
    specs = json.loads((DOCUMENTS/'spark_jobs.json').read_text())
    objects = {o['name']:o for o in objects if o['system']=='spark' and o['subject_area']=='documents'}
    ready, errors, evidence, loaded = set(), {}, {}, set()
    for connection,schema in [(before,'SFX_SPARK'),(after,'SPARK'),(after,'SPARK_INPUT')]:
        connection.execute('CREATE SCHEMA IF NOT EXISTS '+schema)
    register_udfs(after)
    decisions = json.loads((DOCUMENTS/'decisions.json').read_text())
    contract = {r['name']:r for r in json.loads((DOCUMENTS.parent/'parity/documents.json').read_text())}
    for job in specs:
        name = job['name']
        if name not in objects:
            continue
        identifier(job['target'])
        identifier(name)
        target = 'SPARK.'+job['target'].upper()
        source = 'SFX_SPARK.'+name.upper()
        before.execute('DROP TABLE IF EXISTS '+source)
        after.execute('DROP TABLE IF EXISTS '+target)
        try:
            if objects[name]['target']!=job['target'] or objects[name]['target_type']!='dbt_model':
                raise ValueError('Documents Spark target differs from approved manifest')
            if contract[job['contract']]['keys']!=job['keys']:
                raise ValueError('Documents Spark keys differ from relation contract')
            inputs,dependencies,paths,log,day = files_for_job(runtime,job)
            if any('SPARK.SPARK__'+dep.upper() not in ready for dep in job['dependencies']):
                raise ValueError('Upstream candidate has not passed parity')
            load_inputs(after,runtime,job,loaded)
            model = ROOT/job['model']
            query = render_model(model,day)
            before.read_parquet([str(p) for p in paths],hive_partitioning=True).create(source)
            uppercase_columns(before,source)
            if day:
                before.execute('ALTER TABLE '+source+' ALTER COLUMN RUN_DATE TYPE VARCHAR')
            execute_model(after,job,day)
            uppercase_columns(after,target)
            result = local_compare(before,after,source,target,sample_size=10000,keys=job['keys'])
            blockers = [d['object'] for d in decisions if 'spark.'+name in d['blocks']]
            evidence[name] = {'status':'green' if result['passed'] and not blockers else 'red',
                'measurement':result, 'blockers':blockers, 'target':job['target'],
                'legacy_output':path_name(paths[0].parent), 'run_date':day,
                'landing_sha256':checksums(inputs), 'upstream_sha256':checksums(dependencies),
                'output_sha256':checksums(paths), 'execution_log_sha256':checksums([log]),
                'conversion_sha256':checksums([model,UDFS]),
                'legacy_code_sha256':checksums([ROOT/job['source'],ROOT/'etl/spark/jobs/py/common/runtime.py',ROOT/'etl/spark/jobs/py/common/binary_documents.py']),
                'query':query, 'build':'initial snapshot; selected binary run partition only; no incremental replay',
                'inputs':job['inputs'], 'shared_input':name in ('security_alert_anomaly','docs_storage_by_owner')}
            if name=='security_alert_anomaly':
                side = jdbc_output(before,after,namespace)
                evidence[name]['side_outputs'] = {'SFX_AUDIT.SPARK_ALERT_ANOMALY':side}
                if not side['measurement']['passed']:
                    evidence[name]['status'] = 'red'
            if evidence[name]['status']=='green':
                ready.add(target)
        except (duckdb.Error,ValueError,OSError,subprocess.CalledProcessError,sqlglot.errors.SqlglotError) as error:
            errors[target] = str(error)
            evidence[name] = {'status':'red','error':str(error),'target':job['target']}
    return ready,errors,evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--namespace',default='sfx-1119-before')
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    config = RunConfig.from_env()
    if config.token!='sfx1119' or args.namespace!=config.before_namespace:
        raise ValueError('Documents Spark proof requires sfx1119 BEFORE namespace')
    manifest = yaml.safe_load((DOCUMENTS.parent/'manifest.yaml').read_text())
    with duckdb.connect() as before,duckdb.connect() as after:
        ready,errors,evidence = materialize(before,after,manifest['objects'],args.namespace)
    result = {'namespace':args.namespace,'target':'duckdb','snowflake':'not attempted',
              'jobs':evidence,'errors':errors,'ready':sorted(ready)}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,default=str)+'\n')
    for name,row in evidence.items():
        measurement = row.get('measurement',{})
        print(name,row['status'],measurement.get('row_count'),
              'hash_delta='+str(measurement.get('keyed_row_hash',{}).get('difference')),row.get('error',''))


if __name__=='__main__':
    main()
