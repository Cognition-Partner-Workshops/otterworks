import json
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import subprocess
import time

import pytest
import yaml

CONFIG = Path(__file__).with_name('promtail.yml')
pytestmark = pytest.mark.skipif(os.getenv('SFX_PROMTAIL_TEST') != '1',
                                reason='Set SFX_PROMTAIL_TEST=1 to exercise the Promtail container')


def collect(tmp_path, job_name, lines, filename):
    config = yaml.safe_load(CONFIG.read_text().replace('${RUN_TOKEN}', 'sfx1119'))
    job = next(job for job in config['scrape_configs'] if job['job_name'] == job_name)
    job['static_configs'][0]['labels']['filename'] = filename
    config['scrape_configs'] = [job]
    config['positions']['filename'] = '/tmp/positions.yml'
    path = tmp_path / 'promtail.yml'
    path.write_text(yaml.safe_dump(config))
    with subprocess.Popen(['docker', 'run', '--rm', '-i', '--network', 'none',
                             '-v', f'{path}:/config.yml:ro', 'grafana/promtail:3.4.2',
                             '-config.file=/config.yml', '-stdin', '-dry-run'],
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True) as process:
        startup = []
        for line in process.stdout:
            startup.append(line)
            if not line.strip():
                break
        process.stdin.write('\n'.join(lines) + '\n')
        process.stdin.flush()
        time.sleep(.2)
        stdout, stderr = process.communicate(timeout=30)
        assert process.returncode == 0, stderr
        assert 'error creating promtail' not in stderr
    return re.sub(r'\x1b\[[0-9;]*m', '', ''.join(startup) + stdout)


@pytest.mark.parametrize('run', ['sfx1119', 'sfx2220', 'sfx-d1110-alice'])
def test_warehouse_uses_event_run(tmp_path, run):
    result = collect(tmp_path, 'warehouse', [json.dumps({'run': run, 'event': 'load_failure',
                                                       'timestamp': '2026-11-19T16:26:10Z'})],
                     '/logs/warehouse/pipeline.jsonl')
    assert f'run="{run}"' in result
    if run != 'sfx1119':
        assert 'run="sfx1119"' not in result


@pytest.mark.parametrize('namespace,run', [('sfx-1119-before', 'sfx1119'),
                                         ('sfx-2220-after', 'sfx2220'),
                                         ('sfx-d1110-before', 'sfx-d1110'),
                                         ('sfx-d1110-alice-after', 'sfx-d1110-alice')])
def test_runner_uses_namespace_run(tmp_path, namespace, run):
    result = collect(tmp_path, 'runner', ['2026-11-19 16:26:10 : ERROR : failure'],
                     f'/logs/runner/{namespace}/SessLogs/session.log')
    assert f'run="{run}"' in result
    if run != 'sfx1119':
        assert 'run="sfx1119"' not in result


@pytest.mark.parametrize('lines', [[], ['not json'], ['{}'], ['{"run": ""}']])
def test_unattributed_warehouse_events_are_dropped(tmp_path, lines):
    result = collect(tmp_path, 'warehouse', lines, '/logs/warehouse/pipeline.jsonl')
    assert 'component="warehouse"' not in result


def test_unattributed_runner_events_are_dropped(tmp_path):
    result = collect(tmp_path, 'runner', ['2026-11-19 16:26:10 : ERROR : failure'],
                     '/logs/runner/unknown/SessLogs/session.log')
    assert 'component="runner"' not in result


@pytest.mark.parametrize('job,line,filename,expected', [
    ('warehouse', json.dumps({'run': 'sfx1119', 'timestamp': '2020-01-02T03:04:05.123456+00:00',
                             'event': 'load_failure'}), '/logs/warehouse/pipeline.jsonl',
     '2020-01-02T03:04:05.123456+00:00'),
    ('warehouse', json.dumps({'run': 'sfx1119', 'timestamp': '2020-01-02T05:04:05+02:00',
                             'event': 'load_failure'}), '/logs/warehouse/pipeline.jsonl',
     '2020-01-02T03:04:05+00:00'),
    ('runner', '2020-01-02 03:04:05 : ERROR : old failure',
     '/logs/runner/sfx-1119-before/SessLogs/session.log', '2020-01-02T03:04:05+00:00'),
])
def test_retained_logs_keep_event_timestamps(tmp_path, job, line, filename, expected):
    result = collect(tmp_path, job, [line], filename)
    entry = next(line for line in result.splitlines() if f'component="{job}"' in line)
    actual = datetime.fromisoformat(entry.partition('{')[0].strip().replace('Z', '+00:00'))
    assert actual.astimezone(timezone.utc) == datetime.fromisoformat(expected)


@pytest.mark.parametrize('timestamp', [None, '', 'not-a-date', '2020-02-30T03:04:05Z'])
def test_missing_or_invalid_warehouse_timestamp_is_dropped(tmp_path, timestamp):
    result = collect(tmp_path, 'warehouse', [json.dumps({'run': 'sfx1119', 'timestamp': timestamp,
                                                       'event': 'load_failure'})],
                     '/logs/warehouse/pipeline.jsonl')
    assert 'component="warehouse"' not in result


@pytest.mark.parametrize('line', ['', 'not-a-date : ERROR : failure',
                                '2020-02-30 03:04:05 : ERROR : failure'])
def test_missing_or_invalid_runner_timestamp_is_dropped(tmp_path, line):
    result = collect(tmp_path, 'runner', [line], '/logs/runner/sfx-1119-before/SessLogs/session.log')
    assert 'component="runner"' not in result
