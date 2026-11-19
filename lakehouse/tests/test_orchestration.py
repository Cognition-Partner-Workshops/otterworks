import copy
import subprocess
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

import pytest
import yaml

from lakehouse.coverage.inventory import discover
from lakehouse.orchestration import graph, runner
from lakehouse.orchestration.__main__ import main
from lakehouse.runtime import dbt
from lakehouse.runtime.layout import ROOT
from warehouse.seed.columns import TABLES


STAGING = 'cron_entry:warehouse/teradata/jobs/daily_chain#stage=staging'


def node(identity, dependencies=(), kind='noop', **options):
    return dict(id=identity, kind=kind, depends_on=list(dependencies), retries=0,
                retry_delay_seconds=0, legacy_objects=[], **options)


def test_pipeline_contract_and_staging_replacement():
    dags = graph.load()
    assert {'lakehouse_daily', 'lakehouse_hourly', 'lakehouse_documents_folder_manual',
                         'lakehouse_documents_compaction', 'lakehouse_docs_storage_by_owner',
                         'lakehouse_docs_share_activity', 'lakehouse_docs_search_log_parse',
                         'lakehouse_docs_tag_normalize', 'lakehouse_docs_folder_tree_walk',
                         'lakehouse_doc_share_graph_reach', 'lakehouse_collab_session_sessionize',
                         'lakehouse_doc_version_diff_stats', 'lakehouse_file_object_binary_extract',
                         'lakehouse_search_reindex_weekly', 'lakehouse_storage_cleanup_daily',
                         'lakehouse_documents_external_fixture'} <= set(dags)
    daily = dags['lakehouse_daily']
    nodes = {node['id']: node for node in daily['nodes']}
    sensors = [n for n in nodes.values() if n['kind'] == 'feed_sensor' and not n.get('landing_prefix')]
    assert {(n['domain'], n['table']) for n in sensors} == {(t.area, t.name) for t in TABLES}
    assert len(sensors) == len(TABLES)
    for domain in ('billing', 'documents', 'users', 'audit'):
        bronze = nodes['bronze_' + domain]
        assert set(bronze['depends_on']) == {n['id'] for n in sensors if n['domain'] == domain}
        assert bronze['id'] in nodes['dbt_' + domain]['depends_on']
        assert set(nodes['dbt_' + domain]['depends_on']) <= nodes.keys()
        assert nodes['dbt_' + domain]['selector'] == 'tag:' + domain
    replacing = [n for n in nodes.values() if STAGING in n['legacy_objects']]
    assert {n['domain'] for n in replacing} == {t.area for t in TABLES}
    assert set().union(*(set(n['legacy_objects']) for n in replacing)) - {STAGING} == {
        key for key in discover() if key.startswith(('fastload:', 'tpt:'))}
    assert 'dbt_billing' in nodes['parity_customer_account']['depends_on']
    config = yaml.safe_load((ROOT / 'dbt/dbt_project.yml').read_text())['models']['otterworks_lakehouse']
    for layer in ('silver', 'gold'):
        for domain in ('billing', 'documents', 'users', 'audit'):
            assert config[layer][domain]['+tags'] == [domain]
            assert config[layer][domain]['+schema'] == layer + '_' + domain


@pytest.mark.parametrize('mutation,error', [
    (lambda d: d['dags'][0]['nodes'][0].update(depends_on=['unknown']), 'Unknown dependencies'),
    (lambda d: d['dags'][0]['nodes'][0].update(depends_on=['parity_customer_account']), 'cycle'),
    (lambda d: d['dags'][0]['nodes'][0].update(legacy_objects=['missing:object']), 'Unknown legacy ids'),
    (lambda d: d['dags'][0]['nodes'][0].update(retries=-1), 'retries'),
    (lambda d: d['dags'][0]['nodes'][0].update(retry_delay_seconds=True), 'retry_delay'),
    (lambda d: d['dags'][0]['nodes'][0].update(kind='missing'), 'Unknown node kind'),
    (lambda d: d['dags'][0]['nodes'][0].update(table='MISSING'), 'Unknown feed'),
    (lambda d: d['dags'][0]['nodes'][0].update(timeout_seconds=0), 'timeout_seconds'),
    (lambda d: next(n for n in d['dags'][0]['nodes'] if n['kind'] == 'parity' and 'spec' in n).update(
        spec='missing'), 'Unknown parity'),
    (lambda d: d['dags'][0]['nodes'].append(copy.deepcopy(d['dags'][0]['nodes'][0])), 'Duplicate node'),
    (lambda d: d['dags'][0].update(schedule='@monthly'), 'schedule'),
    (lambda d: d['dags'][0].update(max_active_tasks=2), 'one active'),
    (lambda d: d['dags'][0].update(nodes=[]), 'nonempty nodes'),
    (lambda d: d.update(dags=[]), 'nonempty dags'),
])
def test_invalid_pipeline(tmp_path, mutation, error):
    document = yaml.safe_load(graph.PIPELINE.read_text())
    mutation(document)
    path = tmp_path / 'pipeline.yaml'
    path.write_text(yaml.safe_dump(document))
    with pytest.raises(ValueError, match=error):
        graph.load(path)


def test_order_and_logical_business_date():
    assert [n['id'] for n in graph.ordered([node('c', ['b']), node('b', ['a']), node('a')])] == ['a', 'b', 'c']
    assert graph.ordered([]) == []
    assert graph.logical_business_date(datetime(2027, 1, 1, tzinfo=timezone.utc)) == '20261231'
    assert graph.logical_business_date(datetime(2026, 3, 1, 1, tzinfo=timezone(timedelta(hours=2)))) == '20260227'
    with pytest.raises(ValueError, match='timezone-aware'):
        graph.logical_business_date(datetime(2026, 1, 1))
    for day in ('20260230', '2026-01-01', None):
        with pytest.raises(ValueError):
            graph.business_date(day)


def test_readiness_present_empty_missing_and_arriving(tmp_path, monkeypatch):
    sensor = node('feed', kind='feed_sensor', domain='billing', table='CUSTOMER_ACCOUNT',
                  timeout_seconds=2, poke_interval_seconds=1)
    day = '20261109'
    path = graph.feed_path(sensor, tmp_path, day)
    path.parent.mkdir(parents=True)
    path.write_text('')
    runner.execute(sensor, tmp_path, day)
    path.unlink()
    clock = iter([0, 0, 2])
    monkeypatch.setattr(runner.time, 'monotonic', lambda: next(clock))
    monkeypatch.setattr(runner.time, 'sleep', lambda _: None)
    with pytest.raises(TimeoutError, match='not ready'):
        runner.execute(sensor, tmp_path, day)
    monkeypatch.setattr(runner.time, 'monotonic', lambda: 0)
    monkeypatch.setattr(runner.time, 'sleep', lambda _: path.write_text('ready'))
    runner.execute(sensor, tmp_path, day)


def test_command_environment_and_exports(tmp_path, monkeypatch):
    monkeypatch.setenv('NS', 'test-orchestration')
    monkeypatch.delenv('TD_PG_DSN', raising=False)
    monkeypatch.delenv('TD_PG_PORT', raising=False)
    monkeypatch.setenv('LEGACY_NS', 'sfx-d1110-before')
    assert runner.task_environment('20261109')['TD_PG_PORT'] == '55395'
    monkeypatch.setenv('TD_PG_PORT', '1234')
    monkeypatch.setenv('TD_PG_HOST', 'ci-postgres')
    assert runner.task_environment('20261109')['TD_PG_PORT'] == '1234'
    assert runner.task_environment('20261109')['TD_PG_HOST'] == 'ci-postgres'
    monkeypatch.delenv('TD_PG_PORT')
    monkeypatch.setenv('TD_PG_DSN', 'dbname=example')
    assert 'TD_PG_PORT' not in runner.task_environment('20261109')
    bronze = runner.command(node('bronze', kind='bronze_ingest', domain='billing'), tmp_path, '20261109')
    assert set(bronze[bronze.index('--tables') + 1:]) == {t.name for t in TABLES if t.area == 'billing'}
    assert runner.command(node('dbt', kind='dbt', selector='tag:billing'), tmp_path, '20261109')[-2:] == ['--select', 'tag:billing']
    assert runner.command(node('parity', kind='parity', spec='billing.customer_account'), tmp_path, '20261109')[-3:] == ['billing.customer_account', '--business-date', '20261109']
    export = node('export', kind='export', command=['{python}', '-c', "print('ok')", '{business_date}', '{landing}'])
    calls = []
    monkeypatch.setattr(runner.subprocess, 'run', lambda argv, **kwargs: calls.append((argv, kwargs)))
    runner.execute(export, tmp_path / 'with spaces', '20261109')
    assert calls[0][0][-2:] == ['20261109', str(tmp_path / 'with spaces')]
    assert calls[0][1]['check'] is True and 'shell' not in calls[0][1]


def test_retries_block_descendants_continue_independent_and_no_overlap(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, 'data_root', lambda: tmp_path)
    with runner.namespace_lock():
        with pytest.raises(RuntimeError, match='active pipeline'):
            with runner.namespace_lock():
                pass
    tasks = [node('a'), node('b', ['a']), node('independent')]
    tasks[0]['retries'] = 1
    calls = []
    def execute(current, *_):
        calls.append(current['id'])
        if current['id'] == 'a':
            raise subprocess.CalledProcessError(1, ['broken'])
    monkeypatch.setattr(runner, 'execute', execute)
    monkeypatch.setattr(runner.time, 'sleep', lambda _: None)
    assert runner.run({'id': 'example', 'nodes': tasks}, tmp_path, '20261109') == 1
    assert calls == ['a', 'a', 'independent']
    calls.clear()
    monkeypatch.setattr(runner, 'execute', lambda current, *_: calls.append(current['id']))
    assert runner.run({'id': 'example', 'nodes': tasks}, tmp_path, '20261109') == 0
    assert calls == ['a', 'independent', 'b']


def test_dbt_selector_passed_to_runner(monkeypatch):
    monkeypatch.setattr('sys.argv', ['dbt', '--select', 'tag:billing'])
    monkeypatch.setenv('BUSINESS_DATE', '20261109')
    monkeypatch.setenv('NS', 'test-orchestration')
    calls = []
    stopped = []
    monkeypatch.setattr(dbt, 'create_session', lambda: SimpleNamespace(stop=lambda: stopped.append(True)))
    monkeypatch.setattr(dbt, 'dbtRunner', lambda: SimpleNamespace(invoke=lambda args: calls.append(args) or SimpleNamespace(success=True)))
    dbt.main()
    assert calls[0][-2:] == ['--select', 'tag:billing'] and stopped == [True]


def test_cli_check_and_invalid_graph(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr('sys.argv', ['orchestration', 'check'])
    assert main() == 0
    dags = graph.load()
    task_count = sum(len(dag['nodes']) for dag in dags.values())
    assert f'{len(dags)} DAGs, {task_count} tasks, valid' in capsys.readouterr().out
    path = tmp_path / 'empty.yaml'
    path.write_text('{}')
    monkeypatch.setattr('sys.argv', ['orchestration', 'check', '--pipeline', str(path)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


@pytest.mark.parametrize('execute_dag', ['0', '1'])
def test_airflow_make_ci_plan(execute_dag, monkeypatch):
    monkeypatch.setenv('TD_PG_PORT', '5432')
    result = subprocess.run(['make', '-Bn', 'sfx-lakehouse-airflow-test', 'NS=test-ci',
                             'SFX_LH_AF_DAG_TEST=' + execute_dag],
                            cwd=ROOT.parent, text=True, capture_output=True, check=True)
    assert '-m pytest -q lakehouse/airflow/tests' in result.stdout
    assert 'TD_PG_PORT="5432"' in result.stdout
    assert 'docker' not in result.stdout.lower()
    for command in ('-m pip install -r lakehouse/requirements.txt',
                    'airflow db migrate', 'airflow dags test lakehouse_daily'):
        assert (command in result.stdout) == (execute_dag == '1')


@pytest.mark.parametrize('execute_dag', ['', '2'])
def test_airflow_make_invalid_mode(execute_dag):
    result = subprocess.run(['make', 'sfx-lakehouse-airflow-test', 'NS=test-ci',
                             '-o', 'lakehouse/.venv-airflow/.requirements',
                             'SFX_LH_AF_DAG_TEST=' + execute_dag],
                            cwd=ROOT.parent, text=True, capture_output=True)
    assert result.returncode != 0
    assert '-m pytest' not in result.stdout
