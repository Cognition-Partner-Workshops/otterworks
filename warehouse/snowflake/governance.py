"""Restore governance metadata on replaceable scaffold tasks and procedures."""

import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[2]))
from warehouse.run_config import render as _run_render
from warehouse.sql import compose, identifier
from psycopg import sql

import json

import yaml

from sfx_conn import ROOT, query_tag


def objects():
    result = []
    for area in ('billing', 'documents', 'users', 'audit'):
        prefix = f'RAW_{area.upper()}.LOAD_{area.upper()}'
        result.extend([('PROCEDURE', prefix + '(VARCHAR)'), ('TASK', prefix + '_TASK')])
    result.append(('PROCEDURE', 'ORCH.RUN_STEP(VARCHAR)'))
    steps = yaml.safe_load(_run_render((ROOT / 'task_dag.yml').read_text()))['steps']
    result.extend(('TASK', 'ORCH.' + step['task']) for step in steps.values())
    result.extend(('VIEW', 'COMPAT.' + name) for name in (
        'CUSTOMER', 'ACCOUNT', 'INVOICE', 'INVOICE_LINE', 'PAYMENT', 'GL_JOURNAL_LINE',
        'DAILY_USAGE', 'GL_ACCOUNT', 'CUSTOMER_ACCOUNT', 'INVOICE_HDR', 'CREDIT_NOTE',
        'V_INVOICE_REVENUE', 'INVOICE_REVENUE'))
    return result


def reapply(cursor):
    token = json.loads(query_tag('ops', 'governance'))['run_token']
    for kind, name in objects():
        if kind not in ('PROCEDURE', 'TASK', 'VIEW'):
            raise ValueError('Invalid scaffold object kind')
        signature = '(VARCHAR)' if name.endswith('(VARCHAR)') else ''
        object_name = sql.Composed([identifier(name.removesuffix('(VARCHAR)')), sql.SQL(signature)])
        cursor.execute(compose('ALTER {} {} SET TAG GOVERNANCE.SFX_RUN = %s', sql.SQL(kind), object_name),
                       (_run_render('__RUN_TOKEN__'),))
        cursor.execute(compose('COMMENT ON {} {} IS %s', sql.SQL(kind), object_name),
                       (token + ' governed scaffold object',))
        print(f'governance reapplied: {kind} {name}')
