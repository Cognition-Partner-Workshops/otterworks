"""Source ranges and metric implementation links for the measured board."""
import ast
from pathlib import Path
import re
import json
from functools import lru_cache
import subprocess
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[3]
BRANCH = 'devin/sfx1119-billing-parity'
BASE = 'https://github.com/Cognition-Partner-Workshops/otterworks/blob/' + BRANCH + '/'
SUBJECTS = json.loads((ROOT/'migration/dw-exit/parity/provenance_subjects.json').read_text())
BRANCHES = {name:values['branch'] for name,values in SUBJECTS.items()}


def link(path, start=1, end=None, subject='billing', branch=None):
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
            'conversion_note': 'Retirement proposed; no conversion' if obj.get('target_type') == 'retire' else None,
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


@lru_cache
def metric_links(subject='billing'):
    path = Path('migration/dw-exit/parity/ladder.py')
    pinned = SUBJECTS[subject].get('metric_source')
    if pinned:
        nodes = {name:(node['start_line'],node['end_line']) for name,node in pinned['functions'].items()}
    else:
        nodes = {n.name:(n.lineno,n.end_lineno) for n in ast.parse((ROOT/path).read_text()).body if isinstance(n,ast.FunctionDef)}
    metrics = [('counts','local_compare'),('profiles','local_measure'),('hashes','local_compare')]
    if subject=='documents':
        metrics.append(('diffs','local_compare'))
    return {metric:link(path,*nodes[function],subject=subject)
            for metric,function in metrics}


def provenance(obj):
    if obj.get('subject_area')=='documents':
        return documents_provenance(obj)
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


def billing_markdown(rows):
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
                  'Batch, isolated PowerCenter, and actual Spark lake/JDBC outputs are separate evidence paths. Retirements remain unconverted.', '',
                  '| Object | Local DuckDB | Snowflake | Source | Converted producers | Metrics |', '|---|---|---|---|---|---|']
        for row in audit:
            p = row['provenance']
            converted = [entry for entries in p['converted'].values() for entry in entries]
            lines.append(f"| {row['name']} | {row['local_duckdb']} | {row['snowflake']} | {anchors(p['source'])} | {anchors(converted) or p['conversion_note'] or 'Not materialized'} | {anchors(p['metrics'].values())} |")
    return '\n'.join(lines)+'\n'


def json_link(path, keys, subject='documents'):
    text = (ROOT/path).read_text()
    start,end = 0,len(text)
    for key in keys:
        match = re.search(r'"'+re.escape(key)+r'"\s*:\s*',text[start:end])
        if match is None:
            raise ValueError('Missing evidence key: '+key)
        start += match.end()
        _,size = json.JSONDecoder().raw_decode(text[start:end])
        end = start+size
    return link(path,text.count('\n',0,start)+1,text.count('\n',0,end)+1,subject=subject)


def documents_provenance(obj):
    def reference(path):
        return link(path,subject='documents')
    source = []
    if obj.get('source') and (ROOT/obj['source']).is_file():
        original = source_link(obj)
        original['url'] = original['url'].replace('/blob/'+BRANCH+'/', '/blob/'+BRANCHES['documents']+'/')
        source.append(original)
    converted = {}
    if obj['system']=='spark':
        converted['SFX_SPARK.'+obj['name'].upper()] = [reference(p.relative_to(ROOT)) for p in sorted(
            (ROOT/'warehouse/dbt/models/spark'/obj['name']).glob('*.sql'))]
        if obj['name'] in ('doc_version_diff_stats','docs_search_log_parse','docs_tag_normalize','file_object_binary_extract'):
            converted['udfs'] = [reference('warehouse/dbt/macros/documents_spark_udfs.sql')]
        if obj['name'] in ('file_object_binary_extract','security_alert_anomaly'):
            path = Path('etl/spark/jobs/py/common/runtime.py')
            function = 'save_partition' if obj['name']=='file_object_binary_extract' else 'save'
            node = next(n for n in ast.parse((ROOT/path).read_text()).body if isinstance(n,ast.FunctionDef) and n.name==function)
            source.append(link(path,node.lineno,node.end_lineno,subject='documents'))
    else:
        specs = json.loads((ROOT/'migration/dw-exit/documents/objects.json').read_text())
        spec = next((s for s in specs if s['name']==obj['name']),None)
        if spec:
            for field in ('conversion','producer'):
                if spec.get(field):
                    converted[field] = [reference(spec[field])]
            for output in spec.get('output_relations',[]):
                table = output.split('.')[-1]
                entries = []
                for path in sorted((ROOT/'warehouse/teradata/scripts/documents').glob('*.bteq')):
                    text = path.read_text()
                    pattern = r'(?:INSERT\s+INTO|DELETE\s+FROM|UPDATE|MERGE\s+INTO)\s+'+re.escape(output)+r'\b'
                    for match in re.finditer(pattern,text,re.I):
                        end = text.find(';',match.end())
                        source.append(link(path.relative_to(ROOT),text.count('\n',0,match.start())+1,
                            text.count('\n',0,end if end>=0 else len(text))+1,subject='documents'))
                for path in sorted((ROOT/'migration/dw-exit/documents').glob('*.sql')):
                    text = path.read_text()
                    pattern = r'(?:INSERT\s+INTO|COPY\s+INTO|UPDATE|MERGE\s+INTO|CREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW))\s+__RUN_DATABASE__\.DOCUMENTS\.'+re.escape(table)+r'\b'
                    for match in re.finditer(pattern,text,re.I):
                        end = text.find(';',match.end())
                        entries.append(link(path.relative_to(ROOT),text.count('\n',0,match.start())+1,
                            text.count('\n',0,end if end>=0 else len(text))+1,subject='documents'))
                if entries:
                    converted[output] = entries
    return {'source':source,'converted':converted,'conversion_note':None if converted else 'Retire candidate; no conversion executed',
            'metrics':metric_links('documents')}


def documents_table(evidence):
    path = Path('migration/dw-exit/documents/evidence.json')
    metrics = metric_links('documents')
    lines = ['| Documents proof leg | Before → after | Profiles | Hash delta | Diff samples |',
             '|---|---:|---|---:|---:|']
    legs = [(name,evidence[name],[name]) for name in ('sql_relations','tpt_relations','pc_relations','shared_billing_boundary','shared_billing_with_candidate_storage')]
    spark = {}
    for name,row in evidence['spark']['jobs'].items():
        spark[name] = row['measurement']
        for key,side in row.get('side_outputs',{}).items():
            spark[key] = side['measurement']
    legs.append(('spark_current_and_jdbc',spark,['spark']))
    replay = evidence['spark']['binary_history']
    legs.append(('spark_binary_two_date_history',{'history':replay['steps'][-1]['measurement']},['spark','binary_history']))
    for name,rows,keys in legs:
        b = sum(r['row_count']['before'] for r in rows.values())
        a = sum(r['row_count']['after'] for r in rows.values())
        delta = sum(r['keyed_row_hash']['difference'] for r in rows.values())
        samples = sum(len(r['sampled_differences']) for r in rows.values())
        profiles = sum(len(r['column_profile']['before']) for r in rows.values())
        detail = json_link(path,keys)['url']
        lines.append(f"| [{name}]({detail}) | [{b} → {a}]({metrics['counts']['url']}) | [{profiles} columns]({metrics['profiles']['url']}) | [{delta}]({metrics['hashes']['url']}) | [{samples}]({metrics['diffs']['url']}) |")
    return '\n'.join(lines)+'\n'


def markdown(rows, evidence=None):
    text = billing_markdown(rows)
    documents = [r for r in rows if r['subject_area']=='documents']
    if not documents:
        return text
    counts = {state:sum(r['status']==state for r in documents) for state in ('green','red','retired')}
    lines = ['\n## Documents parity provenance','',
             f"Local DuckDB: **{counts['green']} green / {counts['red']} red / {counts['retired']} retire candidates**, {len(documents)} total.",
             'Snowflake: **red/denied** — '+documents[0]['snowflake_reason']+'.',
             'Retire candidates are excluded from executable parity, not approved for deletion. Relation counts below sum within each proof leg; relations can repeat across legs.','']
    if evidence:
        lines.extend([documents_table(evidence),''])
    lines.extend(['| Object | Local | Counts | Hash delta | Diff samples | Source | Converted producers | Profiles |',
                  '|---|---|---:|---:|---:|---|---|---|'])
    def anchors(entries):
        return '<br>'.join(f"[{e['file']}:{e['start_line']}–{e['end_line']}]({e['url']})" for e in entries)
    for row in documents:
        p = row['provenance']
        converted = [entry for entries in p['converted'].values() for entry in entries]
        measured = row['row_count']
        counts_text = f"[{measured['before']} → {measured['after']}]({p['metrics']['counts']['url']})" if measured is not None else 'unmeasured'
        hashes = sum(v['difference'] for v in (row['keyed_row_hash'] or {}).values())
        diffs = sum(len(v) for v in (row['sampled_differences'] or {}).values())
        h = f"[{hashes}]({p['metrics']['hashes']['url']})" if measured else '—'
        d = f"[{diffs}]({p['metrics']['diffs']['url']})" if measured else '—'
        lines.append(f"| {row['name']} | {row['status']} | {counts_text} | {h} | {d} | {anchors(p['source'])} | {anchors(converted) or 'retire candidate'} | [code]({p['metrics']['profiles']['url']}) |")
    return text+'\n'.join(lines)+'\n'
