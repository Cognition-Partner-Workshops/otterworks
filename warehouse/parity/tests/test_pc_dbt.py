import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

from jinja2 import Environment

WAREHOUSE = Path(__file__).resolve().parents[2]


def test_pc_resolved_relations_and_comments(tmp_path):
    project = tmp_path / 'dbt'
    shutil.copytree(WAREHOUSE / 'dbt', project, ignore=shutil.ignore_patterns('target', 'logs'))
    for area, materialized in [('billing', 'table'), ('content', 'view'), ('audit', 'incremental')]:
        (project / 'models/pc' / area / f'pc_{area}__probe.sql').write_text(
            "{{ config(materialized='" + materialized + "') }} select 1 as id")
    env = {k: v for k, v in os.environ.items() if not k.startswith('SNOWFLAKE_')}
    env.update({f'SNOWFLAKE_{k}': 'offline_dummy' for k in ['ACCOUNT', 'USER', 'ROLE', 'DATABASE']})
    env.update(DBT_ENV_SECRET_SNOWFLAKE_PRIVATE_KEY='offline_dummy',
               DBT_SEND_ANONYMOUS_USAGE_STATS='false', SFX_QUERY_TAG='{}')
    subprocess.run([str(Path(sys.executable).with_name('dbt')), 'parse', '--no-partial-parse',
                    '--project-dir', str(project), '--profiles-dir', str(project)],
                   env=env, check=True, capture_output=True, text=True)
    manifest = json.loads((project / 'target/manifest.json').read_text())
    for area in ['billing', 'content', 'audit']:
        node = manifest['nodes'][f'model.sfx_warehouse.pc_{area}__probe']
        assert node['schema'] == 'PC_' + area.upper()
        assert node['alias'] == 'PROBE'
        assert node['config']['post-hook'][0]['sql'] == '{{ pc_relation_comment() }}'
        materialized = node['config']['materialized']
        module = Environment(extensions=['jinja2.ext.do']).from_string(
            (project / 'macros/pc_relation_comment.sql').read_text()).make_module({
                'model': SimpleNamespace(config=SimpleNamespace(materialized=materialized)),
                'this': f'SFX_D1110_AFTER.PC_{area.upper()}.PROBE'})
        sql = module.pc_relation_comment().strip()
        assert "is 'run_token=sfx-d1110 expires=2026-11-24'" in sql
        assert f"comment on {'view' if materialized == 'view' else 'table'}" in sql
        print(f"Resolved: {node['schema']}.{node['alias']} ({materialized}); {sql}")
    unchanged = manifest['nodes']['model.sfx_warehouse.stg_billing_payment'] if 'model.sfx_warehouse.stg_billing_payment' in manifest['nodes'] else next(
        n for n in manifest['nodes'].values() if n['resource_type'] == 'model' and n['fqn'][1] == 'staging')
    assert unchanged['alias'] == unchanged['name']
    hooks = [n['raw_code'] for n in manifest['nodes'].values() if n['resource_type'] == 'operation']
    assert '{{ pc_finalize_comments(results) }}' in hooks
