"""Validate the offline assessment, including against the source estate."""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

from assess import OUT, board, build


def validate(out=OUT, source=True):
    required = ['inventory.csv', 'inventory.md', 'lineage.md', 'manifest.yaml', 'plan.md', 'board/README.md', 'board/board.json', 'README.md']
    errors = ['missing: ' + name for name in required if not (out / name).is_file()]
    if errors:
        return errors
    try:
        inventory = list(csv.DictReader((out / 'inventory.csv').open()))
        manifest = yaml.safe_load((out / 'manifest.yaml').read_text())
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
            for key in ('name', 'source', 'target', 'owner', 'owner_source', 'risk_reasons'):
                if key not in row:
                    errors.append(f"missing {key}: {row['id']}")
            if row['name'] in manifest['dead'] and row['target_type'] != 'retire':
                errors.append('dead object not retired: ' + row['name'])
            if row['kind'] == 'catalog' and row['target_type'] != 'retire':
                errors.append('catalog not retired: ' + row['name'])
        for a, b in manifest['dependencies']:
            if a not in index or b not in index or index[a]['wave'] > index[b]['wave']:
                errors.append(f'dependency wave order: {a} -> {b}')
        lineage = (out / 'lineage.md').read_text()
        for node in ids + [r['id'] for r in manifest['consumers']]:
            if node + '["' not in lineage:
                errors.append('lineage missing node: ' + node)
        if lineage.count('flowchart LR') != 1 or lineage.count('```mermaid') != 1:
            errors.append('lineage must contain one LR Mermaid graph')
        actual_board = json.loads((out / 'board/board.json').read_text())
        if actual_board['waves'] != board(objects, {})['waves']:
            errors.append('board counts differ from manifest')
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
    except (KeyError, TypeError, ValueError, OSError, yaml.YAMLError) as exc:
        errors.append('invalid assessment: ' + str(exc))
    return errors


if __name__ == '__main__':
    issues = validate(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT)
    if issues:
        print('FAIL\n' + '\n'.join(issues))
        sys.exit(1)
    print('PASS: inventory, manifest, dependencies, dead objects, lineage and board consistent')
