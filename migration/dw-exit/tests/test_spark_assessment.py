import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import assess
import spark_analysis as spark


def test_python_static_io_and_constructs():
    parsed = spark.parse_source('''
register(spark, "DOCUMENT", "APP_USER")
frame = landing(spark, "DOC_SHARE").rdd.map(f)
other = jdbc_read(spark, "sfx_billing.PAYMENT")
source = spark.read.parquet("/opt/lake/audit/audit_daily_summary")
save(frame, "documents", "graph", "sfx_documents.SPARK_GRAPH")
''')
    assert parsed['inputs'] == {(None, 'DOCUMENT'), (None, 'APP_USER'), (None, 'DOC_SHARE')}
    assert parsed['outputs'] == {'documents/graph'}
    assert parsed['jdbc_reads'] == {'SFX_BILLING.PAYMENT'}
    assert parsed['jdbc_writes'] == {'SFX_DOCUMENTS.SPARK_GRAPH'}
    assert parsed['lake_reads'] == {'audit/audit_daily_summary'}
    assert parsed['constructs'] == {'rdd', 'jdbc'}


def test_scala_static_io_and_constructs():
    parsed = spark.parse_source('''
BatchSupport.register(spark, "audit", "AUDIT_EVENT", "COMPLIANCE_FLAG")
val x = BatchSupport.landing(spark, "users", "APP_USER")
val f = udf((x: Int) => x + 1)
BatchSupport.save(x, "audit", "summary", Some("sfx_audit.SPARK_SUMMARY"))
''', scala=True)
    assert parsed['inputs'] == {('audit', 'AUDIT_EVENT'), ('audit', 'COMPLIANCE_FLAG'), ('users', 'APP_USER')}
    assert parsed['outputs'] == {'audit/summary'}
    assert parsed['jdbc_writes'] == {'SFX_AUDIT.SPARK_SUMMARY'}
    assert parsed['constructs'] == {'udf', 'jdbc'}


def test_empty_and_invalid_source():
    assert all(not value for value in spark.parse_source('').values())
    with pytest.raises(SyntaxError):
        spark.parse_source('landing(')


def test_cron_states():
    assert spark.cron('') == {'state': 'missing', 'schedule': None}
    assert spark.cron('# explanation\n# 11 2 * * * /opt/etl/spark/submit/old.sh') == {
        'state': 'disabled', 'schedule': '11 2 * * *'}
    assert spark.cron('# old\n9 1 * * * /opt/etl/spark/submit/new.sh')['state'] == 'enabled'


def test_observation_window_is_relative_to_newest_packaged_run():
    runs = {'recent': [{'start': '2026-11-10T20:00:00Z'}],
            'old': [{'start': '2026-07-15T20:00:00Z'}]}
    assert spark.observation_window(runs) == ['2026-08-13', '2026-11-10']
    assert spark.observation_window({}) is None
    with pytest.raises(ValueError):
        spark.observation_window({'bad': [{'start': 'not-a-date'}]})


@pytest.mark.parametrize('path', [
    'warehouse/dbt/models/spark/job/schema.yml', 'warehouse/snowflake/read.sql',
    'warehouse/parity/read.py', 'warehouse/snowpark/job.py', 'warehouse/pipeline/read.py',
    'migration/other/read.sql', 'etl/airflow/dags/job.py', 'docs/query.sql',
    'services/report/README.md', 'README.MD', 'scripts/mention.py',
])
def test_non_reader_paths(path):
    assert spark.non_reader_reason(path, [])


def test_legacy_reader_paths_and_explicit_exclusions():
    registry = [{'path': 'consumers/export'}]
    for path in ('services/report/query.sql', 'clients/export.py', 'notebooks/report.ipynb',
                 'consumers/export/query.sql'):
        assert spark.non_reader_reason(path, registry) is None
    assert spark.non_reader_reason('warehouse/dbt/query.sql', [{'path': 'warehouse/dbt'}])


def test_board_updates_only_assessment_counts(tmp_path):
    path = tmp_path / 'board.json'
    original = {'waves': {'old': 1}, 'licence_counters': {'old': 1}, 'run_token': 'sfx1119',
                'target': 'duckdb', 'rows': [{'id': 'object', 'wave': 3, 'row_count': {'before': 5}}],
                'measurement_contract': {'source': 'emulator'}, 'summary': {'green': 1}}
    path.write_text(json.dumps(original))
    assess.update_board(path, [], {'spark_jobs': {'remaining': 27}})
    updated = json.loads(path.read_text())
    assert updated['waves'] == assess.board([], {})['waves']
    assert updated['licence_counters'] == {'spark_jobs': {'remaining': 27}}
    assert {k: v for k, v in updated.items() if k not in ('waves', 'licence_counters')} == {
        k: v for k, v in original.items() if k not in ('waves', 'licence_counters')}


def test_board_creation_and_invalid_existing_board(tmp_path):
    path = tmp_path / 'board.json'
    assess.update_board(path, [], {})
    assert json.loads(path.read_text()) == assess.board([], {})
    path.write_text('not JSON')
    with pytest.raises(json.JSONDecodeError):
        assess.update_board(path, [], {})
    assert path.read_text() == 'not JSON'


def test_empty_and_inconsistent_history(tmp_path):
    source = assess.ROOT / 'etl/spark/history'
    for name in ('eventlog.py', 'compute_baseline.py'):
        (tmp_path / name).write_text((source / name).read_text())
    (tmp_path / 'eventlogs').mkdir()
    (tmp_path / 'baseline.json').write_text(json.dumps({'jobs': {}}))
    assert dict(spark.history(tmp_path)) == {}
    (tmp_path / 'baseline.json').write_text(json.dumps({'jobs': {'missing': {'app_id': 'absent'}}}))
    with pytest.raises(ValueError, match='baseline differs'):
        spark.history(tmp_path)


@pytest.fixture(scope='module')
def estate():
    return assess.build()


def test_spark_inventory_and_rules(estate):
    jobs = [r for r in estate['objects'] if r['system'] == 'spark']
    assert len(jobs) == 30
    inventory = {r['id']: r for r in estate['artifacts']}
    for row in jobs:
        artifact = inventory[row['id']]
        assert artifact['loc'] == assess.loc((assess.ROOT / row['source']).read_text()) > 0
        assert row['complexity'] == artifact['complexity']
        assert row['output_relations']
        run = row['run_evidence']
        assert run['window'] == ['2026-08-13', '2026-11-10']
        assert run['runs_in_window'] == sum(run['window'][0] <= app['start'][:10] <= run['window'][1]
                                          for app in run['applications'])
        assert run['last_run'] == max(app['start'] for app in run['applications'])
        assert run['executor_hours'] == round(sum(app['executor_hours'] for app in run['applications']), 9)
        assert row['owner_source'] == 'proposed' or row['owner_source'].startswith('output readership')
        if row['name'].startswith('lake_compaction_'):
            assert row['target_type'] == 'retire'
            assert 'replaced by Snowflake storage management' in row['risk_reasons']
        elif (run['cron']['state'] != 'enabled' or run['runs_in_window'] == 0) and not run['readers']:
            assert row['target_type'] == 'retire'
        elif row['target_type'] != 'retire':
            snowpark = set(artifact['constructs'].split('; ')) & {'udf', 'rdd', 'graph', 'binary', 'stateful'}
            assert row['target_type'] == ('snowpark' if snowpark else 'dbt_model')
            assert row['wave'] >= (3 if row['subject_area'] == 'billing' else 2)
    binary = next(row for row in jobs if row['name'] == 'file_object_binary_extract')
    assert 'ModuleNotFoundError' in binary['findings'][0]
    assert inventory[binary['id']]['constructs'] == 'binary; udf'
    assert all(row['owner'] == '@otterworks/data-platform' for row in jobs)
    assert estate['counters']['spark_jobs']['remaining'] == sum(r['target_type'] != 'retire' for r in jobs)
    assert estate['counters']['spark_executor_hours']['remaining'] > 0
    assert sum(r['run_evidence']['runs_in_window'] for r in jobs) == 29
    assert estate['counters']['spark_jobs']['remaining'] == 27
    assert all(not spark.non_reader_reason(reader['path'], [])
               for row in jobs for reader in row['run_evidence']['readers'] if reader['kind'] == 'repo')
    mentions = [mention for row in jobs for mention in row['run_evidence']['non_reader_mentions']]
    assert any(mention['path'].startswith('warehouse/dbt/') for mention in mentions)
    assert all(mention['reason'] for mention in mentions)


def test_spark_edges_and_shared_feeds(estate):
    jobs = {r['name']: r for r in estate['objects'] if r['system'] == 'spark'}
    objects = {r['name']: r for r in estate['objects']}
    links = set(estate['links'])
    assert (jobs['audit_daily_summary']['id'], jobs['lake_compaction_audit']['id']) in links
    assert (jobs['docs_event_export_hourly']['id'], jobs['lake_compaction_documents']['id']) in links
    assert (objects['SFX_BILLING.PAYMENT']['id'], jobs['billing_payment_aging']['id']) in links
    relations = {r['name']: r['id'] for r in estate['external_relations']}
    assert (jobs['billing_gl_trial_balance']['id'], relations['SFX_BILLING.SPARK_GL_TRIAL_BALANCE']) in links
    folder_job = jobs['docs_folder_legacy_report']['id']
    feeds = {a for a, b in links if b == folder_job and '/documents/FOLDER/' in a}
    assert feeds
    loaders = {r['id'] for r in estate['objects'] if r['kind'] in ('fastload', 'tpt')}
    assert all(any(a == feed and b in loaders for a, b in links) for feed in feeds)


def test_retire_and_stale_evidence(estate):
    for row in estate['objects']:
        if row['target_type'] != 'retire':
            continue
        facts = row['retire_evidence']
        if row['system'] == 'spark':
            assert facts == row['run_evidence']
        else:
            assert facts['read_count'] == facts['usage_counts'].get('READ', 0)
            assert len(facts['recent_accesses']) <= 5
            assert all({'QueryID', 'principal', 'timestamp', 'usage_type'} <= access.keys()
                       for access in facts['recent_accesses'])
            if 'feeds only dead objects' in row['risk_reasons']:
                assert facts['feeds_dead_objects']
                assert set(facts['feeds_dead_objects']) <= set(estate['dead'])
    objects = {r['id']: r for r in estate['objects']}
    assert estate['stale']
    for row in estate['stale']:
        assert objects[row['id']]['target_type'] != 'retire'
        assert row['last_read'][:10] < '2026-09-10'
        assert row['review']


def test_full_query_history_evidence(tmp_path):
    base = tmp_path / 'warehouse/teradata/dbql'
    base.mkdir(parents=True)
    (base / 'qrylog.csv').write_text('QueryID,UserName,StartTime\n1,old_reader,2026-07-01 00:00:00\n2,writer,2026-09-01 00:00:00\n')
    (base / 'objectusage.csv').write_text('QueryID,ObjectDatabaseName,ObjectTableName,UsageType\n1,SFX_A,T,READ\n2,SFX_A,T,WRITE\n')
    evidence = assess.usage_evidence(tmp_path)
    facts = evidence('SFX_A.T')
    assert facts['read_count'] == 0
    assert facts['last_read'] == '2026-07-01 00:00:00'
    assert facts['last_write'] == '2026-09-01 00:00:00'
    assert facts['usage_counts'] == {'READ': 0, 'WRITE': 1}
    assert facts['recent_accesses'][0]['principal'] == 'old_reader'
    assert evidence('SFX_A.NEVER')['last_read'] is None
