import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from pyspark.sql.utils import AnalysisException

from lakehouse.orchestration import graph, runner
from lakehouse.parity.documents_spark_fixture import generate
from lakehouse.parity.readers import Readers
from lakehouse.runtime import documents_spark as jobs
from lakehouse.runtime.layout import data_root
from lakehouse.runtime.session import create_session


@pytest.fixture(scope='module')
def spark():
    original = os.environ.get('NS')
    os.environ['NS'] = 'test-documents-spark-' + uuid.uuid4().hex
    session = create_session()
    yield session
    session.stop()
    shutil.rmtree(data_root())
    if original is None:
        del os.environ['NS']
    else:
        os.environ['NS'] = original


@pytest.mark.parametrize('value,expected', [(None, None), ('', None), ('no action', None),
    ('action=é_9 action=last', 'é_9'), ('action=VIEW-status', 'VIEW')])
def test_parse_action(value, expected):
    assert jobs.parse_action(value) == expected


@pytest.mark.parametrize('value,expected', [(None, ''), ('', ''), ('  \t ', ''),
    (' A\t B ', 'a-b'), ('Ops\u00a0 Team', 'ops-team'), ('ÉCOLE ß', 'école-ß')])
def test_normalize_tag(value, expected):
    assert jobs.normalize_tag(value) == expected


def test_shared_fixture_immutable_and_missing_inputs(tmp_path):
    manifest = generate(tmp_path, '20261109')
    root = tmp_path / 'spark/20261109'
    assert jobs.verify_inputs(root) == manifest
    changed = {**manifest, 'version': 2}
    (root / 'manifest.json').write_text(json.dumps(changed))
    with pytest.raises(ValueError, match='manifest changed'):
        jobs.verify_inputs(root, expected=manifest)
    (root / 'manifest.json').write_text(json.dumps(manifest))
    assert all(hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
               for name, digest in manifest['files'].items())
    path = root / 'documents/DOC_TAG/20261109.psv'
    original = path.read_bytes()
    path.write_bytes(original + b'corrupt')
    with pytest.raises(ValueError, match='Spark input changed'):
        jobs.verify_inputs(root)
    jobs.verify_inputs(root, ['DOCUMENT'])
    path.write_bytes(original)
    extra = path.with_name('untracked.psv')
    extra.write_bytes(original)
    with pytest.raises(ValueError, match='manifest'):
        jobs.verify_inputs(root)
    extra.unlink()
    path.unlink()
    with pytest.raises(ValueError, match='manifest'):
        jobs.verify_inputs(root)
    with pytest.raises(FileNotFoundError):
        jobs.verify_inputs(tmp_path / 'missing')


def test_spark_feed_transforms_normal(spark, tmp_path):
    generate(tmp_path, '20261109')
    root = tmp_path / 'spark/20261109'
    frames = {table: jobs.read_input(spark, root, table) for table in jobs.SCHEMAS}
    storage = jobs.transform(spark, 'docs_storage_by_owner', frames)
    owner = storage.where('USER_ID = 1').first()
    assert (owner.FILE_COUNT, owner.SIZE_BYTES) == (5, None)
    assert storage.count() == 17
    inferred = {table: jobs.read_input(spark, root, table, infer=True) for table in ['DOC_SHARE', 'DOCUMENT']}
    assert dict(inferred['DOCUMENT'].dtypes)['DOCUMENT_ID'] == 'int'
    shares = jobs.transform(spark, 'docs_share_activity', inferred)
    row = shares.where("OWNER_USER_ID = 1 AND PERMISSION = 'edit'").first()
    assert (row.SHARES, row.RECIPIENTS) == (3, 2)
    folders = jobs.transform(spark, 'docs_folder_legacy_report', frames)
    assert folders.count() == 10
    assert folders.where('FOLDER_ID = 10').first().DOCUMENTS == 0
    tags = jobs.transform(spark, 'docs_tag_normalize', frames).collect()
    assert {r.NORMALIZED_TAG for r in tags} >= {'', 'finance', 'annual-review', 'école', 'ß', 'ops-team', 'contract|legal'}
    logs = jobs.transform(spark, 'docs_search_log_parse', frames).collect()
    assert {r.PARSED_ACTION for r in logs} == {None, 'é_9', 'VIEW'}
    exported = jobs.transform(spark, 'docs_event_export_hourly', frames)
    buckets = {r.DOCUMENT_ID: r.EXPORT_BUCKET for r in exported.collect()}
    assert {key: buckets[key] for key in [-1, 9999, 10000, 20000]} == {-1: 9999, 9999: 9999, 10000: 0, 20000: 0}
    compacted = jobs.transform(spark, 'lake_compaction_documents', {}, exported)
    assert compacted.rdd.getNumPartitions() <= 4
    assert compacted.collect() == exported.collect()


def test_empty_transforms_and_invalid_jobs(spark):
    frames = {table: spark.createDataFrame([], schema) for table, (_, schema) in jobs.SCHEMAS.items()}
    exported = jobs.transform(spark, 'docs_event_export_hourly', frames)
    for job in jobs.INPUTS:
        assert jobs.transform(spark, job, frames, exported).count() == 0
    with pytest.raises(ValueError, match='Unknown'):
        jobs.transform(spark, 'missing', frames)
    with pytest.raises(ValueError, match='requires an exported'):
        jobs.transform(spark, 'lake_compaction_documents', {})


def test_dated_runtime_retry_empty_inference_and_backfill_retention(spark, tmp_path):
    generate(tmp_path, '20261108')
    manifest = generate(tmp_path, '20261109')
    root = tmp_path / 'spark/20261109'
    for table in ('DOC_SHARE', 'DOCUMENT'):
        name = f'documents/{table}/20261109.psv'
        path = root / name
        path.write_text(path.read_text().splitlines()[0] + '\n')
        manifest['files'][name] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest['rows'][table] = 0
    (root / 'manifest.json').write_text(json.dumps(manifest))
    jobs.run(spark, tmp_path, '20261108', ['docs_share_activity'])
    for _ in range(2):
        jobs.run(spark, tmp_path, '20261109', ['docs_share_activity', 'docs_event_export_hourly'])
    previous = spark.table('silver_documents.spark_runtime_docs_share_activity_20261108')
    empty = spark.table('silver_documents.spark_runtime_docs_share_activity_20261109')
    assert previous.count() == 51 and empty.count() == 0
    assert dict(previous.dtypes)['OWNER_USER_ID'] == 'int'
    assert dict(empty.dtypes)['OWNER_USER_ID'] == 'string'
    assert spark.table('silver_documents.spark_runtime_docs_event_export_hourly_20261109').count() == 0
    with pytest.raises(AnalysisException):
        jobs.run(spark, tmp_path, '20261109', ['lake_compaction_documents'])


def test_feed_header_missing_empty_and_permissive_cast(spark, tmp_path):
    with pytest.raises(FileNotFoundError, match='feed missing'):
        jobs.read_input(spark, tmp_path, 'DOC_TAG')
    path = tmp_path / 'documents/DOC_TAG/20261109.psv'
    path.parent.mkdir(parents=True)
    for content in ['', 'wrong|header\n']:
        path.write_text(content)
        with pytest.raises(ValueError, match='header differs'):
            jobs.read_input(spark, tmp_path, 'DOC_TAG')
    path.write_text('DOC_TAG_ID|DOCUMENT_ID|TAG\n')
    assert jobs.read_input(spark, tmp_path, 'DOC_TAG').count() == 0
    path.write_text('DOC_TAG_ID|DOCUMENT_ID|TAG\ninvalid|1| X\n')
    assert jobs.read_input(spark, tmp_path, 'DOC_TAG').first().DOC_TAG_ID is None


def test_atomic_idempotent_partition_publication_and_pinned_reader(spark, tmp_path):
    output = tmp_path / 'published'
    frame = spark.createDataFrame([(-1, 9999), (10000, 0), (20000, 0)], 'DOCUMENT_ID long, EXPORT_BUCKET long')
    first = jobs.publish(frame, output, partitioned=True)
    assert output.is_symlink() and (output / '_SUCCESS').is_file()
    assert {p.name for p in first.glob('EXPORT_BUCKET=*')} == {'EXPORT_BUCKET=0', 'EXPORT_BUCKET=9999'}
    pinned = output.resolve(strict=True)
    second = jobs.publish(frame, output, partitioned=True)
    assert first != second and pinned == first and first.is_dir()
    reader = Readers('20261109')
    reader.spark = spark
    rows, _ = reader.read({'kind': 'parquet', 'path': str(output)})
    assert len(rows) == 3
    rows, _ = reader.read({'kind': 'parquet', 'path': str(output / 'EXPORT_BUCKET=0/*.parquet')})
    assert len(rows) == 2
    assert spark.read.parquet(str(pinned)).count() == 3
    def reject():
        raise ValueError('changed input')
    with pytest.raises(ValueError, match='changed input'):
        jobs.publish(frame, output, partitioned=True, validate=reject)
    assert output.resolve() == second
    empty = tmp_path / 'empty'
    version = jobs.publish(frame.limit(0), empty, partitioned=True)
    assert (version / '_SUCCESS').is_file()
    assert spark.read.schema(frame.schema).parquet(str(version)).count() == 0
    with pytest.raises(AnalysisException):
        spark.read.parquet(str(version))


@pytest.mark.parametrize('failure', ['write', 'missing_success', 'swap'])
def test_failed_publication_retains_previous_snapshot(tmp_path, monkeypatch, failure):
    previous = tmp_path / 'previous'
    previous.mkdir()
    (previous / '_SUCCESS').touch()
    output = tmp_path / 'published'
    output.symlink_to(previous, target_is_directory=True)
    def write(path):
        Path(path).mkdir(parents=True)
        if failure == 'write':
            raise OSError('disk full')
        if failure == 'swap':
            (Path(path) / '_SUCCESS').touch()
    writer = SimpleNamespace(mode=lambda _: writer, parquet=write)
    if failure == 'swap':
        def fail_swap(*_):
            raise OSError('swap failed')
        monkeypatch.setattr(jobs.os, 'replace', fail_swap)
    with pytest.raises((OSError, RuntimeError)):
        jobs.publish(SimpleNamespace(write=writer), output)
    assert output.resolve() == previous and (output / '_SUCCESS').is_file()


def test_export_readiness_and_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr(graph, 'data_root', lambda: tmp_path)
    sensor = dict(kind='artifact_sensor', path='{data_root}/{business_date}/snapshot/_SUCCESS',
                  timeout_seconds=1, poke_interval_seconds=1)
    clock = iter([0, 1])
    monkeypatch.setattr(runner.time, 'monotonic', lambda: next(clock))
    with pytest.raises(TimeoutError, match='not ready'):
        runner.execute(sensor, tmp_path, '20261109')
    target = graph.artifact_path(sensor, '20261109')
    target.parent.mkdir(parents=True)
    monkeypatch.setattr(runner.time, 'monotonic', lambda: 0)
    monkeypatch.setattr(runner.time, 'sleep', lambda _: target.touch())
    runner.execute(sensor, tmp_path, '20261109')
    runner.execute(sensor, tmp_path, '20261109')


def test_documents_spark_cron_replacements():
    dags = graph.load()
    schedules = dict(docs_storage_by_owner='4 1 * * *', docs_share_activity='5 1 * * *',
                     docs_search_log_parse='12 2 * * *', docs_tag_normalize='14 2 * * *')
    for job, cadence in schedules.items():
        dag = dags['lakehouse_' + job]
        assert dag['schedule'] == cadence and dag['paused'] is False
        daily = {n['id']: n for n in dag['nodes']}
        node = daily['spark_' + job]
        assert node['kind'] == 'export' and node['depends_on']
        assert 'spark_job:' + job in node['legacy_objects']
        for dependency in node['depends_on']:
            feed = daily[dependency]
            assert feed['kind'] == 'feed_sensor' and feed['landing_prefix'] == 'spark/{business_date}'
            assert str(graph.feed_path(feed, Path('/landing'), '20261109')).startswith('/landing/spark/20261109/')
    storage = next(n for n in dags['lakehouse_docs_storage_by_owner']['nodes'] if n['id'] == 'spark_docs_storage_by_owner')
    assert 'feed_spark_app_user' in storage['depends_on']
    hourly = dags['lakehouse_hourly']
    assert hourly['schedule'] == '18 * * * *' and hourly['paused'] is True
    assert any(n['id'] == 'spark_docs_event_export_hourly' for n in hourly['nodes'])
    folder = dags['lakehouse_documents_folder_manual']
    assert folder['schedule'] is None and folder['paused'] is True
    active = [n for dag in dags.values() if not dag['paused'] for n in dag['nodes']]
    assert not any('docs_folder_legacy_report' in n['id'] for n in active)
    compaction = dags['lakehouse_documents_compaction']
    assert compaction['schedule'] == '19 2 * * *' and compaction['paused'] is True
    nodes = {n['id']: n for n in compaction['nodes']}
    assert nodes['spark_lake_compaction_documents']['depends_on'] == ['await_document_export']
    assert nodes['await_document_export']['kind'] == 'artifact_sensor'
    assert nodes['await_document_export']['path'].endswith('/docs_event_export_hourly/_SUCCESS')
    for dag in dags.values():
        for node in dag['nodes']:
            if node['id'].startswith('dbt_spark_'):
                job = node['id'].removeprefix('dbt_spark_')
                assert 'DOCUMENTS_SPARK_JOB=' + job in node['command']
                assert node['depends_on'] == ['spark_' + job]


@pytest.mark.parametrize('prefix', ['/absolute', '../escape', 'spark/{unknown}', '{}', '{business_date.bad}'])
def test_invalid_spark_landing_prefix(tmp_path, prefix):
    document = yaml.safe_load(graph.PIPELINE.read_text())
    document['dags'][0]['nodes'][0]['landing_prefix'] = prefix
    path = tmp_path / 'invalid.yaml'
    path.write_text(yaml.safe_dump(document))
    with pytest.raises(ValueError, match='landing prefix'):
        graph.load(path)
