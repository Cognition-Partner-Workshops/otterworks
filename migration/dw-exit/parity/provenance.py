"""Source ranges and metric implementation links for the measured board."""
import ast
from pathlib import Path
import re
import subprocess
from functools import lru_cache
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[3]
BRANCH = 'devin/sfx1119-billing-parity'
BASE = 'https://github.com/Cognition-Partner-Workshops/otterworks/blob/' + BRANCH + '/'


def link(path, start=1, end=None, branch=None):
    path = Path(path)
    end = end or max(1, len((ROOT / path).read_text().splitlines()))
    base = BASE if branch is None else 'https://github.com/Cognition-Partner-Workshops/otterworks/blob/' + quote(branch, safe='/') + '/'
    return {'file': path.as_posix(), 'start_line': start, 'end_line': end,
            'url': f'{base}{path.as_posix()}#L{start}-L{end}'}


@lru_cache(maxsize=1)
def audit_branch():
    return subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip() or 'HEAD'


def audit_provenance(obj):
    branch = audit_branch()
    def entry(path, text, match):
        return link(path, text.count('\n', 0, match.start())+1,
                    text.count('\n', 0, match.end())+1, branch=branch)
    converted = {}
    for relation in obj.get('output_relations', []):
        schema, table = relation.removeprefix('SFX_').split('.')
        entries = []
        for path in sorted((ROOT / 'migration/dw-exit/audit').glob('*.sql')):
            text = path.read_text()
            pattern = r'(?:INSERT\s+INTO|UPDATE|MERGE\s+INTO|COPY\s+INTO|CREATE\s+OR\s+REPLACE\s+(?:TABLE|VIEW))\s+__RUN_DATABASE__\.' + schema + r'\.' + table + r'\b.*?;'
            entries.extend(entry(path.relative_to(ROOT), text, match)
                           for match in re.finditer(pattern, text, re.S | re.I))
        converted[relation] = entries
    if obj.get('target_type') == 'retire' or obj.get('system') == 'spark':
        converted = {}
    elif obj.get('system') == 'powercenter' or obj['kind'] in ('macro', 'procedure') or obj['name'] == '10_summary_daily':
        name = obj['name'].split('.')[-1].upper()
        if name == '10_SUMMARY_DAILY':
            name = 'P_DAILY_SUMMARY'
        for path in sorted((ROOT / 'migration/dw-exit/audit').glob('*.sql')):
            text = path.read_text()
            pattern = r'CREATE OR REPLACE PROCEDURE\s+\S+\.' + name + r'\(.*?\$\$.*?\$\$;'
            entries = [entry(path.relative_to(ROOT), text, match) for match in re.finditer(pattern, text, re.S | re.I)]
            if entries:
                converted['routine:' + name] = entries
    source = source_link(obj) if obj.get('source') and (ROOT / obj['source']).is_file() else None
    if source:
        source = link(source['file'], source['start_line'], source['end_line'], branch=branch)
    return {'source': [source] if source else [], 'converted': converted,
            'conversion_note': 'Retirement proposed; no conversion' if obj.get('target_type') == 'retire' else
                               'Spark conversion deferred' if obj.get('system') == 'spark' else None,
            'metrics': {key: link(value['file'], value['start_line'], value['end_line'], branch=branch)
                        for key, value in metric_links().items()}}


def source_link(obj):
    path = Path(obj['source'])
    text = (ROOT / path).read_text()
    name = obj['name'].split('.')[-1]
    if obj['kind'] in ('procedure','macro'):
        return link(path)
    if path.suffix.lower() == '.sql':
        for match in re.finditer(r'(?:CREATE|REPLACE)\s+(?:(?:MULTISET|SET)\s+)?(?:TABLE|VIEW|MACRO|PROCEDURE)\s+[\w.]+', text, re.I):
            if match[0].split()[-1].split('.')[-1].upper() == name.upper():
                end = text.find(';', match.end())
                return link(path, text.count('\n',0,match.start())+1, text.count('\n',0,end if end >= 0 else len(text))+1)
    return link(path)


def converted_links(relation):
    table = relation.split('.')[-1]
    if relation.startswith('SFX_SPARK.'):
        paths = list((ROOT/'warehouse/dbt/models/spark'/table.lower()).glob('*.sql'))
        snowpark = ROOT/'warehouse/snowpark'/f'{table.lower()}.py'
        if snowpark.is_file():
            paths.append(snowpark)
        return [link(path.relative_to(ROOT)) for path in sorted(paths)]
    if table in ('M_SUBSCRIPTION_PLANS_OUTPUT', 'M_CURRENCY_TOTALS_OUTPUT'):
        path = Path('migration/dw-exit/billing/20_routines.sql')
        text = (ROOT/path).read_text()
        pattern = r'CREATE OR REPLACE PROCEDURE\s+\S+\.'+table.removesuffix('_OUTPUT')+r'\s*\(.*?\$\$.*?\$\$;'
        return [link(path, text.count('\n',0,m.start())+1, text.count('\n',0,m.end())+1)
                for m in re.finditer(pattern, text, re.S | re.I)]
    links = []
    for path in sorted((ROOT / 'migration/dw-exit/billing').glob('[0-4][0-9]_*.sql')):
        text = path.read_text()
        pattern = r'(?:INSERT\s+INTO|UPDATE|MERGE\s+INTO|CREATE\s+OR\s+REPLACE\s+(?:TABLE|VIEW))\s+__RUN_DATABASE__\.BILLING\.'+re.escape(table)+r'\b'
        for match in re.finditer(pattern,text,re.I):
            end = text.find(';',match.end())
            links.append(link(path.relative_to(ROOT),text.count('\n',0,match.start())+1,text.count('\n',0,end if end >= 0 else len(text))+1))
    return links


def metric_links():
    path = Path('migration/dw-exit/parity/ladder.py')
    nodes = {n.name:n for n in ast.parse((ROOT/path).read_text()).body if isinstance(n,ast.FunctionDef)}
    return {metric:link(path,nodes[function].lineno,nodes[function].end_lineno)
            for metric,function in [('counts','local_compare'),('profiles','local_measure'),('hashes','local_compare')]}


def provenance(obj):
    if obj.get('subject_area') == 'audit':
        return audit_provenance(obj)
    outputs = obj.get('output_relations', [])
    converted = {name:converted_links(name) for name in outputs}
    source = ROOT / obj.get('source', '')
    if source.is_file() and not any(converted.values()):
        text = source.read_text()
        routines = set(re.findall(r'(?:EXEC|CALL)\s+SFX_BILLING\.(\w+)', text, re.I))
        if obj['kind'] in ('macro', 'procedure'):
            routines.add(obj['name'].split('.')[-1])
        path = Path('migration/dw-exit/billing/20_routines.sql')
        sql = (ROOT/path).read_text()
        for match in re.finditer(r'CREATE OR REPLACE PROCEDURE\s+\S+\.(\w+)\s*\(.*?\$\$.*?\$\$;', sql, re.S | re.I):
            if match[1].upper() in {name.upper() for name in routines}:
                converted['routine:'+match[1]] = [link(path, sql.count('\n',0,match.start())+1, sql.count('\n',0,match.end())+1)]
        if obj.get('system') == 'spark':
            candidates = list((ROOT/'warehouse/dbt/models/spark').glob(obj['name']+'/*.sql'))
            candidate = ROOT/'warehouse/snowpark'/f"{obj['name']}.py"
            if candidate.is_file():
                candidates.append(candidate)
            converted['candidate:'+obj['name']] = [link(p.relative_to(ROOT)) for p in sorted(candidates)]
    return {'source': [source_link(obj)] if obj.get('source') and (ROOT/obj['source']).is_file() else [],
            'converted': converted,
            'conversion_note': None if outputs else 'No declared local output relation; linked candidates are not measured',
            'metrics': metric_links()}


def markdown(rows):
    billing = [row for row in rows if row['subject_area'] == 'billing']
    green = sum(row['local_duckdb'] == 'green' for row in billing)
    lines = ['\n## Billing parity provenance', '',
             f'Local DuckDB: {green} green / {len(billing)-green} red (including unmeasured outputs).',
             'Snowflake: **red** — '+(billing[0]['snowflake_reason'] if billing else 'No billing evidence')+'.',
             'These are separate evidence legs; local green does not imply live Snowflake parity.', '',
             '| Object | Local DuckDB | Snowflake | Source | Converted producers | Metrics |', '|---|---|---|---|---|---|']
    def anchors(entries):
        return '<br>'.join(f"[{e['file']}:{e['start_line']}–{e['end_line']}]({e['url']})" for e in entries)
    for row in rows:
        if row['subject_area'] != 'billing':
            continue
        p = row['provenance']
        converted = [entry for entries in p['converted'].values() for entry in entries]
        lines.append(f"| {row['name']} | {row['local_duckdb']} | {row['snowflake']} | {anchors(p['source'])} | {anchors(converted) or p['conversion_note'] or 'Not materialized'} | {anchors(p['metrics'].values())} |")
    audit = [row for row in rows if row['subject_area'] == 'audit']
    if audit:
        lines += ['', '## Audit parity provenance', '',
                  'Batch and isolated PowerCenter workflow outputs are separate evidence paths. Retirements and Spark remain unconverted.', '',
                  '| Object | Local DuckDB | Snowflake | Source | Converted producers | Metrics |', '|---|---|---|---|---|---|']
        for row in audit:
            p = row['provenance']
            converted = [entry for entries in p['converted'].values() for entry in entries]
            lines.append(f"| {row['name']} | {row['local_duckdb']} | {row['snowflake']} | {anchors(p['source'])} | {anchors(converted) or p['conversion_note'] or 'Not materialized'} | {anchors(p['metrics'].values())} |")
    return '\n'.join(lines)+'\n'
