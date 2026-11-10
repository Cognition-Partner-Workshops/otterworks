"""Restore governance metadata on replaceable scaffold tasks and procedures."""
import json

import yaml

from sfx_conn import ROOT, query_tag


def objects():
    result = []
    for area in ('billing', 'documents', 'users', 'audit'):
        prefix = f'RAW_{area.upper()}.LOAD_{area.upper()}'
        result.extend([('PROCEDURE', prefix + '(VARCHAR)'), ('TASK', prefix + '_TASK')])
    result.append(('PROCEDURE', 'ORCH.RUN_STEP(VARCHAR)'))
    steps = yaml.safe_load((ROOT / 'task_dag.yml').read_text())['steps']
    result.extend(('TASK', 'ORCH.' + step['task']) for step in steps.values())
    return result


def reapply(cursor):
    token = json.loads(query_tag('ops', 'governance'))['run_token']
    for kind, name in objects():
        cursor.execute(f'ALTER {kind} {name} SET TAG GOVERNANCE.SFX_RUN = %s', (token,))
        cursor.execute(f'COMMENT ON {kind} {name} IS %s', (token + ' governed scaffold object',))
        print(f'governance reapplied: {kind} {name}')
