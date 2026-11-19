import copy
import json
from types import SimpleNamespace

import pytest

from lakehouse.orchestration import graph
from lakehouse.parity import analytics as oracle
from lakehouse.parity.documents_external_fakes import AWS
from lakehouse.runtime import analytics_daily as analytics
from lakehouse.runtime import documents_external
from lakehouse.runtime import external_settings as settings
from lakehouse.audit.archive import archive


@pytest.fixture
def config(tmp_path, monkeypatch):
    path = tmp_path / 'external.ini'
    path.write_text('[aws]\nregion=us-east-1\n[database]\nhost=fixture\nport=5432\n'
                    'database=fixture\nuser=fixture\n[s3]\ndata_lake_bucket=fixture-analytics\n'
                    'analytics_prefix=analytics/daily\nfile_storage_bucket=source\n'
                    'quarantine_bucket=quarantine\n')
    monkeypatch.setenv('ETL_CONFIG_PATH', str(path))
    monkeypatch.setenv('ETL_DB_PASSWORD', 'fixture-value')
    monkeypatch.setenv('ETL_S3_BUCKET_OWNER', '123456789012')
    monkeypatch.delenv('ETL_SECRET_ID', raising=False)
    return settings.load_config()


@pytest.mark.parametrize('scenario', oracle.fixture('20261109')['scenarios'], ids=lambda value: value['name'])
def test_analytics_unchanged_script_outputs(config, tmp_path, scenario):
    old, new = [oracle.Services(scenario, '20261109') for _ in range(2)]
    oracle.legacy(old, config, '20261109')
    analytics.run(config, new, new.connect, '20261109', tmp_path / 'journal.json')
    assert oracle.outputs(new) == oracle.outputs(old)
    assert set(new.deleted) == set(old.deleted)
    if new.deleted:
        assert new.operations.index('sqs:delete') > max(
            i for i, operation in enumerate(new.operations) if operation.startswith(('s3:', 'pg:')))


@pytest.mark.parametrize('failure', ['summary', 'hourly_breakdown', 'top_users', 'report.json', 'database', 'scan'])
def test_analytics_partial_failure_and_retry_idempotence(config, tmp_path, failure):
    scenario = oracle.fixture('20261109')['scenarios'][0]
    service = oracle.Services(scenario, '20261109')
    service.fail_db = failure == 'database'
    service.fail_scan = failure == 'scan'
    service.fail_key = failure if failure not in ('database', 'scan') else None
    path = tmp_path / 'journal.json'
    with pytest.raises(RuntimeError):
        analytics.run(config, service, service.connect, '20261109', path)
    assert service.deleted == []
    service.fail_db = service.fail_scan = False
    service.fail_key = None
    if failure == 'scan':
        service.offset = 0
    analytics.run(config, service, service.connect, '20261109', path)
    expected = oracle.Services(scenario, '20261109')
    oracle.legacy(expected, config, '20261109')
    assert oracle.outputs(service) == oracle.outputs(expected)
    previous = copy.deepcopy((service.objects, service.rows, service.operations))
    analytics.run(config, service, service.connect, '20261109', path)
    assert previous == (service.objects, service.rows, service.operations)


def test_analytics_ack_failure_resumes_snapshot(config, tmp_path):
    service = oracle.Services(oracle.fixture('20261109')['scenarios'][0], '20261109')
    service.fail_delete = True
    journal = tmp_path / 'journal.json'
    with pytest.raises(RuntimeError, match='acknowledgement'):
        analytics.run(config, service, service.connect, '20261109', journal)
    assert json.loads(journal.read_text())['status'] == 'written'
    before = copy.deepcopy((service.objects, service.rows))
    service.fail_delete = False
    service.messages.append(dict(MessageId='later', ReceiptHandle='new', Body='{}'))
    service.offset = 0
    service.messages[0]['ReceiptHandle'] = 'renewed'
    analytics.run(config, service, service.connect, '20261109', journal)
    assert before == (service.objects, service.rows)
    assert 'later' not in service.deleted and '0' in service.deleted


def test_analytics_malformed_and_corrupt_checkpoint(config, tmp_path):
    service = oracle.Services(dict(sqs=['{bad', {'eventType': {'invalid': 'unhashable'}}]), '20261109')
    with pytest.raises(TypeError):
        analytics.run(config, service, service.connect, '20261109', tmp_path / 'bad-event.json')
    assert service.deleted == []
    journal = tmp_path / 'corrupt.json'
    journal.write_text('{')
    with pytest.raises(json.JSONDecodeError):
        analytics.run(config, service, service.connect, '20261109', journal)
    journal.write_text(json.dumps(dict(version=1, business_date='20261108', status='complete')))
    with pytest.raises(ValueError, match='version/date'):
        analytics.run(config, service, service.connect, '20261109', journal)


def test_analytics_receive_limit_and_no_dynamo_dedup(config, tmp_path):
    service = oracle.Services(oracle.fixture('20261109')['scenarios'][0], '20261109')
    service.receive_failures = 3
    analytics.run(config, service, service.connect, '20261109', tmp_path / 'receive.json')
    assert oracle.outputs(service)['summary']['total_events'] == 3
    assert service.deleted == []


def test_ini_path_compatibility(config, tmp_path, monkeypatch):
    assert settings.load_config().get('database', 'host') == 'fixture'
    monkeypatch.setenv('ETL_CONFIG_PATH', str(tmp_path / 'missing'))
    with pytest.raises(RuntimeError, match='not found'):
        settings.load_config()
    monkeypatch.delenv('ETL_CONFIG_PATH')
    assert settings.load_config().get('s3', 'analytics_prefix') == 'analytics/daily'


def test_ini_and_required_secrets(config, monkeypatch):
    for value in ['', ' ', '\t']:
        monkeypatch.setenv('ETL_DB_PASSWORD', value)
        with pytest.raises(RuntimeError, match='missing or empty'):
            settings.required_secret('ETL_DB_PASSWORD')
    monkeypatch.delenv('ETL_DB_PASSWORD')
    with pytest.raises(RuntimeError):
        settings.required_secret('ETL_DB_PASSWORD')


@pytest.mark.parametrize('payload', [None, '{', '[]', '{}', '{"ETL_DB_PASSWORD":null}',
                                    '{"ETL_DB_PASSWORD":1}', '{"ETL_DB_PASSWORD":" "}'])
def test_job_secret_json_validation(payload):
    client = SimpleNamespace(get_secret_value=lambda **_: {'SecretString': payload})
    with pytest.raises(RuntimeError):
        settings.secrets_for('analytics_daily.py', client)


def test_job_secret_json_and_least_privilege(config, monkeypatch):
    requested = []

    def fetch(**kwargs):
        requested.append(kwargs)
        return {'SecretString': json.dumps(dict(ETL_DB_PASSWORD='$(not-a-command)',
                                                ETL_MEILISEARCH_API_KEY='not-needed'))}

    client = SimpleNamespace(get_secret_value=fetch)
    assert settings.secrets_for('analytics_daily.py', client) == {'ETL_DB_PASSWORD': '$(not-a-command)'}
    assert requested == [{'SecretId': 'otterworks/etl/analytics_daily'}]
    assert settings.secrets_for('audit_archive_weekly.py', None) == {}
    assert settings.secrets_for('user_activity_daily.py', None) == {}
    monkeypatch.setenv('ETL_SECRET_ID', 'fixture/custom')
    aws = SimpleNamespace(client=lambda *a, **k: client)
    assert settings.settings('analytics_daily.py', aws)[1]['ETL_DB_PASSWORD'] == '$(not-a-command)'
    assert requested[-1] == {'SecretId': 'fixture/custom'}
    with pytest.raises(ValueError):
        settings.secrets_for('../other.py', client)


def test_shared_dispatch_allowlist_and_argv(tmp_path, monkeypatch):
    source = tmp_path / 'source with spaces; echo ignored'
    args = settings.command('user_activity_daily.py', '20261109', source=source)
    assert args[-2:] == ['--source', str(source)]
    for name in ('analytics_daily.py; echo unsafe', '../analytics_daily.py', '', 'unknown'):
        with pytest.raises(ValueError):
            settings.command(name, '20261109')
    for job in ('analytics_daily.py', 'user_activity_daily.py'):
        with pytest.raises(ValueError):
            settings.command(job, '20261109')
    calls = []
    monkeypatch.setattr(settings.subprocess, 'run', lambda argv, **kwargs: calls.append((argv, kwargs)))
    monkeypatch.setattr(settings.sys, 'argv', ['external_settings', '--job', 'analytics_daily.py',
                         '--business-date', '20261109', '--ready', str(source)])
    settings.main()
    assert calls[0][1] == {'check': True, 'shell': False}
    assert calls[0][0][-1] == str(source)


@pytest.mark.parametrize('owner', ['', ' ', '123', '1234567890123', '１２３４５６７８９０１２'])
def test_all_s3_entrypoints_reject_invalid_owner(config, tmp_path, owner):
    aws = SimpleNamespace(client=lambda *a, **k: pytest.fail('AWS call before owner validation'))
    with pytest.raises(RuntimeError, match='12-digit'):
        analytics.run(config, aws, None, '20261109', tmp_path / 'journal', lambda: owner)
    with pytest.raises(RuntimeError, match='12-digit'):
        archive(None, None, 'bucket', owner, '20261109')
    with pytest.raises(RuntimeError, match='12-digit'):
        documents_external.cleanup(config, aws, owner_provider=lambda: owner)


def test_documents_inventory_passes_expected_owner(config):
    aws = AWS({})
    documents_external.cleanup(config, aws)
    assert next(action for action in aws.actions if action['operation'] == 'list')['ExpectedBucketOwner'] == '123456789012'


def test_analytics_schedule_readiness_and_failure(tmp_path, monkeypatch):
    dag = graph.load()['lakehouse_analytics_daily']
    assert dag['schedule'] == '0 2 * * *' and dag['paused'] and dag['timezone'] == 'UTC'
    sensor, task = graph.ordered(dag['nodes'])
    assert sensor['kind'] == 'artifact_sensor' and task['depends_on'] == [sensor['id']]
    assert task['retries'] == 1 and 'lakehouse.runtime.external_settings' in task['command']
    marker = tmp_path / 'ready.json'
    with pytest.raises(FileNotFoundError):
        analytics.ready(marker, '20261109')
    marker.write_text(json.dumps(dict(business_date='20261108', status='ready')))
    with pytest.raises(ValueError):
        analytics.ready(marker, '20261109')
    marker.write_text('{')
    with pytest.raises(ValueError):
        analytics.ready(marker, '20261109')
    marker.write_text(json.dumps(dict(business_date='20261109', status='ready')))
    analytics.ready(marker, '20261109')
    monkeypatch.setattr(analytics, 'boto3', SimpleNamespace(client=lambda *a, **k: pytest.fail('unexpected AWS')))
    monkeypatch.setattr(analytics, 'settings', lambda *a: pytest.fail('settings before readiness'))
    monkeypatch.setattr(analytics, 'data_root', lambda: tmp_path)
    monkeypatch.setattr(analytics.argparse.ArgumentParser, 'parse_args', lambda _: SimpleNamespace(
        business_date='20261109', ready=tmp_path / 'absent'))
    with pytest.raises(FileNotFoundError):
        analytics.main()
