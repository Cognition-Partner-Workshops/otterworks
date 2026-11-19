"""Replay explicit binary partition writes against the actual local Spark job."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT),str(ROOT/'migration/dw-exit')]

import duckdb

from parity import spark_documents as spark
from parity.ladder import local_compare
from warehouse.run_config import RunConfig


def history(before, after, runtime, job):
    source = 'SFX_SPARK.FILE_OBJECT_BINARY_EXTRACT'
    # source is the fixed local relation above, never a landing value.
    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
    before.execute('DROP TABLE IF EXISTS '+source)
    paths = sorted((runtime/'lake/documents/file_object_binary_extract').rglob('*.parquet'))
    before.read_parquet([str(p) for p in paths],hive_partitioning=True).create(source)
    spark.uppercase_columns(before,source)
    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
    before.execute('ALTER TABLE '+source+' ALTER COLUMN RUN_DATE TYPE VARCHAR')
    return local_compare(before,after,source,'SPARK.SPARK__FILE_OBJECT_BINARY_EXTRACT',
                         sample_size=10000,keys=job['keys'])


def replay(dates, output):
    config = RunConfig.from_env()
    if config.token!='sfx1119':
        raise ValueError('Replay requires sfx1119 scope')
    namespace = config.before_namespace
    runtime = ROOT/'etl/spark/.data'/namespace
    job = next(j for j in json.loads((spark.DOCUMENTS/'spark_jobs.json').read_text()) if j['name']=='file_object_binary_extract')
    inputs,_,_,log,initial = spark.files_for_job(runtime,job)
    landing = spark.checksums(inputs)
    steps,logs = [],[]
    with duckdb.connect() as before,duckdb.connect() as after:
        before.execute('CREATE SCHEMA SFX_SPARK')
        after.execute('CREATE SCHEMA SPARK')
        after.execute('CREATE SCHEMA SPARK_INPUT')
        spark.register_udfs(after)
        spark.load_inputs(after,runtime,job,set())
        partitions = sorted(p.name.removeprefix('run_date=') for p in (runtime/'lake/documents/file_object_binary_extract').glob('run_date=*') if p.is_dir())
        # Seed previously materialized dates from the identical, fingerprinted landing.
        for index,day in enumerate(partitions):
            spark.execute_model(after,job,day,incremental=index>0)
        steps.append({'phase':'initial history','measurement':history(before,after,runtime,job)})
        for day in dates:
            spark.render_model(ROOT/job['model'],day)
            run_log = runtime/'logs'/('file_object_binary_extract.'+day+'.log')
            command = ['docker','compose','-f','docker-compose.spark.yml','-p',config.token+'-spark-'+namespace,
                       'exec','-T','-e','SFX_RUN_DATE='+day,'spark-master','bash',
                       '/opt/sfx/spark/submit/file_object_binary_extract.sh']
            with run_log.open('w') as stream:
                subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,check=True)
            shutil.copyfile(run_log,log)
            spark.files_for_job(runtime,job)
            if landing!=spark.checksums(inputs):
                raise ValueError('Landing changed during actual replay')
            spark.execute_model(after,job,day,incremental=True)
            measured = history(before,after,runtime,job)
            steps.append({'phase':'legacy + incremental '+day,'command':command,'measurement':measured})
            logs.append(run_log)
            if not measured['passed']:
                break
    paths = sorted((runtime/'lake/documents/file_object_binary_extract').rglob('*.parquet'))
    payload = {'namespace':namespace,'dates':dates,'initial_log_date':initial,'steps':steps,
               'passed':all(s['measurement']['passed'] for s in steps),
               'landing_sha256':landing,'output_sha256':spark.checksums(paths),
               'execution_log_sha256':spark.checksums(logs+[log]),
               'conversion_sha256':spark.checksums([ROOT/job['model'],spark.UDFS]),
               'legacy_code_sha256':spark.checksums([ROOT/job['source'],ROOT/'etl/spark/jobs/py/common/runtime.py'])}
    output.write_text(json.dumps(payload,indent=2,default=str)+'\n')
    for step in steps:
        result = step['measurement']
        print(step['phase'],result['row_count'],'hash_delta='+str(result['keyed_row_hash']['difference']),result['passed'])
    if not payload['passed']:
        raise ValueError('Actual partition replay differs')


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dates',nargs='+',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    replay(args.dates,args.output)
