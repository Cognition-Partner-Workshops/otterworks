import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from jinja2 import Environment
import yaml

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from warehouse.run_config import RunConfig

PROJECT = REPO / 'warehouse/dbt'
SOURCE_NAMES = {'unt3_pc_src', 'unt4_archive_fixture', 'unt5_pc_src', 'unt5_fixture',
                'unt6_pc_src', 'unt6_fixture', 'unt7_pc_src', 'unt7_fixture',
                'unt8_pc_src', 'unt8_fixture'}


@pytest.mark.parametrize('token', ['sfx1119', 'sfx2220'])
def test_fixture_source_databases_follow_run(token, tmp_path):
    config = RunConfig(token)
    project = tmp_path / 'project'
    shutil.copytree(PROJECT, project, ignore=shutil.ignore_patterns('target', 'logs'))
    for path in project.rglob('*'):
        if path.is_file() and path.suffix in ('.sql', '.yml', '.yaml'):
            path.write_text(config.render(path.read_text()))
    env = {k: v for k, v in os.environ.items() if not k.startswith('SNOWFLAKE_')}
    env.update(config.environment())
    env.update({f'SNOWFLAKE_{key}': 'offline_dummy' for key in ['ACCOUNT', 'USER', 'ROLE', 'DATABASE']})
    env.update(DBT_ENV_SECRET_SNOWFLAKE_PRIVATE_KEY='offline_dummy',
               DBT_SEND_ANONYMOUS_USAGE_STATS='false', SFX_QUERY_TAG='{}')
    subprocess.run([str(Path(sys.executable).with_name('dbt')), 'parse', '--no-partial-parse',
                    '--project-dir', str(project), '--profiles-dir', str(project)],
                   env=env, check=True, capture_output=True, text=True)
    manifest = json.loads((project / 'target/manifest.json').read_text())
    sources = [s for s in manifest['sources'].values() if s['source_name'] in SOURCE_NAMES]
    assert {s['source_name'] for s in sources} == SOURCE_NAMES
    assert {s['database'] for s in sources} == {config.database}


def test_sources_default_to_profile_without_run_environment():
    for path in (PROJECT / 'models/pc').rglob('*.yml'):
        for source in yaml.safe_load(path.read_text()).get('sources', []):
            if source['name'] in SOURCE_NAMES:
                database = Environment().from_string(source['database']).render(
                    env_var=lambda key, default: default, target={'database': 'PROFILE_DATABASE'})
                assert database == 'PROFILE_DATABASE'
