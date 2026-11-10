"""Offline, deterministic assessment of the checked-out warehouse estate."""
import csv
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'migration/dw-exit'
FIELDS = 'id system kind name file loc complexity constructs dbql_reads_90d last_read'.split()
OBJ = r'[A-Za-z_][\w]*\.[A-Za-z_][\w]*'


def uid(value):
    return 'n' + hashlib.sha256(value.encode()).hexdigest()[:16]


def clean(text):
    text = re.sub(r'/\*.*?\*/|<!--.*?-->', '', text, flags=re.S)
    return re.sub(r'--[^\n]*', '', text)


def loc(text):
    return sum(bool(line.strip()) for line in clean(text).splitlines())


def ddl_objects(text):
    pattern = r'\b(?:CREATE|REPLACE)\s+(?:(?:MULTISET|SET)\s+)?(TABLE|VIEW)\s+(' + OBJ + r')\b.*?;'
    return [(m[1].lower(), m[2].upper(), m[0]) for m in re.finditer(pattern, clean(text), re.I | re.S)]


def sql_refs(text):
    text = clean(text)
    reads = set(re.findall(r'\b(?:FROM|JOIN)\s+(' + OBJ + ')', text, re.I))
    writes = set(re.findall(r'\b(?:INSERT\s+INTO|MERGE\s+INTO|UPDATE)\s+(' + OBJ + ')', text, re.I))
    return {x.upper() for x in reads}, {x.upper() for x in writes}


def rows(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def dbql(root):
    base = root / 'warehouse/teradata/dbql'
    queries = {r['QueryID']: r for r in rows(base / 'qrylog.csv')
               if '2026-08-12' <= r['StartTime'][:10] <= '2026-11-09'}
    usage = [r for r in rows(base / 'objectusage.csv') if r['QueryID'] in queries]
    catalog = rows(base / 'tablesv.csv')
    used = {r['ObjectDatabaseName'] + '.' + r['ObjectTableName'] for r in usage}
    dead = sorted(r['DatabaseName'] + '.' + r['TableName'] for r in catalog
                  if r['DatabaseName'] != 'DBC' and r['DatabaseName'] + '.' + r['TableName'] not in used)
    return queries, usage, catalog, dead


def hidden_consumers(root, readers):
    files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
    hits = {user: [] for user in readers}
    for name in files:
        if not name or name.startswith(('warehouse/teradata/dbql/', 'migration/dw-exit/')) or '/tests/' in name or name.startswith('tests/'):
            continue
        path = root / name
        if not path.is_file():
            continue
        data = path.read_text(errors='ignore')
        for user in readers:
            if re.search(r'(?<![\w])' + re.escape(user) + r'(?![\w])', data):
                hits[user].append(name)
    return {user: {'warehouse_etl_hits': [p for p in paths if p.startswith(('warehouse/', 'etl/'))],
                   'repo_hits': paths} for user, paths in sorted(hits.items())}


def build(root=ROOT):
    artifacts, links, feeds = [], set(), set()
    def add(kind, name, path, text, constructs=()):
        tokens = sorted(set(constructs) | {token for token in ['.IF', '.GOTO', '.EXPORT', 'QUALIFY', 'MERGE', 'VOLATILE', 'SET TABLE', 'CURSOR'] if token in text.upper()})
        size = loc(text)
        complexity = 'high' if size >= 100 or len(tokens) >= 4 or any(t in tokens for t in ['Sequence', 'Use First Value', 'Unconnected']) else 'medium' if size >= 35 or tokens else 'low'
        row = dict(zip(FIELDS, [uid(kind + ':' + name), 'powercenter' if kind in ('mapping', 'session', 'worklet', 'workflow') else 'teradata', kind, name, str(path), size, complexity, '; '.join(tokens), 0, '']))
        artifacts.append(row)
        return row['id']
    td = root / 'warehouse/teradata'
    for path in sorted((td / 'ddl').glob('*/*.sql')):
        for kind, name, text in ddl_objects(path.read_text()):
            add(kind, name, path.relative_to(root), text)
    for folder, pattern, kind in [('scripts', '*/*.bteq', 'bteq'), ('macros', '*.sql', 'macro'), ('procedures', '*.sql', 'procedure'), ('load/fastload', '*.fl', 'fastload'), ('load/tpt', '*.tpt', 'tpt')]:
        for path in sorted((td / folder).glob(pattern)):
            text = path.read_text()
            match = re.search(r'REPLACE\s+(?:MACRO|PROCEDURE)\s+(' + OBJ + ')', text, re.I)
            name = match[1].upper() if match else path.stem
            node = add(kind, name, path.relative_to(root), text)
            if kind in ('fastload', 'tpt'):
                landing = re.search(r'FILE=([^;]+)', text) if kind == 'fastload' else re.search(r"DirectoryPath\s*=\s*'([^']+)'", text)
                if landing:
                    feed = landing[1] + ('/${BUSINESS_DATE}.psv' if kind == 'tpt' else '')
                    feeds.add(feed)
                    links.add(('feed:' + feed, node))
    mapping_files = sorted((root / 'etl/informatica/repository').glob('*/mappings/*.XML'))
    for path in mapping_files:
        tree = ET.fromstring(path.read_text())
        mapping = tree.find('.//MAPPING')
        text = ET.tostring(mapping, encoding='unicode')
        types = [e.get('TYPE', '') for e in mapping.findall('TRANSFORMATION')]
        types.append('transformations=' + str(len(mapping.findall('TRANSFORMATION'))))
        if ':LKP.' in text.upper():
            types.append('Unconnected')
        types += [v for v in ['Use First Value', 'Unconnected'] if v.lower() in text.lower()]
        node = add('mapping', mapping.get('NAME'), path.relative_to(root), text, types)
        definitions = {e.get('NAME'): e for tag in ['SOURCE', 'TARGET'] for e in tree.findall('.//' + tag)}
        for inst in mapping.findall('INSTANCE'):
            if inst.get('TYPE') not in ('SOURCE', 'TARGET'):
                continue
            definition = definitions[inst.get('TRANSFORMATION_NAME')]
            name = definition.get('NAME')
            owner = definition.get('OWNERNAME')
            if definition.get('DATABASETYPE') == 'Flat File':
                key = 'feed:' + name
                feeds.add(name)
            else:
                candidates = [r['name'] for r in artifacts if r['kind'] in ('table', 'view') and r['name'].split('.')[-1] == name.upper()]
                if not owner and len(candidates) != 1:
                    raise ValueError('Ambiguous mapping definition: ' + name)
                key = (owner + '.' + name).upper() if owner else candidates[0]
            links.add((key, node) if inst.get('TYPE') == 'SOURCE' else (node, key))
    for path in sorted((root / 'etl/informatica/repository').glob('*/wf_*.XML')):
        tree = ET.fromstring(path.read_text())
        for kind in ['session', 'worklet', 'workflow']:
            for elem in tree.findall('.//' + kind.upper()):
                node = add(kind, elem.get('NAME'), path.relative_to(root), ET.tostring(elem, encoding='unicode'))
                if kind == 'session':
                    links.add((uid('mapping:' + elem.get('MAPPINGNAME')), node))
                for task in elem.findall('TASKINSTANCE'):
                    task_kind = task.get('TASKTYPE', '').lower()
                    if task_kind in ('session', 'worklet'):
                        links.add((uid(task_kind + ':' + task.get('TASKNAME')), node))
    queries, usage, catalog, dead = dbql(root)
    for item in catalog:
        if item['DatabaseName'] == 'DBC':
            add('catalog', 'DBC.' + item['TableName'], 'warehouse/teradata/dbql/tablesv.csv', '')
    by_name = {r['name']: r['id'] for r in artifacts}
    for row in artifacts:
        if row['system'] == 'teradata' and row['kind'] != 'catalog':
            text = (root / row['file']).read_text()
            if row['kind'] in ('table', 'view'):
                text = next(t for k, n, t in ddl_objects(text) if n == row['name'])
            reads, writes = sql_refs(text)
            links.update((name, row['id']) for name in reads if name != row['name'])
            links.update((row['id'], name) for name in writes if name != row['name'])
    normalized = set()
    nodes = {r['id'] for r in artifacts}
    for a, b in links:
        a, b = by_name.get(a, a), by_name.get(b, b)
        if (a in nodes or a.startswith('feed:')) and b in nodes and a != b:
            normalized.add((a, b))
    registry = yaml.safe_load((root / 'consumers/registry.yaml').read_text())['consumers']
    registered = {c['teradata_service_account']: c for c in registry}
    reads = defaultdict(list)
    principals = set()
    for u in usage:
        if u['UsageType'] == 'READ':
            q = queries[u['QueryID']]
            reads[u['ObjectDatabaseName'] + '.' + u['ObjectTableName']].append(q)
            principals.add(q['UserName'])
    scans = hidden_consumers(root, principals)
    consumers = []
    # Utility and batch accounts are not end-user consumers.
    batch_accounts = {q['UserName'] for q in queries.values() if q['StatementGroup'] in ('UTILITY', 'ETL', 'BATCH')}
    reader_accounts = principals - batch_accounts
    for account in sorted(set(registered) | reader_accounts):
        reg = registered.get(account)
        consumers.append({'id': uid('consumer:' + account), 'name': reg['name'] if reg else account, 'account': account,
                          'owner': reg['team'] if reg else 'unknown', 'owner_source': 'consumers/registry.yaml' if reg else 'unknown',
                          'risk': 'med' if reg else 'high', 'wave': 4, 'status': 'not_started', 'hidden': not bool(reg),
                          'applications': sorted({q['AppID'] for q in queries.values() if q['UserName'] == account}),
                          'clients': sorted({q['ClientID'] for q in queries.values() if q['UserName'] == account}),
                          'scan': scans.get(account, {'warehouse_etl_hits': [], 'repo_hits': []})})
    for name, qs in reads.items():
        for consumer in consumers:
            if any(q['UserName'] == consumer['account'] for q in qs) and name in by_name:
                normalized.add((by_name[name], consumer['id']))
    risks = defaultdict(set)
    for filename in ['sfx-teradata.json', 'sfx-informatica.json']:
        data = json.loads((root / 'demos/app/complexity' / filename).read_text())
        instances = [(c['id'], i) for c in data.get('classes', []) for i in c['instances']]
        instances += [(i['class_id'], i) for i in data.get('instances', [])]
        for code, inst in instances:
            for row in artifacts:
                if inst.get('object', '').split(' / ')[0] == row['name'] or (inst.get('file') == row['file'] and row['kind'] not in ('table', 'view')):
                    risks[row['id']].add(code)
    manifest = []
    for row in sorted(artifacts, key=lambda r: (r['system'], r['kind'], r['name'])):
        name, kind = row['name'], row['kind']
        qs = reads[name]
        row['dbql_reads_90d'] = len(qs)
        row['last_read'] = max((q['StartTime'] for q in qs), default='')
        area = name.split('.')[0].removeprefix('SFX_') if '.' in name else ('BILLING' if 'BILLING' in name.upper() or '/billing/' in row['file'] else 'AUDIT' if 'AUDIT' in name.upper() or '/audit/' in row['file'] else 'USERS')
        if '/SFX_BILLING/' in row['file']:
            area = 'BILLING'
        elif '/SFX_AUDIT/' in row['file']:
            area = 'AUDIT'
        elif '/documents/' in row['file']:
            area = 'DOCUMENTS'
        elif row['kind'] == 'mapping':
            targets = [r['name'].split('.')[0].removeprefix('SFX_') for r in artifacts if r['kind'] == 'table' and (row['id'], r['id']) in normalized]
            if len(set(targets)) == 1:
                area = targets[0]
        stage = '.STG_' in name or '_STG_' in name
        target_type = 'dbt_model'
        wave = 1 if stage or kind in ('fastload', 'tpt', 'catalog') or name in dead else 3 if area == 'BILLING' or kind in ('macro', 'procedure') else 2
        if kind in ('fastload', 'tpt', 'macro', 'procedure', 'workflow', 'worklet') or kind == 'bteq' and any(t in row['constructs'] for t in ('.IF', '.GOTO', '.EXPORT')):
            target_type = 'snowflake_scripting'
        if kind == 'mapping' and any(t in row['constructs'] for t in ('Sequence', 'Unconnected', 'Use First Value')):
            target_type = 'snowpark'
        if kind == 'view':
            target_type, wave = 'compatibility_view', 4
        if kind in ('workflow', 'worklet'):
            wave = 3 if 'BILLING' in name else 4
        reasons = sorted(risks[row['id']])
        if row['complexity'] == 'high':
            reasons.append('high complexity')
        if name in dead:
            target_type, wave = 'retire', 1
            reasons.append('no DBQL usage in 90-day window')
        if kind == 'catalog':
            target_type = 'retire'
            reasons.append('replaced by SNOWFLAKE.ACCOUNT_USAGE')
        target = ('stg_' if stage else 'core_') + area.lower() + '__' + name.split('.')[-1].lower().removeprefix('stg_')
        if target_type == 'snowflake_scripting':
            target = 'RAW_' + area + '.LOAD_' + area if kind in ('fastload', 'tpt') else 'OPS.' + re.sub(r'\W', '_', name).upper()
        elif target_type == 'snowpark':
            target = 'TRANSFORM.' + name.upper()
        elif target_type == 'compatibility_view':
            target = 'COMPAT.' + name.replace('.', '__')
        elif target_type == 'retire':
            target = 'SNOWFLAKE.ACCOUNT_USAGE' if kind == 'catalog' else 'NONE'
        # Attribute reads through downstream views/macros, without counting load paths as readership.
        reachable = {row['id']}
        if kind not in ('table', 'view', 'macro', 'procedure', 'catalog'):
            load_nodes = {row['id']}
            if kind == 'session':
                load_nodes |= {a for a, b in normalized if b == row['id']}
            reachable |= {b for a, b in normalized if a in load_nodes and any(r['id'] == b and r['kind'] == 'table' for r in artifacts)}
        while True:
            expanded = reachable | {b for a, b in normalized if a in reachable and any(r['id'] == b and r['kind'] in ('view', 'macro', 'procedure') for r in artifacts)}
            if expanded == reachable:
                break
            reachable = expanded
        scores = Counter(q['UserName'] for r in artifacts if r['id'] in reachable for q in reads[r['name']] if q['UserName'] in registered)
        account = sorted(scores, key=lambda a: (-scores[a], a))[0] if scores else None
        manifest.append({**{k: row[k] for k in ('id', 'system', 'kind', 'name', 'complexity')}, 'source': row['file'], 'target_type': target_type, 'target': target, 'wave': wave,
                         'owner': registered[account]['team'] if account else '@otterworks/data-platform', 'owner_source': 'DBQL readership via consumers/registry.yaml' if account else 'proposed',
                         'risk': 'high' if reasons or row['complexity'] == 'high' else 'med' if row['complexity'] == 'medium' else 'low', 'risk_reasons': reasons, 'status': 'not_started'})
    # Dependency edges describe data availability, not execution sequencing within a wave.
    entries = {r['id']: r for r in manifest}
    retired = {r['id'] for r in manifest if r['name'] in dead}
    while True:
        previous = set(retired)
        for row in manifest:
            node = row['id']
            if node in retired or row['kind'] in ('catalog', 'workflow', 'worklet'):
                continue
            if row['kind'] == 'session':
                downstream = {a for a, b in normalized if b == node and a in entries and entries[a]['kind'] == 'mapping'}
            else:
                downstream = {b for a, b in normalized if a == node and b in entries and entries[b]['kind'] not in ('session', 'workflow', 'worklet')}
                if row['kind'] == 'table' and '.STG_' in row['name']:
                    core = by_name.get(row['name'].replace('.STG_', '.'))
                    if core:
                        downstream.add(core)
            if downstream and downstream <= retired:
                retired.add(node)
        if previous == retired:
            break
    dependents = sorted(entries[node]['name'] for node in retired if entries[node]['name'] not in dead)
    for node in retired:
        if entries[node]['name'] not in dead:
            entries[node].update(target_type='retire', target='NONE', wave=1)
            entries[node]['risk_reasons'].append('feeds only dead objects')
    dependencies = sorted((a, b) for a, b in normalized if a in entries and b in entries and entries[a]['target_type'] != 'retire' and entries[b]['target_type'] != 'retire')
    for _ in range(len(entries) * 4):
        before = [r['wave'] for r in manifest]
        for a, b in dependencies:
            entries[b]['wave'] = max(entries[a]['wave'], entries[b]['wave'])
        if before == [r['wave'] for r in manifest]:
            break
    setup_only = sorted(name for name, qs in reads.items() if qs and all(q['StartTime'][:10] == '2026-08-12' for q in qs))
    cost = yaml.safe_load((root / 'etl/informatica/licence.yaml').read_text())['variables']
    counters = {'teradata_objects': {'remaining': len(catalog), 'target': 0}, 'powercenter_mappings': {'remaining': len(mapping_files), 'target': 0}, 'spark_executor_hours': {'remaining': 0, 'target': 0, 'status': 'no Spark estate on branch yet'}, 'powercenter_annual_cost': {'value': cost['ANNUAL_COST'], 'currency': cost['ANNUAL_COST_CURRENCY']}}
    return {'artifacts': sorted(artifacts, key=lambda r: r['id']), 'objects': manifest, 'consumers': consumers, 'dead': dead, 'dead_dependents': dependents, 'setup_only': setup_only, 'scans': scans, 'links': sorted(normalized), 'dependencies': dependencies, 'feeds': sorted(feeds), 'counters': counters}


def board(objects, counters):
    return {'waves': {str(w): {'total': sum(r['wave'] == w for r in objects), 'by_kind': dict(sorted(Counter(r['kind'] for r in objects if r['wave'] == w).items())), 'by_target': dict(sorted(Counter(r['target_type'] for r in objects if r['wave'] == w).items()))} for w in range(1, 5)}, 'licence_counters': counters}


def main():
    data = build()
    with (OUT / 'inventory.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator='\n')
        writer.writeheader()
        writer.writerows(data['artifacts'])
    payload = {k: data[k] for k in ('objects', 'consumers', 'dead', 'dead_dependents', 'setup_only', 'dependencies')}
    (OUT / 'manifest.yaml').write_text(yaml.safe_dump(payload, sort_keys=False))
    b = board(data['objects'], data['counters'])
    (OUT / 'board/board.json').write_text(json.dumps(b, indent=2) + '\n')
    summary = {'by_kind': dict(sorted(Counter(r['kind'] for r in data['artifacts']).items())), 'total': len(data['artifacts']), 'loc_total': sum(r['loc'] for r in data['artifacts']), 'complexity': dict(Counter(r['complexity'] for r in data['artifacts'])), 'dead': data['dead'], 'setup_only_reads_not_dead': data['setup_only'], 'not_in_warehouse_etl': [u for u, v in data['scans'].items() if not v['warehouse_etl_hits']], 'not_in_any_repo_code': [u for u, v in data['scans'].items() if not v['repo_hits']], 'waves': b['waves'], 'licence_counters': data['counters']}
    summary['dead_dependents'] = data['dead_dependents']
    (OUT / 'inventory.md').write_text('# Inventory\n\nAs of 2026-11-10; DBQL window 2026-08-12 through 2026-11-09 inclusive.\n\n```json\n' + json.dumps(summary, indent=2) + '\n```\n\n0 Spark jobs found. `etl/spark` absent. `migration/job/ldm/engines/spark_load.py` is a separate legacy demo, excluded.\n\nScan evidence for every DBQL reader (tracked repository text, excluding DBQL, tests and generated assessment):\n\n```json\n' + json.dumps(data['scans'], indent=2) + '\n```\n')
    lines = ['# Lineage', '', '```mermaid', 'flowchart LR']
    groups = defaultdict(list)
    for r in data['artifacts']:
        group = 'staging' if '.STG_' in r['name'] else 'core' if r['kind'] == 'table' else 'serving' if r['kind'] in ('view', 'macro', 'procedure', 'catalog') else 'landing_loads' if r['kind'] in ('fastload', 'tpt') else 'transforms'
        groups[group].append((r['id'], r['name']))
    groups['source_feeds'] = [(uid('feed:' + f), re.sub(r'[^\w./-]', '_', f)) for f in data['feeds']]
    groups['consumers'] = [(r['id'], r['name']) for r in data['consumers']]
    for group, members in sorted(groups.items()):
        lines += ['  subgraph ' + group]
        lines += ['    ' + node + '["' + name + '"]' for node, name in members]
        lines += ['  end']
    lines += ['  ' + (uid(a) if a.startswith('feed:') else a) + ' --> ' + b for a, b in data['links']]
    lines += ['  classDef hidden fill:#ffd6a5,stroke:#c00', '  classDef dead fill:#ddd,stroke:#888,stroke-dasharray:5']
    lines += ['  class ' + r['id'] + ' hidden' for r in data['consumers'] if r['hidden']]
    lines += ['  class ' + r['id'] + ' dead' for r in data['artifacts'] if r['name'] in data['dead']]
    lines += ['```', '', f"{len(data['artifacts'])} artifacts; {len(data['feeds'])} feed nodes; {len(data['consumers'])} consumers; {len(data['links'])} parsed edges. Orange = unregistered consumer; gray dashed = no DBQL usage. Arrows indicate data dependency; session/workflow arrows indicate containment dependencies."]
    (OUT / 'lineage.md').write_text('\n'.join(lines) + '\n')
    table = '| Count | Wave 1 | Wave 2 | Wave 3 | Wave 4 |\n|---|---:|---:|---:|---:|\n'
    table += '| Total | ' + ' | '.join(str(b['waves'][str(w)]['total']) for w in range(1, 5)) + ' |\n'
    for field in ('by_kind', 'by_target'):
        for key in sorted({k for v in b['waves'].values() for k in v[field]}):
            table += '| ' + field + ': ' + key + ' | ' + ' | '.join(str(b['waves'][str(w)][field].get(key, 0)) for w in range(1, 5)) + ' |\n'
    (OUT / 'board/README.md').write_text('# Migration board\n\n' + table + '\n## Licence counters\n\n| Counter | Remaining | Target |\n|---|---:|---:|\n' + '\n'.join(f"| {k} | {v['remaining']} | {v['target']} |" for k, v in data['counters'].items() if 'remaining' in v) + f"\n\nPowerCenter annual cost: {data['counters']['powercenter_annual_cost']['value']} USD. Spark: 0 measured executor-hours; no Spark estate on branch yet. Later acts drive remaining counters to zero via MIGRATION_CONTROL status. Consumer repointing (including hidden accounts) and decommission are Wave 4 gates.\n")
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
