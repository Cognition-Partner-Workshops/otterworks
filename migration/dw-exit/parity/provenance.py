"""Source ranges and metric implementation links for the measured board."""
import ast
from pathlib import Path
import re
import json
from functools import lru_cache
import subprocess
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[3]
BRANCH = 'devin/sfg1120-audit'
BASE = 'https://github.com/Cognition-Partner-Workshops/otterworks/blob/' + BRANCH + '/'
SUBJECTS = json.loads((ROOT/'migration/dw-exit/parity/provenance_subjects.json').read_text())
BRANCHES = {name:values['branch'] for name,values in SUBJECTS.items()}


def link(path, start=1, end=None, subject='audit', branch=None):
    path = Path(path)
    end = end or max(1, len((ROOT / path).read_text().splitlines()))
    branch = branch or BRANCHES.get(subject, BRANCH)
    base = 'https://github.com/Cognition-Partner-Workshops/otterworks/blob/' + quote(branch, safe='/') + '/'
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
        if obj.get('system') == 'spark':
            directory = Path('warehouse/dbt/models/spark') / obj['name']
            converted[relation] = [link(path.relative_to(ROOT), branch=branch)
                                   for path in sorted((ROOT / directory).glob('*.sql'))]
            continue
        entries = []
        for path in sorted((ROOT / 'migration/dw-exit/audit').glob('*.sql')):
            text = path.read_text()
            pattern = r'(?:INSERT\s+INTO|UPDATE|MERGE\s+INTO|COPY\s+INTO|CREATE\s+OR\s+REPLACE\s+(?:TABLE|VIEW))\s+__RUN_DATABASE__\.' + schema + r'\.' + table + r'\b.*?;'
            entries.extend(entry(path.relative_to(ROOT), text, match)
                           for match in re.finditer(pattern, text, re.S | re.I))
        converted[relation] = entries
    if obj.get('target_type') == 'retire':
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
            'conversion_note': 'Retirement candidate; see board owner approval evidence; no conversion' if obj.get('target_type') == 'retire' else None,
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


@lru_cache
def metric_links():
    path = Path('migration/dw-exit/parity/ladder.py')
    nodes = {n.name:(n.lineno,n.end_lineno) for n in ast.parse((ROOT/path).read_text()).body
             if isinstance(n,ast.FunctionDef)}
    return {metric:link(path,*nodes[function],branch=audit_branch())
            for metric,function in [('counts','local_compare'),('profiles','local_measure'),
                                    ('hashes','local_compare'),('diffs','local_compare')]}


def provenance(obj):
    if obj.get('subject_area') == 'audit':
        return audit_provenance(obj)
    return {'source': [source_link(obj)] if obj.get('source') else [],
            'converted': {}, 'metrics': {}}


def audit_markdown(rows):
    lines = ['## Audit parity provenance', '',
             '| Object | Source | Converted | Metrics |', '|---|---|---|---|']
    for row in rows:
        if row['subject_area'] != 'audit':
            continue
        proof = row['provenance']
        links = lambda items: ', '.join('['+v['file']+' L'+str(v['start_line'])+'–'+str(v['end_line'])+']('+v['url']+')' for v in items)
        lines.append('| '+row['name']+' | '+links(proof['source'])+' | '+
                     links([v for values in proof['converted'].values() for v in values])+' | '+
                     links(proof['metrics'].values())+' |')
    return '\n'.join(lines)+'\n'
