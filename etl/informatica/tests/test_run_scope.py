import os
from pathlib import Path
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
