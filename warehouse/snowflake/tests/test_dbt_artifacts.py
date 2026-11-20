import argparse
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_dbt


@pytest.fixture
def project(tmp_path, monkeypatch):
    source = tmp_path / 'dbt'
    models = source / 'models'
    models.mkdir(parents=True)
    (models / 'example.sql').write_text("select '__RUN_DATABASE__' as name")
    (source / 'dbt_project.yml').write_text('name: example')
    monkeypatch.setattr(run_dbt, 'ROOT', tmp_path / 'snowflake')
    monkeypatch.setenv('RUN_TOKEN', 'sfx2220')
    monkeypatch.setenv('SFX_COMMIT', 'test')
    monkeypatch.setenv('SNOWFLAKE_PRIVATE_KEY', 'test-only')
    monkeypatch.delenv('SFX_SPARK_JOB', raising=False)
    monkeypatch.setattr(sys, 'argv', ['run_dbt.py', 'build', '--select', 'example'])
    return source


@pytest.mark.parametrize('failed', [False, True])
def test_execution_artifacts_outlive_rendered_project(project, monkeypatch, failed):
    rendered = []

    def execute(command, **kwargs):
        path = Path(command[command.index('--project-dir') + 1])
        rendered.append(path)
        assert (path / 'models/example.sql').read_text() == "select 'SFX_2220' as name"
        for flag, default, filename, content in [
            ('--target-path', path / 'target', 'run_results.json', '{"results": []}'),
            ('--log-path', path / 'logs', 'dbt.log', 'offline fixture execution')
        ]:
            destination = Path(command[command.index(flag) + 1]) if flag in command else default
            destination.mkdir(parents=True, exist_ok=True)
            (destination / filename).write_text(content)
        if failed:
            raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(run_dbt.subprocess, 'run', execute)
    if failed:
        with pytest.raises(subprocess.CalledProcessError):
            run_dbt.main()
    else:
        run_dbt.main()
    assert not rendered[0].exists()
    assert json.loads((project / 'target/run_results.json').read_text()) == {'results': []}
    assert (project / 'logs/dbt.log').read_text() == 'offline fixture execution'


def test_no_artifacts_fabricated(project, monkeypatch):
    monkeypatch.setattr(run_dbt.subprocess, 'run', lambda *args, **kwargs: None)
    run_dbt.main()
    assert not (project / 'target/run_results.json').exists()
    assert not (project / 'logs/dbt.log').exists()
    assert not list((project / 'target').glob('sfx2220-*'))


@pytest.mark.parametrize('value', [
    'staging.billing', 'path:models/pc/billing', 'path:models/spark/billing_job', 'pc_content__app_user',
    '+tag:nightly+', '@source:raw.orders', 'staging.billing,tag:daily staging.audit', 'models/*.sql', '2+example+3'])
def test_selection_accepts_dbt_selectors(value):
    assert run_dbt.selection(value) == value


@pytest.mark.parametrize('value', [
    '', '--profiles-dir=/tmp/evil', '-s', 'example --target prod', 'example;touch /tmp/pwned',
    'example$(id)', '`id`', 'example|sh', "example'", 'example\n--target', 'a,--vars={}'])
def test_selection_rejects_option_and_shell_injection(value):
    with pytest.raises(Exception):
        run_dbt.selection(value)


@pytest.mark.parametrize('flag, value', [
    ('--select', '--profiles-dir=/tmp/evil'), ('--select', 'example --target prod'),
    ('--select', 'example;touch /tmp/pwned'), ('--phase', '--target=prod'), ('--load-date', '2026-11-10')])
def test_untrusted_cli_values_never_reach_dbt(project, monkeypatch, flag, value):
    calls = []
    monkeypatch.setattr(run_dbt.subprocess, 'run', lambda *args, **kwargs: calls.append(args))
    monkeypatch.setattr(sys, 'argv', ['run_dbt.py', 'build', flag + '=' + value])
    with pytest.raises(SystemExit) as raised:
        run_dbt.main()
    assert raised.value.code == 2
    assert calls == []


def test_dbt_argv_is_fixed_shape(project, monkeypatch):
    calls = []
    monkeypatch.setattr(run_dbt.subprocess, 'run', lambda argv, **kwargs: calls.append((argv, kwargs)))
    monkeypatch.setattr(sys, 'argv', ['run_dbt.py', 'build', '--select', 'path:models/pc/billing',
                                      '--phase', 'idempotence', '--load-date', '20261110'])
    run_dbt.main()
    (argv, kwargs), = calls
    assert Path(argv[0]).name == 'dbt' and argv[1] == 'build'
    assert argv[argv.index('--select') + 1] == 'path:models/pc/billing'
    assert json.loads(argv[argv.index('--vars') + 1]) == {'phase': 'idempotence', 'load_date': '20261110'}
    assert kwargs.get('shell', False) is False and kwargs['check'] is True
    assert [a for a in argv if a.startswith('-')] == [
        '--project-dir', '--profiles-dir', '--target-path', '--log-path', '--select', '--vars']


def test_dbt_argv_revalidates_selection():
    with pytest.raises(argparse.ArgumentTypeError):
        run_dbt.dbt_argv('build', 'p', 't', 'l', '--profiles-dir=/tmp/evil')
    with pytest.raises(ValueError):
        run_dbt.dbt_argv('run-operation', 'p', 't', 'l')
