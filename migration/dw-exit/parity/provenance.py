"""Source ranges and metric implementation links for the measured board."""
import ast
from pathlib import Path
import re
import json
from functools import lru_cache
from urllib.parse import quote

from .subjects import SUBJECTS as EXECUTION_SUBJECTS

ROOT = Path(__file__).resolve().parents[3]
BRANCH = 'devin/sfg1120-integration'
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
    return BRANCH


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
    if obj.get('subject_area') == 'users':
        return users_provenance(obj)
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

def converted_links(relation):
    table = relation.split('.')[-1]
    subject = 'users' if relation.startswith('SFX_USERS.') else 'billing'
    if relation.startswith('SFX_SPARK.'):
        paths = list((ROOT/'warehouse/dbt/models/spark'/table.lower()).glob('*.sql'))
        snowpark = ROOT/'warehouse/snowpark'/f'{table.lower()}.py'
        if snowpark.is_file():
            paths.append(snowpark)
        return [link(path.relative_to(ROOT)) for path in sorted(paths)]
    if table in ('M_SUBSCRIPTION_PLANS_OUTPUT', 'M_CURRENCY_TOTALS_OUTPUT', 'M_TEAM_COUNTS_OUTPUT'):
        path = Path('migration/dw-exit')/subject/'20_routines.sql'
        text = (ROOT/path).read_text()
        pattern = r'CREATE OR REPLACE PROCEDURE\s+\S+\.'+table.removesuffix('_OUTPUT')+r'\s*\(.*?\$\$.*?\$\$;'
        return [link(path, text.count('\n',0,m.start())+1, text.count('\n',0,m.end())+1)
                for m in re.finditer(pattern, text, re.S | re.I)]
    links = []
    for path in sorted((ROOT / 'migration/dw-exit'/subject).glob('[0-4][0-9]_*.sql')):
        text = path.read_text()
        pattern = r'(?:INSERT\s+INTO|UPDATE|MERGE\s+INTO|CREATE\s+OR\s+REPLACE\s+(?:TABLE|VIEW))\s+__RUN_DATABASE__\.'+subject.upper()+r'\.'+re.escape(table)+r'\b'
        for match in re.finditer(pattern,text,re.I):
            end = text.find(';',match.end())
            links.append(link(path.relative_to(ROOT),text.count('\n',0,match.start())+1,text.count('\n',0,end if end >= 0 else len(text))+1))
    return links


def _provenance(obj):
    outputs = obj.get('output_relations', [])
    converted = {name:converted_links(name) for name in outputs}
    source = ROOT / obj.get('source', '')
    if source.is_file() and not any(converted.values()) and obj.get('target_type') != 'retire':
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


def users_provenance(obj):
    result = _provenance(obj)
    if obj.get('subject_area') == 'users' and obj.get('system') == 'powercenter' and obj['kind'] in ('mapping','session'):
        mapping = obj['name'].removeprefix('s_')
        table = mapping.removeprefix('m_SFX_')
        source = Path('etl/informatica/repository/SFX_CONTENT/mappings')/(mapping+'.XML')
        if obj['kind'] == 'session':
            result['source'].append(link(source))
        if obj['kind'] == 'session':
            path = Path(obj['source'])
            text = (ROOT/path).read_text()
            match = re.search(r'<SESSION\b[^>]*\bNAME="'+re.escape(obj['name'])+r'"[^>]*>.*?</SESSION>',text,re.S)
            if match:
                result['source'][0] = link(path,text.count('\n',0,match.start())+1,text.count('\n',0,match.end())+1)
        paths = [Path('warehouse/dbt/models/pc/content')/('pc_content__'+table.lower()+'.sql')]
        macro = Path('warehouse/dbt/macros')/('pc_content_'+table.lower()+'.sql')
        if (ROOT/macro).exists():
            paths.append(macro)
        if table == 'TEAM_MEMBER':
            paths.append(Path('warehouse/dbt/macros/unt8_python_unicode.sql'))
        result['converted'] = {'SFX_USERS.'+table:[link(p) for p in paths]}
        result['conversion_note'] = 'PC runner proof; dbt SELECT plus configured table/merge materialization, not BTEQ output'
        if table == 'APP_USER':
            result['converted']['TRANSFORM.M_SFX_APP_USER'] = [link('warehouse/snowpark/m_sfx_app_user.py')]
            result['conversion_note'] += '; Snowpark handler measured with local_testing=True, not live Snowflake'
    if obj.get('subject_area') == 'users':
        if obj['target_type'] == 'retire':
            path = Path('migration/dw-exit/manifest.yaml')
            text = (ROOT/path).read_text()
            start = text.index('\ndead:') + 1
            end = text.index('\nsetup_only:', start)
            result['metrics']['retirement_manifest'] = link(path, text.count('\n', 0, start)+1, text.count('\n', 0, end))
            path = Path('migration/dw-exit/tools/assess.py')
            text = (ROOT/path).read_text()
            for key, start_marker, end_marker in [('absence', 'def dbql(', '\ndef hidden_consumers('),
                                                  ('propagation', '    # Dependency edges', '    dependencies = sorted(')]:
                start, end = text.index(start_marker), text.index(end_marker)
                result['metrics']['retirement_'+key] = link(path, text.count('\n', 0, start)+1, text.count('\n', 0, end))
            for filename in ('qrylog.csv', 'objectusage.csv', 'tablesv.csv'):
                result['metrics']['retirement_'+filename] = link('warehouse/teradata/dbql/'+filename)
            result['metrics']['retirement_check'] = link('migration/dw-exit/parity/retirement_users.py')
            result['conversion_note'] = 'Retirement evidence only, not migrated; keep Spark USER_PREF/PREF_JSON landing for user_pref_json_flatten'
        for entry in result['source'] + list(result['metrics'].values()) + [e for entries in result['converted'].values() for e in entries]:
            entry['url'] = entry['url'].replace('devin/sfg1120-users', BRANCH)
    return result


def markdown(rows, subject='billing'):
    billing = [row for row in rows if row['subject_area'] == subject]
    green = sum(row['local_duckdb'] == 'green' for row in billing)
    retired = sum(row['local_duckdb'] == 'retired' for row in billing)
    deviations = sum(row['local_duckdb'] == 'approved_deviation' for row in billing)
    counts = (f'Local DuckDB: {green} green / {deviations} approved_deviation / {retired} retired / {len(billing)-green-retired-deviations} red (retirement evidence is not green-migrated).'
              if subject == 'users' else f'Local DuckDB: {green} green / {len(billing)-green} red (including unmeasured outputs).')
    lines = ['\n## '+subject.title()+' parity provenance', '',
             counts,
             'Snowflake: **red** — '+(billing[0]['snowflake_reason'] if billing else 'No '+subject+' evidence')+'.',
             'These are separate evidence legs; local green does not imply live Snowflake parity.', '',
             '| Object | Local DuckDB | Snowflake | Source | Converted producers | Metrics |', '|---|---|---|---|---|---|']
    if subject == 'users':
        lines[6:6] = ['Retirement checks use current checked-out DBQL, 2026-08-12–2026-11-09, and dead-dependent propagation; failure returns red. Keep the independent Spark USER_PREF/PREF_JSON landing feed for user_pref_json_flatten. Owner-approved retirement; board generation performs no deletion or cutover.', '']
    def anchors(entries):
        return '<br>'.join(f"[{e['file']}:{e['start_line']}–{e['end_line']}]({e['url']})" for e in entries)
    for row in rows:
        if row['subject_area'] != subject:
            continue
        p = row['provenance']
        converted = [entry for entries in p['converted'].values() for entry in entries]
        lines.append(f"| {row['name']} | {row['local_duckdb']} | {row['snowflake']} | {anchors(p['source'])} | {anchors(converted) or p['conversion_note'] or 'Not materialized'} | {anchors(p['metrics'].values())} |")
    text = '\n'.join(lines)+'\n'
    if subject == 'billing':
        text += ''.join(markdown(rows, area) for area in EXECUTION_SUBJECTS if area != 'billing')
    return text


def compact_markdown(rows, subject='users'):
    lines = ['\n## '+subject.title()+' compact parity', '',
             'Counts sum declared output relations; hash diff sums multiset differences. PC rows use their independent runner proof. A red hold with zero diff is not cleared. Dashes mean no conversion measurement, not zero rows.', '',
             '| Object | Status | Before | After | Hash diff |', '|---|---|---|---|---|']
    for row in rows:
        if row['subject_area'] != subject:
            continue
        metrics = row['provenance']['metrics']
        counts = row['row_count']
        hashes = row['keyed_row_hash']
        def number(value, metric):
            return '—' if value is None else f"[{value}]({metrics[metric]['url']})"
        before = number(counts['before'] if counts else None, 'counts')
        after = number(counts['after'] if counts else None, 'counts')
        difference = number(sum(h['difference'] for h in hashes.values()) if hashes else None, 'hashes')
        lines.append(f"| {row['name']} | {row['local_duckdb']} | {before} | {after} | {difference} |")
    return '\n'.join(lines)+'\n'
