"""Validate the offline assessment, including against the source estate."""

import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[3]))
from warehouse.run_config import render as _run_render

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

from assess import OUT, board, build, uid


def validate(out=OUT, source=True):
    required = ['inventory.csv', 'inventory.md', 'lineage.md', 'lineage.html', 'waves.md', 'manifest.yaml', 'plan.md', 'board/README.md', 'board/board.json', 'README.md']
    errors = ['missing: ' + name for name in required if not (out / name).is_file()]
    if errors:
        return errors
    try:
        inventory = list(csv.DictReader((out / 'inventory.csv').open()))
        manifest = yaml.safe_load(_run_render((out / 'manifest.yaml').read_text()))
        objects = manifest['objects']
        ids = [r['id'] for r in inventory]
        mids = [r['id'] for r in objects]
        if len(set(ids)) != len(ids) or Counter(ids) != Counter(mids) or len(set(mids)) != len(mids):
            errors.append('inventory/manifest must have exactly one entry per object')
        index = {r['id']: r for r in objects}
        for row in objects:
            for key, allowed in {'kind': {'bteq', 'catalog', 'fastload', 'tpt', 'table', 'view', 'macro', 'procedure', 'mapping', 'session', 'worklet', 'workflow', 'spark_job'}, 'system': {'teradata', 'powercenter', 'spark'}, 'target_type': {'dbt_model', 'snowpark', 'snowflake_scripting', 'compatibility_view', 'retire'}, 'wave': {1, 2, 3, 4}, 'risk': {'low', 'med', 'high'}, 'complexity': {'low', 'medium', 'high'}, 'status': {'not_started'}}.items():
                if row.get(key) not in allowed:
                    errors.append(f"invalid {key}: {row['id']}")
            for key in ('name', 'source', 'target', 'owner', 'owner_source', 'risk_reasons', 'subject_area', 'licence_dependency', 'output_relations'):
                if key not in row:
                    errors.append(f"missing {key}: {row['id']}")
            if row.get('licence_dependency') not in {'teradata', 'powercenter', 'spark', 'none'}:
                errors.append('invalid licence dependency: '+row['id'])
            if not row.get('subject_area'):
                errors.append('missing subject area: '+row['id'])
            if row['name'] in manifest['dead'] and row['target_type'] != 'retire':
                errors.append('dead object not retired: ' + row['name'])
            if row['kind'] == 'catalog' and row['target_type'] != 'retire':
                errors.append('catalog not retired: ' + row['name'])
            if row['target_type'] == 'retire':
                facts = row.get('retire_evidence')
                required_facts = {'runs_in_window', 'last_run', 'cron', 'readers'} if row['system'] == 'spark' else {'usage_counts', 'read_count', 'last_read', 'last_write', 'recent_accesses'}
                if not isinstance(facts, dict) or not required_facts <= facts.keys():
                    errors.append('missing retire_evidence: ' + row['name'])
                if 'feeds only dead objects' in row['risk_reasons'] and not (facts or {}).get('feeds_dead_objects'):
                    errors.append('missing dead dependency evidence: ' + row['name'])
            if row['system'] == 'spark':
                facts = row.get('run_evidence', {})
                if not {'window', 'runs_in_window', 'last_run', 'executor_hours', 'executor_hours_in_window', 'cron', 'readers', 'non_reader_mentions', 'applications'} <= facts.keys():
                    errors.append('missing Spark run evidence: ' + row['name'])
                elif facts['runs_in_window'] < 0 or facts['executor_hours'] < 0 or facts['cron'].get('state') not in {'enabled', 'disabled', 'missing'}:
                    errors.append('invalid Spark run evidence: ' + row['name'])
                if not row.get('output_relations'):
                    errors.append('missing Spark outputs: ' + row['name'])
        if not isinstance(manifest.get('stale'), list):
            errors.append('missing stale review list')
        else:
            for item in manifest['stale']:
                if item['id'] not in index or index[item['id']]['target_type'] == 'retire' or not item.get('last_read') or item['last_read'][:10] >= '2026-09-10' or not item.get('review'):
                    errors.append('invalid stale review evidence: ' + item['name'])
        for a, b in manifest['dependencies']:
            if a not in index or b not in index or index[a]['wave'] > index[b]['wave']:
                errors.append(f'dependency wave order: {a} -> {b}')
        lineage = _run_render((out / 'lineage.md').read_text())
        html = (out / 'lineage.html').read_text()
        match = re.search(r'<script id="lineage-data" type="application/json">(.*?)</script>', html, re.S)
        if not match:
            errors.append('lineage.html missing graph data')
        else:
            graph = json.loads(match[1])
            graph_ids = [node['id'] for node in graph['nodes']]
            if len(graph_ids) != len(set(graph_ids)):
                errors.append('lineage.html duplicate node ids')
            for node in ids + [r['id'] for r in manifest['consumers']]:
                if node not in graph_ids:
                    errors.append('lineage.html missing node: ' + node)
            if any(a not in graph_ids or b not in graph_ids for a, b in graph['links']):
                errors.append('lineage.html dangling edge')
        waves = re.findall(r'^## Wave ([1-4])\n\nObjects: (\d+)$', (out / 'waves.md').read_text(), re.M)
        expected_waves = [(str(w), str(sum(r['wave'] == w for r in objects))) for w in range(1, 5)]
        if waves != expected_waves:
            errors.append('waves.md counts differ from manifest')
        for wave in range(1, 5):
            section = re.search(rf'^## Wave {wave}\n(.*?)(?=^## |\Z)', (out / 'waves.md').read_text(), re.M | re.S)
            if section:
                counts = re.findall(r'^\| (system|kind|target_type) \| ([^|]+) \| (\d+) \|$', section[1], re.M)
                expected_counts = [(field, value, str(count)) for field in ('system', 'kind', 'target_type')
                                   for value, count in Counter(r[field] for r in objects if r['wave'] == wave).items()]
                if Counter(counts) != Counter(expected_counts):
                    errors.append(f'waves.md dimension counts differ from manifest: wave {wave}')
        for a, b in manifest['dependencies']:
            if f'{a} --> {b}' not in lineage:
                errors.append(f'lineage missing edge: {a} -> {b}')
        if not manifest.get('spark_edges'):
            errors.append('missing Spark lineage edges')
        for a, b in manifest.get('spark_edges', []):
            start = uid(a) if a.startswith('feed:') else a
            if f'{start} --> {b}' not in lineage:
                errors.append(f'lineage missing Spark edge: {a} -> {b}')
        for node in ids + [r['id'] for r in manifest['consumers']]:
            if node + '["' not in lineage:
                errors.append('lineage missing node: ' + node)
        if lineage.count('flowchart LR') != 1 or lineage.count('```mermaid') != 1:
            errors.append('lineage must contain one LR Mermaid graph')
        actual_board = json.loads(_run_render((out / 'board/board.json').read_text()))
        if actual_board['waves'] != board(objects, {})['waves']:
            errors.append('board counts differ from manifest')
        if 'rows' in actual_board:
            if Counter(r['id'] for r in actual_board['rows']) != Counter(mids):
                errors.append('parity board rows differ from manifest')
            for row in actual_board['rows']:
                if row['id'] in index and any(row.get(key) != index[row['id']][key]
                                             for key in ('name', 'kind', 'wave', 'owner', 'subject_area', 'licence_dependency')):
                    errors.append('parity board metadata differs from manifest: ' + row['id'])
            if actual_board.get('summary', {}).get('rows') != len(objects):
                errors.append('parity board summary row count differs from manifest')
        if source:
            expected = build()
            if {r['id'] for r in expected['artifacts']} != set(ids):
                errors.append('inventory differs from source estate')
            if manifest['dead'] != expected['dead']:
                errors.append('dead objects differ from DBQL')
            if manifest['dependencies'] != [list(edge) for edge in expected['dependencies']]:
                errors.append('dependencies differ from parsed source')
            if manifest['consumers'] != expected['consumers']:
                errors.append('consumers differ from registry/DBQL')
            expected_inventory = [{k: str(v) for k, v in r.items()} for r in expected['artifacts']]
            if inventory != expected_inventory:
                errors.append('inventory content differs from source estate')
            if objects != expected['objects']:
                errors.append('manifest content differs from assessment rules')
            if actual_board['licence_counters'] != expected['counters']:
                errors.append('licence counters differ from source')
            if manifest.get('stale') != expected['stale']:
                errors.append('stale review evidence differs from source')
            if manifest.get('external_relations') != expected['external_relations']:
                errors.append('external relations differ from source')
            if manifest.get('spark_edges') != [list(edge) for edge in expected['spark_edges']]:
                errors.append('Spark edges differ from source')
            for a, b in expected['links']:
                start = uid(a) if a.startswith('feed:') else a
                if f'{start} --> {b}' not in lineage:
                    errors.append(f'lineage missing parsed edge: {a} -> {b}')
    except (KeyError, TypeError, ValueError, OSError, yaml.YAMLError) as exc:
        errors.append('invalid assessment: ' + str(exc))
    return errors


if __name__ == '__main__':
    issues = validate(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT)
    if issues:
        print('FAIL\n' + '\n'.join(issues))
        sys.exit(1)
    print('PASS: inventory, manifest, dependencies, dead objects, lineage and board consistent')
