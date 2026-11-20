"""Generate pc_dag/audit.yml task bodies from the SQL dbt executed for wf_SFX_AUDIT_DAILY sessions."""

import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[2]))
from warehouse.run_config import render as _run_render

import argparse
from pathlib import Path
import re
import sys

from jinja2 import select_autoescape
from jinja2.sandbox import SandboxedEnvironment
import yaml

ROOT = Path(__file__).resolve().parent
DATABASE = _run_render('__RUN_DATABASE__')
SCHEMAS = ('PC_AUDIT', 'PC_FX_UNT9_AUDIT_WF')
COMMENT = _run_render('run_token=__RUN_TOKEN__ expires=2026-11-24')
# Enabled sessions of wf_SFX_AUDIT_DAILY; archive is disabled in the canonical workflow and has no task.
TASKS = {
    'STG_AUDIT_EVENT': ('s_m_SFX_STG_AUDIT_EVENT', ['START']),
    'AUDIT_EVENT': ('s_m_SFX_AUDIT_EVENT', ['STG_AUDIT_EVENT']),
    'AUDIT_DAILY_SUMMARY': ('s_m_SFX_AUDIT_DAILY_SUMMARY', ['AUDIT_EVENT']),
    'SECURITY_ALERT': ('s_m_SFX_SECURITY_ALERT', ['START']),
}


def relation(schema, name):
    return f'{DATABASE}.{schema}.{name}'


def strip(sql):
    return sql.strip().rstrip(';').strip()


def unwrap(sql):
    """dbt run SQL without leading line comments or its explicit begin/commit transaction wrapper."""
    sql = strip(re.sub(r'(?m)^\s*--[^\n]*$', '', sql))
    match = re.fullmatch(r'(?is)begin\s*;\s*(.*?)\s*;\s*commit', sql)
    return strip(match.group(1)) if match else sql


def summary_hooks(schema):
    model = ROOT.parent / 'dbt/models/pc/audit/pc_audit__audit_daily_summary.sql'
    config = {}
    # Renders the repository's own dbt SQL model, not HTML: autoescape stays off for strings.
    env = SandboxedEnvironment(autoescape=select_autoescape(default_for_string=False, default=False))
    env.from_string(_run_render(model.read_text())).render(
        config=lambda **kw: config.update(kw) or '',
        this=relation(schema, 'AUDIT_DAILY_SUMMARY'),
        ref=lambda name: relation(schema, name.split('__', 1)[1].upper()),
        var=lambda name, default: default, is_incremental=lambda: True)
    return [strip(sql) for sql in config['post_hook']]


def body(session_dir, schema, name):
    """Snowflake Scripting block replaying the session's dbt write: CTAS for tables, temp view + MERGE for incrementals."""
    run_sql = unwrap(_run_render((session_dir / 'run.sql').read_text()))
    target = relation(schema, name)
    if not re.search(re.escape(target), run_sql.replace('"', ''), re.I):
        raise ValueError(f'{session_dir.name}: run SQL does not write {target}')
    if '$$' in run_sql:
        raise ValueError('Dollar quoting inside dbt SQL is unsupported')
    statements = []
    if re.match(r'(?is)^merge\s+into', run_sql):
        compiled = strip(_run_render((session_dir / 'compiled.sql').read_text()))
        if '$$' in compiled:
            raise ValueError('Dollar quoting inside dbt SQL is unsupported')
        statements.append(f'CREATE OR REPLACE TEMPORARY VIEW {target}__dbt_tmp AS (\n{compiled}\n)')
        statements.append(run_sql)
        statements.append(f'DROP VIEW IF EXISTS {target}__dbt_tmp')
    elif re.match(r'(?is)^create\s+or\s+replace\s+(transient\s+)?table', run_sql):
        statements.append(run_sql)
    else:
        raise ValueError(f'{session_dir.name}: unsupported dbt write')
    if name == 'AUDIT_DAILY_SUMMARY':
        statements.extend(summary_hooks(schema))
    statements.append(f"COMMENT ON TABLE {target} IS '{COMMENT}'")
    return 'EXECUTE IMMEDIATE $$\nBEGIN\n' + ''.join(s + ';\n' for s in statements) + 'END;\n$$'


def generate(run_dir, source_schema, schema):
    if source_schema not in SCHEMAS or schema not in SCHEMAS:
        raise ValueError('Schema outside the audit workflow scope')
    tasks = {'START': {'sql': 'SELECT 1'}}
    for name, (session, after) in TASKS.items():
        sql = body(Path(run_dir) / session, source_schema, name)
        sql = re.sub(re.escape(f'{DATABASE}.{source_schema}.'), f'{DATABASE}.{schema}.', sql, flags=re.I)
        tasks[name] = {'after': after, 'warehouse': _run_render('__RUN_DATABASE___TRANSFORM_WH'), 'sql': sql}
    return {'root': 'START', 'tasks': tasks}


def refresh_summary(path, schema):
    model = ROOT.parent / 'dbt/models/pc/audit/pc_audit__audit_daily_summary.sql'
    env = SandboxedEnvironment(autoescape=False)
    query = env.from_string(model.read_text()).render(
        config=lambda **kwargs:'', var=lambda name,default:default,
        ref=lambda name:'__RUN_DATABASE__.'+schema+'.'+name.split('__',1)[1].upper())
    target = '__RUN_DATABASE__.'+schema+'.AUDIT_DAILY_SUMMARY'
    task = {'after':['AUDIT_EVENT'], 'warehouse':'__RUN_DATABASE___TRANSFORM_WH',
            'sql':'EXECUTE IMMEDIATE $$\nBEGIN\nCREATE OR REPLACE TRANSIENT TABLE '+target+
                  ' AS (\n'+query.strip()+"\n);\nCOMMENT ON TABLE "+target+
                  " IS 'run_token=__RUN_TOKEN__ expires=2026-11-24';\nEND;\n$$"}
    text = path.read_text()
    replacement = '\n'.join('  '+line if line else '' for line in yaml.safe_dump(
        {'AUDIT_DAILY_SUMMARY':task},sort_keys=False,width=1000).splitlines())+'\n'
    text = re.sub(r'(?ms)^  AUDIT_DAILY_SUMMARY:\n.*?(?=^  [A-Z_]+:|\Z)',lambda match:replacement,text)
    path.write_text(text)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-dir', type=Path, help='parity.workflow --out directory')
    parser.add_argument('--refresh-summary', action='store_true', help='Compile only the current summary model; no live dbt execution')
    parser.add_argument('--source-schema', default='PC_FX_UNT9_AUDIT_WF', choices=SCHEMAS)
    parser.add_argument('--schema', default='PC_AUDIT', choices=SCHEMAS)
    parser.add_argument('--output', type=Path, default=ROOT / 'pc_dag/audit.yml')
    args = parser.parse_args(argv)
    if args.refresh_summary:
        refresh_summary(args.output,args.schema)
        return 0
    if args.run_dir is None:
        parser.error('--run-dir is required without --refresh-summary')
    doc = generate(args.run_dir, args.source_schema, args.schema)
    header = ('# Generated by warehouse/snowflake/pc_dag_audit.py from the SQL dbt ran for wf_SFX_AUDIT_DAILY.\n'
              '# s_m_SFX_AUDIT_EVENT_ARCHIVE has no task: it is disabled in the canonical PowerCenter workflow,\n'
              '# so daily enablement is not authorized. No schedule: deploy suspended, EXECUTE TASK only.\n')
    args.output.write_text(header + yaml.safe_dump(doc, sort_keys=False, width=1000))
    return 0


if __name__ == '__main__':
    sys.exit(main())
