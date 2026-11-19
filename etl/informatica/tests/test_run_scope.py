import os
from pathlib import Path
import shutil
import subprocess
import zlib

import pytest

from runner import db
from runner.workflow import process_variables

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize('token,namespace', [(None, 'sfx-1119-before'),
                                         ('sfx2220', 'sfx-2220-before'),
                                         ('sfx-d1110-alice', 'sfx-d1110-alice-before')])
def test_default_namespace_reaches_runner_and_make(monkeypatch, token, namespace):
    for key in ('RUN_TOKEN', 'SNOWFLAKE_RUN_TOKEN', 'NS', 'PMROOTDIR'):
        monkeypatch.delenv(key, raising=False)
    if token is not None:
        monkeypatch.setenv('RUN_TOKEN', token)
    assert process_variables()['$PMRootDir'] == str(ROOT / 'etl/informatica/infa_shared' / namespace)
    assert db.default_port() == str(54500 + zlib.crc32(namespace.encode()) % 1000)
    command = ['make', '-n', 'sfx-informatica-run'] + ([f'RUN_TOKEN={token}'] if token else [])
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    assert f'NS={namespace} ' in result.stdout
    assert f'/infa_shared/{namespace} ' in result.stdout


def test_explicit_namespace_and_root_win(monkeypatch, tmp_path):
    monkeypatch.setenv('RUN_TOKEN', 'sfx2220')
    monkeypatch.setenv('NS', 'sfx3330-custom')
    monkeypatch.setenv('PMROOTDIR', str(tmp_path))
    assert process_variables()['$PMRootDir'] == str(tmp_path)
    assert db.default_port() == str(54500 + zlib.crc32(b'sfx3330-custom') % 1000)
    assert db.default_port('explicit') == str(54500 + zlib.crc32(b'explicit') % 1000)


@pytest.fixture
def guarded_commands(tmp_path, monkeypatch):
    directory = tmp_path / 'bin'
    directory.mkdir()
    marker = tmp_path / 'command-ran'
    for name in ('rm', 'runner'):
        executable = directory / name
        executable.write_text(f'#!/bin/sh\nprintf reached > "{marker}"\n')
        executable.chmod(0o755)
    monkeypatch.setenv('PATH', str(directory) + os.pathsep + os.environ['PATH'])
    monkeypatch.delenv('NS', raising=False)
    return tmp_path, marker


@pytest.mark.parametrize('target', ['sfx-informatica-run', 'sfx-informatica-down'])
@pytest.mark.parametrize('arguments', [
    ['RUN_TOKEN=invalid'], ['RUN_TOKEN='], ["RUN_TOKEN=sfx1119'quote"],
    ['RUN_TOKEN=invalid', 'NS=sfx-safe-before'], ['INFA_NS='], ['INFA_NS= '],
    ['NS=..'], ['NS=../other'], ['NS=/'],
])
def test_guard_rejects_invalid_scope(target, arguments, guarded_commands):
    directory, marker = guarded_commands
    result = subprocess.run(['make', target, f'INFA_DIR={directory}', 'INFA_DB=teradata',
                             f'INFA_PY={directory}/bin/runner', 'INFA_WORKFLOWS=sample:job', *arguments],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode != 0
    assert 'RunConfig' in result.stderr or 'nonempty namespace' in result.stderr
    assert 'docker' not in result.stdout and 'rm -rf' not in result.stdout
    assert not marker.exists()


@pytest.mark.parametrize('output,status', [('sfx-1119-before', 7), ('', 0)])
@pytest.mark.parametrize('target', ['sfx-informatica-run', 'sfx-informatica-down'])
def test_run_config_failure_or_empty_output_stops_commands(guarded_commands, monkeypatch, output, status, target):
    tmp_path, marker = guarded_commands
    executable = tmp_path / 'python3'
    executable.write_text(f'#!/bin/sh\nprintf "%s" "{output}"\nexit {status}\n')
    executable.chmod(0o755)
    monkeypatch.setenv('PATH', str(tmp_path) + os.pathsep + os.environ['PATH'])
    result = subprocess.run(['make', target, f'INFA_DIR={tmp_path}', 'INFA_DB=teradata',
                             f'INFA_PY={tmp_path}/bin/runner', 'INFA_WORKFLOWS=sample:job'],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode != 0
    assert 'RunConfig' in result.stderr or 'nonempty namespace' in result.stderr
    assert 'docker' not in result.stdout and 'rm -rf' not in result.stdout
    assert not marker.exists()


def test_valid_run_reaches_runner(guarded_commands):
    directory, marker = guarded_commands
    subprocess.run(['make', 'sfx-informatica-run', 'RUN_TOKEN=sfx2220', f'INFA_DIR={directory}',
                    f'INFA_PY={directory}/bin/runner', 'INFA_WORKFLOWS=sample:job'],
                   cwd=ROOT, capture_output=True, text=True, check=True)
    assert marker.read_text() == 'reached'


@pytest.mark.parametrize('target,expected', [
    ('infra-up', 'docker compose -f docker-compose.infra.yml up -d'),
    ('testdata-setup-schema', 'Creating schema otterworks_Demo_1'),
])
def test_unrelated_targets_ignore_runner_validation(tmp_path, target, expected):
    make = shutil.which('make')
    (tmp_path / 'grep').symlink_to(shutil.which('grep'))
    env = {**os.environ, 'PATH': str(tmp_path)}
    assert shutil.which('python3', path=env['PATH']) is None
    result = subprocess.run([make, '-n', target, 'NS=Demo_1', 'RUN_TOKEN=invalid'],
                            cwd=ROOT, env=env, capture_output=True, text=True, check=True)
    assert expected in result.stdout
    assert 'RunConfig failed' not in result.stderr and 'INFA_NS' not in result.stderr


def test_teardown_removes_only_the_selected_child(tmp_path):
    parent = tmp_path / 'infa_shared'
    selected = parent / 'sfx-2220-before'
    sibling = parent / 'sfx-1119-before'
    selected.mkdir(parents=True)
    sibling.mkdir()
    (selected / 'session.log').write_text('selected')
    (sibling / 'session.log').write_text('retained')
    subprocess.run(['make', 'sfx-informatica-down', 'RUN_TOKEN=sfx2220', 'INFA_DB=teradata',
                    f'INFA_DIR={tmp_path}'], cwd=ROOT, capture_output=True, text=True, check=True)
    assert not selected.exists()
    assert parent.is_dir() and (sibling / 'session.log').read_text() == 'retained'
