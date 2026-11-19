import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from lakehouse.coverage.inventory import discover
from lakehouse.parity.spec import discover as discover_specs
from lakehouse.runtime.layout import DOMAINS, ROOT
from warehouse.seed.columns import TABLES

PIPELINE = ROOT / 'orchestration/pipeline.yaml'
KINDS = {'feed_sensor', 'bronze_ingest', 'dbt', 'parity', 'export', 'noop'}


def business_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{8}', value):
        raise ValueError('business-date must be YYYYMMDD')
    return datetime.strptime(value, '%Y%m%d').date()


def logical_business_date(logical_date):
    if logical_date.tzinfo is None:
        raise ValueError('logical date must be timezone-aware')
    return (logical_date.astimezone(timezone.utc).date() - timedelta(days=1)).strftime('%Y%m%d')


def ordered(nodes):
    remaining = {node['id']: node for node in nodes}
    result = []
    done = set()
    while remaining:
        ready = sorted(key for key, node in remaining.items() if set(node['depends_on']) <= done)
        if not ready:
            raise ValueError('Pipeline contains a cycle or unknown dependency')
        for key in ready:
            result.append(remaining.pop(key))
            done.add(key)
    return result


def load(path=PIPELINE, inventory=None, specs=None):
    document = yaml.safe_load(Path(path).read_text())
    if not isinstance(document, dict) or not isinstance(document.get('dags'), list) or not document['dags']:
        raise ValueError('Pipeline requires a nonempty dags list')
    inventory = discover() if inventory is None else inventory
    specs = discover_specs() if specs is None else specs
    dags = {}
    for dag in document['dags']:
        if not isinstance(dag, dict) or not re.fullmatch(r'[a-z][a-z0-9_]*', str(dag.get('id', ''))):
            raise ValueError('Invalid DAG id')
        if dag['id'] in dags:
            raise ValueError('Duplicate DAG id: ' + dag['id'])
        if dag.get('schedule') not in ('@daily', '@hourly') or dag.get('timezone') != 'UTC':
            raise ValueError('DAG schedule must be @daily/@hourly in UTC')
        business_date(dag.get('start_date'))
        if dag.get('catchup') is not True or dag.get('max_active_runs') != 1 or dag.get('max_active_tasks') != 1:
            raise ValueError('DAGs require catchup and one active run/task for embedded Derby')
        if not isinstance(dag.get('paused'), bool):
            raise ValueError('DAG paused must be boolean')
        nodes = dag.get('nodes')
        if not isinstance(nodes, list) or not nodes:
            raise ValueError('DAG requires nonempty nodes')
        seen = set()
        for node in nodes:
            if not isinstance(node, dict) or not re.fullmatch(r'[a-z][a-z0-9_]*', str(node.get('id', ''))):
                raise ValueError('Invalid node id')
            if node['id'] in seen:
                raise ValueError('Duplicate node id: ' + node['id'])
            seen.add(node['id'])
            if not isinstance(node.get('kind'), str) or node['kind'] not in KINDS:
                raise ValueError('Unknown node kind')
            for field in ('depends_on', 'legacy_objects'):
                if not isinstance(node.get(field), list) or any(not isinstance(v, str) for v in node[field]):
                    raise ValueError(field + ' must be a string list')
            if set(node['legacy_objects']) - inventory.keys():
                raise ValueError('Unknown legacy ids: ' + str(sorted(set(node['legacy_objects']) - inventory.keys())))
            for field in ('retries', 'retry_delay_seconds'):
                if type(node.get(field)) is not int or node[field] < 0:
                    raise ValueError(field + ' must be a nonnegative integer')
            kind = node['kind']
            if kind in ('feed_sensor', 'bronze_ingest', 'dbt') and node.get('domain') not in DOMAINS:
                raise ValueError('Unknown domain')
            if kind == 'feed_sensor':
                if not any(t.area == node['domain'] and t.name == node.get('table') for t in TABLES):
                    raise ValueError('Unknown feed table')
                for field in ('timeout_seconds', 'poke_interval_seconds'):
                    if type(node.get(field)) is not int or node[field] <= 0:
                        raise ValueError(field + ' must be a positive integer')
            if kind == 'dbt' and (not isinstance(node.get('selector'), str) or not node['selector'].strip()):
                raise ValueError('dbt requires selector')
            if kind == 'parity' and (not isinstance(node.get('spec'), str) or node['spec'] not in specs):
                raise ValueError('Unknown parity spec')
            if kind == 'export' and (not isinstance(node.get('command'), list) or not node['command']
                                     or any(not isinstance(v, str) or not v for v in node['command'])):
                raise ValueError('export requires command argv')
        for node in nodes:
            if set(node['depends_on']) - seen:
                raise ValueError('Unknown dependencies: ' + str(sorted(set(node['depends_on']) - seen)))
        ordered(nodes)
        dags[dag['id']] = dag
    return dags


def feed_path(node, landing, day):
    business_date(day)
    return Path(landing).resolve() / node['domain'] / node['table'] / f'{day}.psv'
