import json
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
    result = collect(tmp_path, 'warehouse', [json.dumps({'run': run, 'event': 'load_failure'})],
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
