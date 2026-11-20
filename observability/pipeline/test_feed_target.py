import importlib.util
import json
from pathlib import Path
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'warehouse/snowflake'))
import capacity
import telemetry
from warehouse.query_tags import query_tag
from warehouse.run_config import RunConfig


@pytest.mark.parametrize('token,database', [('sfx1119', 'SFX_1119'), ('sfx2220', 'SFX_2220')])
def test_capacity(token, database, monkeypatch):
    monkeypatch.setenv('RUN_TOKEN', token)
    sql = capacity.render()
    assert sql.count('CREATE WAREHOUSE IF NOT EXISTS') == len(capacity.WORKLOADS) == 5
    assert sql.count('AUTO_SUSPEND = 60') == sql.count('WAREHOUSE_SIZE = XSMALL') == 5
    assert sql.count('RESOURCE_MONITOR = ' + database + '_CREDITS') == 5
    assert 'CREDIT_QUOTA = 25' in sql and 'DO SUSPEND_IMMEDIATE' in sql
    for workload in capacity.WORKLOADS:
        assert database + '_' + workload.upper() + '_WH' in sql


@pytest.mark.parametrize('token', ['', 'sfx2220;DROP', 'not-a-run'])
def test_invalid_capacity(token):
    with pytest.raises(ValueError):
        RunConfig(token)


def test_tag_fields_and_overrides(monkeypatch):
    monkeypatch.setenv('RUN_TOKEN', 'sfx2220')
    monkeypatch.setenv('SFX_COMMIT', 'abc123')
    monkeypatch.setenv('SFX_RUN_ID', 'local-test')
    tag = json.loads(query_tag('load', 'copy', {'step': 'fixture', 'commit': 'untrusted'}))
    assert tag == dict(workload='load', phase='copy', commit='abc123',
                       run_id='local-test', run_token='sfx2220', step='fixture')
    with pytest.raises(ValueError):
        query_tag('', 'copy')
    with pytest.raises(ValueError):
        query_tag('load', '')


def test_event_success_failure_empty_and_redaction(tmp_path, monkeypatch):
    path = tmp_path / 'events.jsonl'
    monkeypatch.setenv('SFX_LOG_PATH', str(path))
    @telemetry.operation
    def success():
        return 42
    @telemetry.operation
    def failure():
        raise RuntimeError('must-not-log-secret')
    assert success() == 42
    with pytest.raises(RuntimeError):
        failure()
    events = [json.loads(line) for line in path.read_text().splitlines()]
    assert [e['event'] for e in events] == ['load_started', 'load_success', 'load_started', 'load_failure']
    assert events[-1]['error_type'] == 'RuntimeError'
    assert 'must-not-log-secret' not in path.read_text()
    before = path.read_bytes()
    telemetry.record_checks({'checks': {}})
    assert path.read_bytes() == before
    with pytest.raises(ValueError):
        telemetry.emit('unknown')


def test_quality_events(tmp_path, monkeypatch):
    path = tmp_path / 'quality.jsonl'
    monkeypatch.setenv('SFX_LOG_PATH', str(path))
    result = {'checks': {name: dict(firing=firing, value=.5, threshold=.1)
                         for name, firing in [('load_failure', False), ('row_count_drop', True), ('null_spike', True)]}}
    assert telemetry.record_checks(result) is result
    assert [json.loads(s)['event'] for s in path.read_text().splitlines()] == ['row_count_drop', 'null_spike']


def test_safe_load_message_is_bounded_and_redacted(tmp_path, monkeypatch):
    path = tmp_path / 'events.jsonl'
    monkeypatch.setenv('SFX_LOG_PATH', str(path))
    monkeypatch.setenv('EXAMPLE_PASSWORD', 'private-sample')
    @telemetry.operation
    def failure():
        raise telemetry.SafeLoadError('CUSTOMER_ID count=1 sample=private-sample ' + 'x' * 1200)
    with pytest.raises(telemetry.SafeLoadError):
        failure()
    event = json.loads(path.read_text().splitlines()[-1])
    assert event['event'] == 'load_failure'
    assert len(event['error_message']) == 1000
    assert 'CUSTOMER_ID count=1 sample=[REDACTED]' in event['error_message']
    assert 'private-sample' not in path.read_text()


def test_logging_error_does_not_mask_load(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('SFX_LOG_PATH', str(tmp_path))
    telemetry.emit('load_started')
    assert 'Unable to write operational event' in capsys.readouterr().err


def test_provisioning(monkeypatch):
    spec = importlib.util.spec_from_file_location('feed_config', ROOT / 'observability/pipeline/configure.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv('RUN_TOKEN', 'sfx2220')
    document = yaml.safe_load(module.render())
    assert document['contactPoints'][0]['receivers'][0]['settings']['url'] == '$SFX_ALERT_WEBHOOK_URL'
    rules = document['groups'][0]['rules']
    assert {r['labels']['check'] for r in rules} == {'load_failure', 'row_count_drop', 'null_spike'}
    assert all('run="sfx2220"' in r['data'][0]['model']['expr'] for r in rules)
    compose = (ROOT / 'docker-compose.observability.yml').read_text()
    assert '${SFX_ALERT_WEBHOOK_URL:?' in compose
    assert '127.0.0.1:' in compose
    promtail = yaml.safe_load((ROOT / 'observability/pipeline/promtail.yml').read_text())
    assert {c['job_name'] for c in promtail['scrape_configs']} == {'warehouse', 'runner'}
