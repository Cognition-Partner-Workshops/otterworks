import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from lakehouse.coverage.inventory import discover
from lakehouse.parity.spec import discover as discover_specs
from lakehouse.runtime.layout import DOMAINS, ROOT, data_root
from lakehouse.runtime.platform import FEEDS, feed_path as platform_feed_path
from warehouse.seed.columns import TABLES

PIPELINE = ROOT / 'orchestration/pipeline.yaml'
KINDS = {'feed_sensor', 'artifact_sensor', 'bronze_ingest', 'dbt', 'parity', 'export', 'noop'}


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
        schedule = dag.get('schedule')
        timed_cron = isinstance(schedule, str) and re.fullmatch(r'[0-5]?\d (?:\*|[01]?\d|2[0-3]) \* \* (?:\*|[0-6])', schedule)
        if 'schedule' not in dag or not (schedule in (None, '@daily', '@hourly', '@weekly') or timed_cron) or dag.get('timezone') != 'UTC':
            raise ValueError('DAG schedule must be @daily/@hourly, a daily/weekly/hourly clock cron or manual in UTC')
        business_date(dag.get('start_date'))
        if dag.get('catchup') is not True or dag.get('max_active_runs') != 1 or dag.get('max_active_tasks') != 1:
            raise ValueError('DAGs require catchup and one active run/task for embedded Derby')
        if not isinstance(dag.get('paused'), bool):
            raise ValueError('DAG paused must be boolean')
        if dag['schedule'] is None and not dag['paused']:
            raise ValueError('Unscheduled DAG must remain paused')
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
                prefix = node.get('landing_prefix', '')
                if not isinstance(prefix, str) or Path(prefix).is_absolute() or '..' in Path(prefix).parts:
                    raise ValueError('Invalid landing prefix')
                try:
                    prefix.format(business_date='20261109')
                except (KeyError, ValueError, IndexError, AttributeError) as exc:
                    raise ValueError('Invalid landing prefix') from exc
                known = (node.get('table') in FEEDS if node['domain'] == 'platform' else
                         any(t.area == node['domain'] and t.name == node.get('table') for t in TABLES))
                if not known:
                    raise ValueError('Unknown feed table')
            if kind == 'artifact_sensor':
                value = node.get('path')
                if not isinstance(value, str) or not value.startswith('{data_root}/'):
                    raise ValueError('Artifact sensor path must be namespace-scoped')
                try:
                    rendered = value.format(data_root='/namespace', business_date='20261109')
                except (KeyError, ValueError, IndexError, AttributeError) as exc:
                    raise ValueError('Invalid artifact sensor path') from exc
                if '..' in Path(rendered).parts:
                    raise ValueError('Invalid artifact sensor path')
            if kind in ('feed_sensor', 'artifact_sensor'):
                for field in ('timeout_seconds', 'poke_interval_seconds'):
                    if type(node.get(field)) is not int or node[field] <= 0:
                        raise ValueError(field + ' must be a positive integer')
            if kind == 'dbt' and (not isinstance(node.get('selector'), str) or not node['selector'].strip()):
                raise ValueError('dbt requires selector')
            if kind == 'dbt' and 'exclude' in node and (
                    not isinstance(node['exclude'], str) or not node['exclude'].strip()):
                raise ValueError('dbt requires nonempty exclude')
            if kind == 'parity':
                selected = node.get('specs', [node.get('spec')])
                if 'spec' in node and 'specs' in node:
                    raise ValueError('Parity node cannot specify both spec and specs')
                if not isinstance(selected, list) or not selected:
                    raise ValueError('Parity nodes require a nonempty list of specs')
                if any(not isinstance(spec, str) or spec not in specs for spec in selected):
                    raise ValueError('Unknown parity spec')
                if len(selected) != len(set(selected)):
                    raise ValueError('Duplicate parity spec')
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
    if node['domain'] == 'platform':
        return platform_feed_path(node['table'])
    prefix = node.get('landing_prefix', '').format(business_date=day)
    return Path(landing).resolve() / prefix / node['domain'] / node['table'] / f'{day}.psv'


def artifact_path(node, day):
    business_date(day)
    return Path(node['path'].format(data_root=data_root(), business_date=day))
