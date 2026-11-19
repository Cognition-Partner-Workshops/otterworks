import os
import shlex
from datetime import timedelta
from pathlib import Path

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.sensors.filesystem import FileSensor

from lakehouse.orchestration.graph import PIPELINE, load, logical_business_date
from lakehouse.runtime.layout import ROOT, data_root

DAY = '{{ business_date(logical_date) }}'


def build_dags():
    landing = Path(os.environ.get('SFX_LH_LANDING', data_root() / 'landing')).resolve()
    dags = {}
    for identity, config in load().items():
        with DAG(identity, schedule=config['schedule'],
                 start_date=pendulum.from_format(config['start_date'], 'YYYYMMDD', tz='UTC'),
                 catchup=config['catchup'], max_active_runs=config['max_active_runs'],
                 max_active_tasks=config['max_active_tasks'], is_paused_upon_creation=config['paused'],
                 user_defined_macros={'business_date': logical_business_date},
                 tags=['lakehouse']) as dag:
            tasks = {}
            for node in config['nodes']:
                common = {'task_id': node['id'], 'retries': node['retries'],
                          'retry_delay': timedelta(seconds=node['retry_delay_seconds'])}
                if node['kind'] in ('feed_sensor', 'artifact_sensor'):
                    if node['kind'] == 'feed_sensor':
                        prefix = node.get('landing_prefix', '').replace('{business_date}', DAY)
                        path = landing / prefix / node['domain'] / node['table'] / (DAY + '.psv')
                    else:
                        path = Path(node['path'].format(data_root=data_root(), business_date=DAY))
                    task = FileSensor(filepath=str(path), fs_conn_id='fs_default', mode='reschedule',
                                      timeout=node['timeout_seconds'], poke_interval=node['poke_interval_seconds'],
                                      **common)
                elif node['kind'] == 'noop':
                    task = EmptyOperator(**common)
                else:
                    command = [str(ROOT / '.venv/bin/python'), '-m', 'lakehouse.orchestration', 'execute',
                               '--pipeline', str(PIPELINE), '--dag', identity, '--node', node['id'],
                               '--business-date', DAY, '--landing', str(landing)]
                    task = BashOperator(bash_command=shlex.join(command), append_env=True,
                                        env={'NS': os.environ['NS'], 'PYTHONPATH': str(ROOT.parent),
                                             'SPARK_LOCAL_IP': '127.0.0.1'}, **common)
                tasks[node['id']] = task
            for node in config['nodes']:
                for dependency in node['depends_on']:
                    tasks[dependency] >> tasks[node['id']]
        dags[identity] = dag
    return dags


globals().update(build_dags())
