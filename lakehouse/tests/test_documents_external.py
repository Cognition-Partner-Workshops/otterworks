import configparser
import json
import sys

import pytest

from lakehouse.orchestration import graph
from lakehouse.parity import documents_external as oracle
from lakehouse.parity.documents_external_fakes import AWS, HTTP
from lakehouse.runtime import documents_external as native


@pytest.fixture
def document(tmp_path):
    value = oracle.fixture('20261109')
    config = configparser.ConfigParser()
    config.read_dict(value['config'])
    path = tmp_path / 'config.ini'
    with path.open('w') as handle:
        config.write(handle)
    return value, path


@pytest.mark.parametrize('category,index', [(category, i) for category in ['search', 'cleanup']
                                         for i in range(len(oracle.fixture('20261109')[category]))])
def test_unchanged_legacy_external_scenarios(document, category, index):
    value, path = document
    scenario = value[category][index]
    job = 'search_reindex_weekly' if category == 'search' else 'storage_cleanup_daily'
    legacy, _ = oracle.execute('legacy', job, scenario, value, path)
    converted, _ = oracle.execute('lakehouse', job, scenario, value, path)
    assert converted == legacy


def test_search_pagination_settings_and_defaults(document):
    value, path = document
    state, _ = oracle.execute('lakehouse', 'search_reindex_weekly', value['search'][0], value, path)
    assert state['outcome'] == {'status': 'success'}
    docs, files = [state['indexes'][name] for name in ['documents', 'files']]
    assert len(docs['documents']) == len(files['documents']) == 101
    assert docs['primaryKey'] == files['primaryKey'] == 'id'
    assert docs['documents']['1']['owner_id'] is None
    assert docs['documents']['2']['title'] == ''
    assert files['documents']['2']['name'] == 'fallback' and files['documents']['2']['size'] == 9
    assert files['documents']['1']['tags'] is None
    assert docs['settings']['searchableAttributes'] == ['title', 'content', 'tags']
    assert files['settings']['sortableAttributes'] == ['updated_at', 'created_at', 'size']
    pages = [action['params'] for action in state['actions'] if '/api/v1/' in action['url']]
    assert pages == [{'page': 1, 'size': 100}, {'page': 2, 'size': 100},
                     {'page': 1, 'page_size': 100}, {'page': 2, 'page_size': 100}]
    batches = [action for action in state['actions'] if action['method'] == 'POST' and action['url'].endswith('/documents')]
    assert [len(action['data']) for action in batches] == [100, 1, 100, 1]
    assert all(action['headers'].get('Authorization') == '[REDACTED SECRET]' for action in batches)


def test_search_failures_polling_and_secret_gate(document):
    value, path = document
    states = {scenario['name']: oracle.execute('lakehouse', 'search_reindex_weekly', scenario, value, path)[0]
              for scenario in value['search']}
    assert states['empty']['outcome'] == {'status': 'success'}
    assert states['empty']['indexes']['documents']['documents'] == {}
    assert states['queued']['elapsed'] > 0 and states['queued']['outcome']['status'] == 'success'
    assert not any('/tasks/' in action['url'] for action in states['no_task_uid']['actions'])
    for name in ['failed_tasks', 'poll_timeout', 'bad_stats']:
        assert states[name]['outcome'] == {'status': 'exit', 'code': 1}
    assert states['poll_timeout']['elapsed'] >= 120
    assert states['delete_http']['outcome'] == {'status': 'success'}
    for name in ['create_http', 'settings_http', 'service_http', 'index_http']:
        assert states[name]['outcome']['status'] == 'error'
    assert states['missing_secret']['actions'] == []


def test_cleanup_copy_delete_order_errors_and_owner_guards(document, monkeypatch):
    value, path = document
    monkeypatch.setenv('DRY_RUN', 'true')
    scenario = next(s for s in value['cleanup'] if s['name'] == 'copy_delete_errors')
    state, _ = oracle.execute('lakehouse', 'storage_cleanup_daily', scenario, value, path)
    report = json.loads(next(iter(state['reports'].values())))
    assert state['outcome'] == {'status': 'success'}
    assert report['report_date'] == '2026-11-09' and report['generated_at'] == value['instant']
    assert report['inventory']['total_objects'] == 5
    assert report['orphans']['orphaned_objects'] == 4
    assert report['orphans']['orphaned_bytes'] == 2147483648 + 29 + 31
    assert report['cleanup']['objects_quarantined'] == report['cleanup']['objects_failed'] == 2
    actions = state['actions']
    assert len([a for a in actions if a['operation'] == 'scan']) == 2
    copied = [a['CopySource']['Key'] for a in actions if a['operation'] == 'copy']
    deleted = [a['Key'] for a in actions if a['operation'] == 'delete']
    assert copied == ['files/orphan', 'files/empty', 'files/copy-fail', 'files/delete-fail']
    assert deleted == ['files/orphan', 'files/empty', 'files/delete-fail']
    assert 'files/copy-fail' in state['objects'] and 'files/delete-fail' in state['objects']
    assert 'quarantined/2026-11-09/files/delete-fail' in state['quarantine']
    assert 'outside/untouched' in state['objects']
    for action in actions:
        if action['operation'] in ['copy', 'delete', 'put']:
            assert action['ExpectedBucketOwner'] == '123456789012'
        if action['operation'] == 'copy':
            assert action['ExpectedSourceBucketOwner'] == '123456789012'
        if action['operation'] == 'delete':
            previous = actions[actions.index(action) - 1]
            assert previous['operation'] == 'copy' and previous['CopySource']['Key'] == action['Key']


def test_cleanup_empty_and_fatal_errors(document):
    value, path = document
    states = {scenario['name']: oracle.execute('lakehouse', 'storage_cleanup_daily', scenario, value, path)[0]
              for scenario in value['cleanup']}
    for name in ['empty', 'all_referenced']:
        report = json.loads(next(iter(states[name]['reports'].values())))
        assert report['orphans']['orphaned_objects'] == report['cleanup']['objects_quarantined'] == 0
    for name in ['list_error', 'scan_error', 'report_error', 'missing_owner', 'invalid_owner']:
        assert states[name]['outcome']['status'] == 'error' and states[name]['reports'] == {}
    for name in ['missing_owner', 'invalid_owner']:
        assert states[name]['actions'] == []


@pytest.mark.parametrize('job', ['search_reindex_weekly', 'storage_cleanup_daily'])
def test_external_task_entrypoint_injected_clients(document, tmp_path, monkeypatch, job):
    value, path = document
    http, aws = HTTP(value['search'][0]), AWS(value['cleanup'][0])
    monkeypatch.setattr(native, 'requests', http)
    monkeypatch.setattr(native, 'boto3', aws)
    monkeypatch.setenv('ETL_CONFIG_PATH', str(path))
    monkeypatch.setenv('ETL_MEILISEARCH_API_KEY', 'fixture-only-key')
    monkeypatch.setenv('ETL_S3_BUCKET_OWNER', '123456789012')
    monkeypatch.setattr(native, 'data_root', lambda: tmp_path)
    monkeypatch.setattr(sys, 'argv', ['documents_external', '--job', job, '--business-date', '20261109'])
    native.main()
    output = json.loads((tmp_path / 'external_runs/20261109' / (job + '.json')).read_text())
    if job == 'search_reindex_weekly':
        assert output == {'documents': 101, 'files': 101}
    else:
        assert output['cleanup']['objects_quarantined'] == 4


def test_external_configuration_guards(tmp_path, monkeypatch):
    monkeypatch.setenv('ETL_CONFIG_PATH', str(tmp_path / 'missing.ini'))
    with pytest.raises(RuntimeError, match='not found'):
        native.load_config()
    for value in ['', ' ', '\t']:
        monkeypatch.setenv('ETL_MEILISEARCH_API_KEY', value)
        with pytest.raises(RuntimeError, match='missing or empty'):
            native.required_secret('ETL_MEILISEARCH_API_KEY')
    for value in ['', '123', '1234567890123']:
        monkeypatch.setenv('ETL_S3_BUCKET_OWNER', value)
        with pytest.raises(RuntimeError, match='12-digit'):
            native.expected_bucket_owner()
    with pytest.raises(AssertionError, match='Unexpected fake HTTP'):
        HTTP({}).get('http://real.invalid/endpoint')


def test_documents_external_cron_replacements():
    dags = graph.load()
    for job, schedule, identity in [('search_reindex_weekly', '0 4 * * 0', '69562b8e166b'),
                                    ('storage_cleanup_daily', '30 2 * * *', 'fd7befdb4e7d')]:
        dag = dags['lakehouse_' + job]
        assert dag['schedule'] == schedule and dag['paused'] is True
        assert dag['timezone'] == 'UTC' and len(dag['nodes']) == 1
        node = dag['nodes'][0]
        assert node['kind'] == 'export' and node['retries'] == 0
        assert node['legacy_objects'] == ['etl_script:etl/scripts/' + job + '.py', 'cron_entry:etl/crontab#' + identity]
        assert 'lakehouse.runtime.documents_external' in node['command']
        assert '--job' in node['command'] and job in node['command']
    fixture = dags['lakehouse_documents_external_fixture']
    assert fixture['schedule'] is None and fixture['paused'] is True
    for node in fixture['nodes'][1:]:
        assert node['kind'] == 'parity' and node['depends_on'] == ['external_documents_fixture']
