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
