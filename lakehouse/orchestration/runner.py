import fcntl
import os
import subprocess
import time
import zlib
from contextlib import contextmanager
from pathlib import Path

from lakehouse.runtime.layout import ROOT, data_root
from warehouse.seed.columns import TABLES

from .graph import business_date, feed_path, ordered


@contextmanager
def namespace_lock():
    root = data_root()
    root.mkdir(parents=True, exist_ok=True)
    with (root / 'pipeline.lock').open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('Namespace already has an active pipeline task/run') from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def task_environment(day):
    business_date(day)
    env = dict(os.environ, BUSINESS_DATE=day, PYTHONPATH=str(ROOT.parent), SPARK_LOCAL_IP='127.0.0.1')
    legacy_ns = env.setdefault('LEGACY_NS', 'sfx-d1110-before')
    if not env.get('TD_PG_DSN'):
        env.setdefault('TD_PG_PORT', str(54500 + zlib.crc32(legacy_ns.encode()) % 1000))
    return env


def command(node, landing, day):
    python = str(ROOT / '.venv/bin/python')
    base = [python, '-m']
    if node['kind'] == 'bronze_ingest':
        tables = [t.name for t in TABLES if t.area == node['domain']]
        return base + ['lakehouse.runtime.ingest', '--landing', str(landing), '--business-date', day, '--tables', *tables]
    if node['kind'] == 'dbt':
        return base + ['lakehouse.runtime.dbt', '--select', node['selector']]
    if node['kind'] == 'parity':
        selected = node['specs'] if 'specs' in node else [node['spec']]
        return base + ['lakehouse.parity', 'run', '--spec', *selected, '--business-date', day]
    if node['kind'] == 'export':
        values = {'python': python, 'business_date': day, 'landing': str(landing), 'data_root': str(data_root())}
        return [part.format_map(values) for part in node['command']]
    raise ValueError('Node has no subprocess command: ' + node['kind'])


def execute(node, landing, day):
    business_date(day)
    if node['kind'] == 'feed_sensor':
        path = feed_path(node, landing, day)
        deadline = time.monotonic() + node['timeout_seconds']
        while not path.is_file():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Landing file not ready: ' + str(path))
            time.sleep(min(node['poke_interval_seconds'], remaining))
    elif node['kind'] != 'noop':
        subprocess.run(command(node, Path(landing).resolve(), day), env=task_environment(day), cwd=ROOT.parent, check=True)


def run(dag, landing, day):
    business_date(day)
    states = {}
    with namespace_lock():
        for node in ordered(dag['nodes']):
            identity = node['id']
            if any(states[dependency] != 'PASS' for dependency in node['depends_on']):
                states[identity] = 'BLOCKED'
            else:
                for attempt in range(node['retries'] + 1):
                    try:
                        execute(node, landing, day)
                        states[identity] = 'PASS'
                        break
                    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
                        print(f'{identity}: attempt {attempt + 1} failed: {exc}', flush=True)
                        if attempt == node['retries']:
                            states[identity] = 'FAIL'
                        else:
                            time.sleep(node['retry_delay_seconds'])
            print(f'{identity}: {states[identity]}', flush=True)
    passed = all(state == 'PASS' for state in states.values())
    print(f'Pipeline {dag["id"]}: {"PASS" if passed else "FAIL"} ({len(states)} tasks)', flush=True)
    return 0 if passed else 1
