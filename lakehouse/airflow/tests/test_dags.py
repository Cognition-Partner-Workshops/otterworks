from pathlib import Path
import shlex

import pendulum
from airflow.models import DagBag
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.sensors.filesystem import FileSensor
from airflow.timetables.base import TimeRestriction

from lakehouse.orchestration.graph import load, logical_business_date
from lakehouse.runtime.layout import ROOT


def test_dagbag_contract_and_templates():
    bag = DagBag(dag_folder=str(ROOT / 'airflow/dags'), include_examples=False, safe_mode=False)
    assert bag.import_errors == {}
    expected = load()
    assert set(bag.dags) == set(expected)
    for identity, config in expected.items():
        dag = bag.dags[identity]
        assert dag.catchup and dag.max_active_runs == 1 and dag.max_active_tasks == 1
        assert str(dag.timezone) == 'UTC'
        assert dag.schedule_interval == config['schedule']
        assert dag.is_paused_upon_creation == config['paused']
        assert set(dag.task_ids) == {node['id'] for node in config['nodes']}
        for node in config['nodes']:
            task = dag.get_task(node['id'])
            assert task.upstream_task_ids == set(node['depends_on'])
            assert task.retries == node['retries']
            assert task.retry_delay.total_seconds() == node['retry_delay_seconds']
            logical_date = pendulum.datetime(2026, 11, 10, tz='UTC')
            task.render_template_fields({'logical_date': logical_date}, jinja_env=dag.get_template_env())
            if node['kind'] in ('feed_sensor', 'artifact_sensor'):
                assert isinstance(task, FileSensor)
                assert Path(task.filepath).is_absolute()
                if node['kind'] == 'feed_sensor':
                    assert task.filepath.endswith('/' + node['table'] + '/20261109.psv')
                else:
                    assert task.filepath.endswith('/20261109/docs_event_export_hourly/_SUCCESS')
                if node.get('landing_prefix'):
                    assert '/' + node['landing_prefix'].format(business_date='20261109') + '/' in task.filepath
                assert task.mode == 'reschedule' and task.timeout == node['timeout_seconds']
            elif node['kind'] == 'noop':
                assert isinstance(task, EmptyOperator)
            else:
                assert isinstance(task, BashOperator)
                assert '--business-date 20261109' in task.bash_command or "--business-date '20261109'" in task.bash_command
                assert node['id'] in task.bash_command
    assert logical_business_date(pendulum.datetime(2027, 1, 1, tz='UTC')) == '20261231'


def test_audit_owned_schedule_and_dependencies():
    bag = DagBag(dag_folder=str(ROOT / 'airflow/dags'), include_examples=False, safe_mode=False)
    assert bag.import_errors == {}
    daily = bag.dags['lakehouse_daily']
    weekly = bag.dags['lakehouse_audit_weekly']
    assert daily.schedule_interval == '@daily' and weekly.schedule_interval == '@weekly'
    for dag in (daily, weekly):
        assert str(dag.timezone) == 'UTC' and dag.catchup
        assert dag.max_active_runs == dag.max_active_tasks == 1
        assert not dag.is_paused_upon_creation
    assert daily.get_task('dbt_audit').upstream_task_ids >= {
        'bronze_audit', 'bronze_users', 'bronze_documents', 'dbt_billing'}
    assert daily.get_task('audit_spark').upstream_task_ids == {'dbt_audit', 'bronze_users'}
    assert daily.get_task('audit_delta_optimize').upstream_task_ids == {'audit_spark'}
    assert daily.get_task('export_audit_reconciliation').upstream_task_ids == {'dbt_audit'}
    archive = weekly.get_task('audit_weekly_archive')
    assert not archive.upstream_task_ids and archive.retries == 1
    assert all(task.trigger_rule == 'all_success' for task in (
        daily.get_task('dbt_audit'), daily.get_task('audit_spark'), archive))
    assert not any('audit' in task_id and 'informatica' in task_id for task_id in daily.task_ids)
    logical_date = pendulum.datetime(2026, 11, 15, tz='UTC')
    archive.render_template_fields({'logical_date': logical_date}, jinja_env=weekly.get_template_env())
    argv = shlex.split(archive.bash_command)
    assert argv[argv.index('--business-date') + 1] == '20261114'
    interval = weekly.timetable.next_dagrun_info(
        last_automated_data_interval=None,
        restriction=TimeRestriction(
            earliest=pendulum.datetime(2026, 11, 10, tz='UTC'), latest=None, catchup=True))
    assert interval.data_interval.start == logical_date
    assert interval.run_after == logical_date.add(weeks=1)
