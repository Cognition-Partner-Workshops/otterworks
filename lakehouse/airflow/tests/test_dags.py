from pathlib import Path

import pendulum
from airflow.models import DagBag
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.sensors.filesystem import FileSensor

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
            if node['kind'] == 'feed_sensor':
                assert isinstance(task, FileSensor)
                assert Path(task.filepath).is_absolute()
                assert task.filepath.endswith('/' + node['table'] + '/20261109.psv')
                assert task.mode == 'reschedule' and task.timeout == node['timeout_seconds']
            elif node['kind'] == 'noop':
                assert isinstance(task, EmptyOperator)
            else:
                assert isinstance(task, BashOperator)
                assert '--business-date 20261109' in task.bash_command or "--business-date '20261109'" in task.bash_command
                assert node['id'] in task.bash_command
    assert logical_business_date(pendulum.datetime(2027, 1, 1, tz='UTC')) == '20261231'
