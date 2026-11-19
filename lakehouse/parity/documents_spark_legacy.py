"""Execute unchanged legacy jobs with isolated /opt bind mounts, without network."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pyspark

from lakehouse.runtime.documents_spark import INPUTS, verify_inputs
from lakehouse.runtime.ingest import business_date
from lakehouse.runtime.layout import ROOT, data_root


def run(landing, day, jar):
    business_date(day)
    fixture = (Path(landing) / 'spark' / day).resolve()
    manifest = verify_inputs(fixture)
    output = data_root() / 'legacy_spark' / day
    output.mkdir(parents=True, exist_ok=True)
    repo = ROOT.parent
    java_home = Path(shutil.which('java')).resolve().parents[1]
    spark_home = Path(pyspark.__file__).parent
    python_home = Path(sys.base_prefix)
    if not jar.is_file():
        raise FileNotFoundError('Build the legacy Scala jar offline before execution: ' + str(jar))
    base = ['docker', 'run', '--rm', '--network', 'none', '--hostname', 'localhost',
            '--user', f'{os.getuid()}:{os.getgid()}', '--entrypoint', str(spark_home / 'bin/spark-submit')]
    java_config = (java_home / 'conf/security/java.security').resolve().parents[1]
    for source, target, mode in [(repo, repo, 'ro'), (java_home, java_home, 'ro'),
                                 (java_config, java_config, 'ro'),
                                 ('/etc/passwd', '/etc/passwd', 'ro'), ('/etc/group', '/etc/group', 'ro'),
                                 (python_home, python_home, 'ro'), (fixture, '/opt/landing', 'ro'),
                                 (output, '/opt/lake', 'rw')]:
        base += ['-v', f'{source}:{target}:{mode}']
    for key, value in dict(JAVA_HOME=java_home, SPARK_HOME=spark_home, SPARK_LOCAL_IP='127.0.0.1',
                           PYSPARK_PYTHON=Path(sys.executable), PYSPARK_DRIVER_PYTHON=Path(sys.executable),
                           PYTHONPATH=str(repo / 'etl/spark/jobs/py') + ':' + str(repo),
                           LANDING_DIR='/opt/landing', LAKE_DIR='/opt/lake', TZ='UTC', HOME='/tmp',
                           SPARK_SUBMIT_OPTS='-Duser.home=/tmp -Duser.name=ubuntu').items():
        base += ['-e', f'{key}={value}']
    base += ['postgres:16', '--master', 'local[2]', '--driver-memory', '768m', '--conf', 'spark.ui.enabled=false',
             '--conf', 'spark.sql.shuffle.partitions=2', '--conf', 'spark.sql.session.timeZone=UTC']
    dependencies = ['etl/spark/jobs/py/common/runtime.py', 'etl/spark/jobs/py/common/schemas.py',
                    'etl/spark/scala/src/main/scala/sfx/BatchSupport.scala', 'etl/spark/scala/build.sbt']
    sources = {path: hashlib.sha256((repo / path).read_bytes()).hexdigest() for path in dependencies}
    for job in INPUTS:
        if job in ('docs_share_activity', 'lake_compaction_documents'):
            name = {'docs_share_activity': 'DocsShareActivity', 'lake_compaction_documents': 'LakeCompactionDocuments'}[job]
            source = repo / f'etl/spark/scala/src/main/scala/sfx/{name}.scala'
            command = base + ['--class', 'sfx.' + name, str(jar.resolve())]
        else:
            source = repo / f'etl/spark/jobs/py/{job}.py'
            command = base + [str(source)]
        with (output / (job + '.log')).open('w') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
        verify_inputs(fixture, expected=manifest)
        sources[str(source.relative_to(repo))] = hashlib.sha256(source.read_bytes()).hexdigest()
        print('legacy.spark.' + job + ': SUCCEEDED', flush=True)
    provenance = dict(inputs=manifest, sources=sources, scala_jar_hash=hashlib.sha256(jar.read_bytes()).hexdigest(),
                      runtime_image='postgres:16', network='none', python=sys.version,
                      spark=pyspark.__version__,
                      image_id=subprocess.check_output(['docker', 'image', 'inspect', 'postgres:16', '--format', '{{.Id}}'], text=True).strip(),
                      java=subprocess.check_output([str(java_home / 'bin/java'), '-version'], stderr=subprocess.STDOUT, text=True),
                      note='Existing local image is only an isolated filesystem/runtime; host Java, Python and Spark are read-only bind mounts.')
    (output / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--landing', type=Path, required=True)
    parser.add_argument('--business-date', required=True)
    parser.add_argument('--jar', type=Path, required=True)
    args = parser.parse_args()
    run(args.landing, args.business_date, args.jar)


if __name__ == '__main__':
    main()
