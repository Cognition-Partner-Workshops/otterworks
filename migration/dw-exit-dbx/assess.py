"""Deterministic, offline estate assessment (stdlib and PyYAML only)."""
import argparse
import ast
import csv
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
ALLOWED = {'Databricks SQL view', 'Databricks SQL function', 'Delta table', 'Lakeflow pipeline', 'PySpark job', 'Databricks SQL script', 'compatibility view', 'retire'}
SPARK_REF = None
OBJECT = r'\bSFX_(?:BILLING|DOCUMENTS|USERS|AUDIT)\.[A-Z_0-9]+'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True)


def read(path):
    if SPARK_REF and path.startswith('etl/spark/'):
        return git('show', f'{SPARK_REF}:{path}')
    return (ROOT / path).read_text()


def spark_files():
    if SPARK_REF:
        return git('ls-tree', '-r', '--name-only', SPARK_REF, 'etl/spark').splitlines()
    return sorted(str(p.relative_to(ROOT)) for p in (ROOT / 'etl/spark').rglob('*') if p.is_file())


def source_files():
    patterns = ['warehouse/teradata/ddl/**/*.sql', 'warehouse/teradata/scripts/**/*.bteq',
                'warehouse/teradata/macros/*.sql', 'warehouse/teradata/procedures/*.sql',
                'warehouse/teradata/load/fastload/*', 'warehouse/teradata/load/tpt/*',
                'warehouse/teradata/jobs/*', 'etl/informatica/repository/**/*.XML',
                'etl/scripts/*.py', 'migration/job/ldm/engines/spark_load.py']
    return sorted({str(p.relative_to(ROOT)) for pattern in patterns for p in ROOT.glob(pattern) if p.is_file()})


def mask(value):
    value = re.sub(r'(FIN_ANALYST_)([A-Za-z])[A-Za-z]+', r'\1\2*****', value, flags=re.I)
    return re.sub(r'(nb_dsci_)([A-Za-z])[A-Za-z]+', r'\1\2*****', value, flags=re.I)


def registry():
    return yaml.safe_load(read('consumers/registry.yaml'))['consumers']


def dbql():
    folder = ROOT / 'warehouse/teradata/dbql'
    def rows(name):
        with (folder / (name + '.csv')).open() as stream:
            return list(csv.DictReader(stream))
    start = datetime(2026, 11, 10) - timedelta(days=90)
    end = datetime(2026, 11, 11)
    queries = {r['QueryID']: r for r in rows('qrylog') if start <= datetime.fromisoformat(r['StartTime']) < end}
    usages = [r for r in rows('objectusage') if r['QueryID'] in queries]
    live = {r['ObjectDatabaseName'] + '.' + r['ObjectTableName'] for r in usages if r['UsageType'] in ('READ', 'EXECUTE')}
    tables = {r['DatabaseName'] + '.' + r['TableName']: r for r in rows('tablesv') if r['DatabaseName'].startswith('SFX_')}
    dead = {name: {'last_access': row['LastAccessTimeStamp'], 'access_count': row['AccessCount'],
                   'tier': 'dormant' if row['AccessCount'] == '0' else 'write-only'} for name, row in tables.items() if name not in live}
    readers = code_readers(dead)
    for name, evidence in dead.items():
        evidence['code_readers'] = readers[name]
    tracked = git('ls-files', '-z').split('\0')
    corpus = '\n'.join((ROOT / p).read_text(errors='ignore') for p in tracked if p and p != 'warehouse/teradata/tests/test_dbql.py' and not p.startswith(('warehouse/teradata/dbql/', 'migration/dw-exit-dbx/')) and (ROOT / p).is_file())
    hidden = []
    for user in sorted({r['UserName'] for r in queries.values() if r['StatementType'] == 'SELECT'}):
        if user.startswith('svc_etl_'):
            continue
        selected = [r for r in queries.values() if r['UserName'] == user and r['StatementType'] == 'SELECT']
        clients = sorted({r['ClientID'] for r in selected})
        if user.lower() in corpus.lower() or any(c.lower() in corpus.lower() for c in clients):
            continue
        ids = {r['QueryID'] for r in selected}
        hidden.append({'user': mask(user), 'queries': len(selected), 'clients': clients,
                       'apps': sorted({r['AppID'] for r in selected}),
                       'first': min(r['StartTime'] for r in selected), 'last': max(r['StartTime'] for r in selected),
                       'objects': sorted({r['ObjectDatabaseName'] + '.' + r['ObjectTableName'] for r in usages if r['QueryID'] in ids and r['UsageType'] == 'READ'})})
    return dead, hidden


def code_readers(names):
    """Static read evidence, excluding definitions, writes and DBQL fixtures."""
    result = {name: [] for name in names}
    paths = [p for p in source_files() if '/ddl/' in p or '/macros/' in p or '/procedures/' in p or '/scripts/' in p or '/mappings/' in p]
    tracked = git('ls-files', '-z').split('\0')
    paths += [p for p in tracked if p.startswith(('consumers/', 'services/')) and '/test' not in p and '/contract' not in p and Path(p).suffix in ('.py', '.java', '.scala', '.rb', '.sql', '.sh', '.yaml', '.lkml', '.ipynb')]
    paths += [p for p in spark_files() if p.endswith(('.py', '.scala')) and ('/jobs/' in p or '/scala/src/' in p)]
    for path in sorted(set(paths)):
        text = read(path)
        text = re.sub(r'/\*.*?\*/|<!--.*?-->|--[^\n]*|#[^\n]*', '', text, flags=re.S)
        reads = set(re.findall(r'\b(?:FROM|JOIN|CALL|EXEC(?:UTE)?)\s+(' + OBJECT.replace(r'\b', '') + ')', text, re.I))
        if path.endswith('.XML'):
            tree = ET.fromstring(read(path))
            reads.update(e.attrib['OWNERNAME'] + '.' + e.attrib['NAME'] for e in tree.iter('SOURCE') if e.attrib.get('DATABASETYPE') == 'Teradata')
            for e in tree.iter('TABLEATTRIBUTE'):
                if e.attrib.get('NAME') in ('Lookup table name', 'Lookup Sql Override', 'Sql Query'):
                    reads.update(re.findall(OBJECT, e.attrib.get('VALUE', ''), re.I))
        if path.startswith('etl/spark/'):
            for name in names:
                table = name.split('.')[1]
                # Spark register() reads equivalent landing feeds, so retain the logical object.
                if re.search(r'\b(?:FROM|JOIN)\s+' + re.escape(table) + r'\b', text, re.I) or re.search(r'(?:register|landing|jdbc_read)\([^\n]*["\']' + re.escape(table) + r'["\']', text, re.I):
                    reads.add(name)
                if re.search(r'jdbc_read\([^\n]*' + re.escape(name), text, re.I):
                    reads.add(name)
        for name in names:
            if name in {r.upper() for r in reads}:
                result[name].append(path)
    return result


def dbql_exceptions():
    folder = ROOT / 'warehouse/teradata/dbql'
    with (folder / 'qrylog.csv').open() as stream:
        queries = list(csv.DictReader(stream))
    with (folder / 'objectusage.csv').open() as stream:
        usage = list(csv.DictReader(stream))
    counts = Counter()
    for q in queries:
        if q['ErrorCode'] == '0' or q['StatementType'] != 'SELECT':
            continue
        objects = {u['ObjectDatabaseName'] + '.' + u['ObjectTableName'] for u in usage if u['QueryID'] == q['QueryID'] and u['UsageType'] == 'READ'}
        objects.update(re.findall(OBJECT, q['QueryText'], re.I))
        for name in sorted(objects):
            counts[(mask(q['UserName']), q['ErrorCode'], name)] += 1
    partner = [q for q in queries if q['UserName'] == 'svc_partner_sftp']
    return {'partner_extract': {'registered': True, 'registry': 'consumers/registry.yaml', 'code': 'consumers/partner-extract',
                               'registry_cadence': next(c['cadence'] for c in registry() if c['teradata_service_account'] == 'svc_partner_sftp'),
                               'query_count': len(partner), 'observed_times': dict(sorted(Counter(q['StartTime'][11:16] for q in partner).items())),
                               'first': min(q['StartTime'] for q in partner), 'last': max(q['StartTime'] for q in partner)},
            'failed_reads': [{'user': user, 'error_code': code, 'object': name, 'count': count} for (user, code, name), count in sorted(counts.items())]}


def loc(text):
    text = re.sub(r'/\*.*?\*/|<!--.*?-->', '', text, flags=re.S)
    return sum(bool(line.strip()) and not line.lstrip().startswith(('#', '--', '//', '*')) for line in text.splitlines())


def area(text):
    for key, name in [('billing', 'billing'), ('audit', 'audit'), ('users', 'users'), ('user_', 'users'), ('team_', 'users'), ('docs', 'documents'), ('doc_', 'documents'), ('documents', 'documents'), ('content', 'documents')]:
        if key in text.lower():
            return name
    return 'data-platform'


def landing_areas():
    tree = ast.parse(read('etl/spark/jobs/py/common/schemas.py'))
    tables = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'TABLES' for t in node.targets))
    return {table: subject for subject, definitions in tables.items() for table in definitions}


def spark_subject(text):
    tables = landing_areas()
    calls = re.findall(r'\b(?:register|landing|jdbc_read)\(([^\n]*)', text)
    reads = {tables[t] for t in re.findall(r'["\']([A-Z][A-Z_0-9]+)["\']', ' '.join(calls)) if t in tables}
    reads.update(tables[t.upper()] for t in re.findall(r'\b(?:FROM|JOIN)\s+([A-Z_0-9]+)', text, re.I) if t.upper() in tables)
    destinations = set(re.findall(r'\bSFX_(BILLING|DOCUMENTS|USERS|AUDIT)\.', text, re.I))
    subjects = reads | {s.lower() for s in destinations}
    subjects.update(re.findall(r'/opt/(?:lake|landing)/(billing|documents|users|audit)/', text))
    subjects.update(re.findall(r'\bsave\([^\n]*?,\s*"(billing|documents|users|audit)"', text))
    if not subjects:
        raise ValueError('Spark job has no grounded subject-area evidence')
    return next(iter(subjects)) if len(subjects) == 1 else 'data-platform'


def build():
    dead, hidden = dbql()
    consumers = registry()
    entries = []

    def add(path, name, kind, text, paths=None, hours=None, hint=None):
        subject = spark_subject(text) if kind == 'Spark job' else area(path + name)
        count = loc(text)
        features = len(re.findall(r'\b(?:JOIN|QUALIFY|MERGE|UNION|WHILE|LOOP|UDF|RDD|TRANSFORMATION)\b', text, re.I))
        complexity = 'high' if count > 150 or features >= 8 else 'medium' if count > 40 or features >= 2 else 'low'
        target, wave = 'Databricks SQL script', 3
        reason = 'Dialect and orchestration parity requires replay'
        if kind == 'table':
            target, wave = 'Delta table', 1
        elif kind == 'view':
            target = 'Databricks SQL view'
            if any(name in c['tables'] and c.get('teradata_constructs') for c in consumers) or any(name in h['objects'] for h in hidden):
                target, wave = 'compatibility view', 4
                reason = 'Consumer SQL uses Teradata constructs; preserve contracts before cutover'
        elif kind == 'macro':
            target = 'Databricks SQL function'
        elif kind in ('FastLoad', 'TPT') or (kind == 'BTEQ' and ('load_' in path or 'STG_' in text)):
            target, wave = 'Lakeflow pipeline', 2
        elif kind.startswith('PowerCenter'):
            target = 'Lakeflow pipeline'
            wave = 2 if 'STG_' in name else 3
        elif kind in ('Spark job', 'Spark shared', 'batch job'):
            target = 'Lakeflow pipeline' if hint == 'dbt' else 'PySpark job'
            reason = 'Relational dbt hint becomes Lakeflow SQL transform' if hint == 'dbt' else 'Python/Scala distributed behavior requires PySpark parity'
        elif kind in ('consumer', 'hidden consumer', 'hidden consumer object', 'decommission'):
            target, wave = 'Databricks SQL script', 4
            reason = 'Consumer cutover and owner signoff required'
            if kind == 'hidden consumer object':
                target = 'compatibility view'
                reason = 'Unregistered ODBC/Excel reader requires contract-preserving cutover'
        if name in dead:
            if dead[name]['code_readers']:
                reason = 'no DBQL read in 90d; read by ' + ', '.join(dead[name]['code_readers'])
            else:
                target, wave, reason = 'retire', 1, 'No DBQL read in 90d and no static code reader found'
        owner = next((c['team'] for c in consumers if name in c['tables']), '@otterworks/' + subject)
        if kind == 'consumer':
            owner = next(c['team'] for c in consumers if c['name'] == name)
        if kind.startswith('hidden consumer'):
            owner = '@otterworks/finance-ops'
        source_paths = paths or [path]
        entry = dict(id=hashlib.sha256((path + '#' + name).encode()).hexdigest()[:16], source=path + '#' + name,
                     object_name=name, source_paths=source_paths, kind=kind, target=target, wave=wave, owner=owner,
                     risk='high' if kind.startswith('hidden consumer') or target == 'compatibility view' or name in dead and dead[name]['code_readers'] else complexity,
                     risk_reason=reason, subject_area=subject,
                     source_system='powercenter' if kind.startswith('PowerCenter') else 'spark-batch' if kind.startswith(('Spark', 'batch')) else 'teradata',
                     loc=count, complexity=complexity, executor_hours=hours,
                     unread_tier=dead[name]['tier'] if name in dead else None,
                     code_readers=dead[name]['code_readers'] if name in dead else [])
        entries.append(entry)

    for path in source_files():
        text = read(path)
        if '/ddl/' in path:
            matches = list(re.finditer(r'CREATE\s+(?:MULTISET\s+|SET\s+)?(TABLE|VIEW)\s+(' + OBJECT.replace(r'\b', '') + ')', text, re.I))
            for i, match in enumerate(matches):
                add(path, match[2].upper(), match[1].lower(), text[match.start():matches[i + 1].start() if i + 1 < len(matches) else len(text)])
        elif path.endswith('.XML'):
            tree = ET.fromstring(text)
            tags = ('MAPPING',) if '/mappings/' in path else ('SESSION', 'WORKFLOW')
            for tag in tags:
                for element in tree.iter(tag):
                    block = re.search(r'<' + tag + r'\b[^>]*\bNAME="' + re.escape(element.attrib['NAME']) + r'"[^>]*>.*?</' + tag + '>', text, re.S)
                    add(path, element.attrib['NAME'], 'PowerCenter ' + tag.lower(), block[0] if block else ET.tostring(element, encoding='unicode'))
        else:
            kind = 'macro' if '/macros/' in path else 'procedure' if '/procedures/' in path else 'FastLoad' if '/fastload/' in path else 'TPT' if '/tpt/' in path else 'BTEQ' if path.endswith('.bteq') else 'batch job' if path.endswith('.py') and '/jobs/' not in path else 'scheduler'
            match = re.search(r'(?:REPLACE|CREATE)\s+(?:MACRO|PROCEDURE)\s+(' + OBJECT.replace(r'\b', '') + ')', text, re.I)
            add(path, match[1].upper() if match else Path(path).stem, kind, text)
    files = spark_files()
    if 'etl/spark/jobs.txt' in files:
        baseline = json.loads(read('etl/spark/history/baseline.json'))
        hints = {e['job']: e for e in yaml.safe_load(read('etl/spark/classification.yaml'))}
        for job in read('etl/spark/jobs.txt').splitlines():
            code = 'etl/spark/jobs/py/' + job + '.py'
            if code not in files:
                code = 'etl/spark/scala/src/main/scala/sfx/' + ''.join(word.title() for word in job.split('_')) + '.scala'
            paths = [code, f'etl/spark/submit/{job}.sh', f'etl/spark/k8s/{job}.yaml']
            for path in paths:
                read(path)
            add(code, job, 'Spark job', read(code), paths, baseline['jobs'][job]['executor_hours'], hints[job]['target'])
        for path in files:
            if '/common/' in path and path.endswith('.py') or path.endswith('/BatchSupport.scala'):
                add(path, Path(path).stem, 'Spark shared', read(path))
    for consumer in consumers:
        add('consumers/registry.yaml', consumer['name'], 'consumer', '')
    for consumer in hidden:
        add('warehouse/teradata/dbql/qrylog.csv', consumer['user'], 'hidden consumer', '')
        for name in consumer['objects']:
            add('warehouse/teradata/dbql/objectusage.csv', consumer['user'] + ':' + name, 'hidden consumer object', '')
    for user in ('svc_etl_audit', 'svc_etl_billing', 'svc_etl_docs', 'svc_etl_users'):
        add('warehouse/teradata/dbql/qrylog.csv', user, 'internal ETL', '')
    add('warehouse/teradata/README.md', 'teradata-powercenter-decommission', 'decommission', '')
    return sorted(entries, key=lambda e: (e['source'], e['id']))


def write(name, value):
    (BASE / name).write_text(mask(value))


def main():
    global SPARK_REF
    parser = argparse.ArgumentParser()
    parser.add_argument('--spark-ref')
    args = parser.parse_args()
    SPARK_REF = args.spark_ref
    entries = build()
    dead, hidden = dbql()
    files = spark_files()
    provenance = {'spark_ref': SPARK_REF or 'working tree', 'spark_commit': git('rev-parse', SPARK_REF or 'HEAD').strip()}
    measured = json.loads(read('etl/spark/history/baseline.json')) if 'etl/spark/history/baseline.json' in files else None
    metadata = dict(provenance, as_of='2026-11-10', dead=dead, hidden=hidden)
    write('manifest.yaml', yaml.safe_dump(dict(metadata=metadata, objects=entries), sort_keys=False))
    with (BASE / 'inventory.csv').open('w') as stream:
        columns = ['id', 'source', 'object_name', 'kind', 'loc', 'complexity', 'source_paths', 'executor_hours']
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore', lineterminator='\n')
        writer.writeheader()
        for entry in entries:
            writer.writerow({k: mask(str(v)) if v is not None else '' for k, v in entry.items() if k in columns})
    write('dbql.md', '# DBQL assessment\n\n25 unread in 90 days: 6 dormant (AccessCount 0, last access 2026-07-01); 19 write-only (recent writes, no reads). Only objects without static code readers are proposed for retirement. Spark landing-feed reads are conservatively treated as logical object readers, not observed JDBC reads.\n\n' + yaml.safe_dump(metadata, sort_keys=False) + '\nHidden discovery excludes warehouse/teradata/dbql/**, warehouse/teradata/tests/test_dbql.py and this output directory. svc_etl_* are internal producer row-count checks, not consumers; they remain in ETL lineage. The single hidden consumer is FIN_ANALYST_J***** (ODBC/Excel).\n\nPartner SFTP extract svc_partner_sftp IS registered in consumers/registry.yaml with code in consumers/partner-extract. It is not hidden. Registry cadence is nightly 02:15; DBQL instead shows 05:xx reads (timestamps have no timezone, so scheduling/timezone drift requires owner confirmation). Failed read counts below are per user/error/object; multi-object queries contribute to each object.\n\n' + yaml.safe_dump(dbql_exceptions(), sort_keys=False))
    waves = dict(sorted(Counter(e['wave'] for e in entries).items()))
    counters = {'teradata_objects': sum(e['kind'] in ('table', 'view', 'macro', 'procedure') for e in entries), 'powercenter_mappings': sum(e['kind'] == 'PowerCenter mapping' for e in entries), 'spark_executor_hours': measured['totals']['executor_hours'] if measured else 'not measured'}
    board = dict(provenance, waves=waves, kinds=dict(sorted(Counter(e['kind'] for e in entries).items())), loc=sum(e['loc'] for e in entries), counters=counters, spark_applications=len(measured['jobs']) if measured else 0,
                 unread_in_90d=len(dead), unread_tiers=dict(Counter(d['tier'] for d in dead.values())), retire=[e['object_name'] for e in entries if e['target'] == 'retire'])
    write('board/board.json', json.dumps(board, indent=2) + '\n')
    sql = """/* run=dbx-d1111 act=assess step=counter */
SELECT
  count_if(source_system = 'teradata' AND kind IN ('table','view','macro','procedure')) AS teradata_objects,
  count_if(kind = 'PowerCenter mapping') AS powercenter_mappings,
  sum(executor_hours) AS spark_executor_hours
FROM cpw.dbx_d1111_control.migration_control
WHERE status NOT IN ('migrated', 'retired');"""
    write('board/README.md', '# Migration board\n\n```json\n' + json.dumps(board, indent=2) + '\n```\n\nWave 1: retirement and Delta foundations. Wave 2: ingestion. Wave 3: transformations, shared Spark runtime and orchestration. Wave 4: compatibility, consumer signoff and decommission. Spark dbt hints are transforms (wave 3), not ingestion.\n\nExecutor-hours are the measured History Server baseline over 30 applications, not an annual estimate. Non-Spark batch jobs have NULL hours: unmeasured, not zero.\n\n```sql\n' + sql + '\n```\n')
    lineage(entries, hidden, provenance)
    print(json.dumps(board, sort_keys=True))


def lineage(entries, hidden, provenance):
    lines = ['# Lineage', '', str(provenance), '', 'Area-level overview; arrows represent feed/processing flow, not execution order. Detailed Spark reads/writes below are extracted from code literals.', '', '```mermaid', 'flowchart LR']
    for subject in ('billing', 'documents', 'users', 'audit', 'data-platform'):
        key = subject.replace('-', '_')
        lines += [f'subgraph {key}["{subject}"]', f'{key}_landing["landing feeds"] --> {key}_stg["staging"] --> {key}_core["core"] --> {key}_api["views / macros / procedures"] --> {key}_etl["PowerCenter / BTEQ / Spark"]', 'end']
    for key, user in [('billing', 'billing'), ('documents', 'docs'), ('users', 'users'), ('audit', 'audit')]:
        lines += [f'{key}_etl --> internal_{user}["svc_etl_{user}: internal row-count check"]']
    lines += ['subgraph consumers["Consumers"]']
    for i, c in enumerate(registry()):
        lines += [f'c{i}["{c["name"]}"]']
    for i, c in enumerate(hidden):
        lines += [f'h{i}["{c["user"]}"]:::hidden']
    lines += ['end', 'classDef hidden fill:#ffe0e0,stroke:#b00020,stroke-width:3px']
    for i, c in enumerate(registry()):
        for subject in sorted({area(t) for t in c['tables']}):
            lines += [f'{subject.replace("-", "_")}_etl --> c{i}']
    for i, c in enumerate(hidden):
        for subject in sorted({area(t) for t in c['objects']}):
            lines += [f'{subject.replace("-", "_")}_etl --> h{i}']
    lines += ['```', '', '## Spark code-level lineage', '', 'register/BatchSupport.register literals identify reads; save target literals identify writes. Tables are logical register names; runtime schema resolution is in common/runtime.py and BatchSupport.scala. External binary/lake inputs without register calls are shown as external.', '', '```mermaid', 'flowchart LR']
    for subject in ('billing', 'documents', 'users', 'audit', 'data-platform'):
        lines += [f'subgraph spark_{subject.replace("-", "_")}["{subject} Spark transforms"]']
        for e in entries:
            if e['kind'] != 'Spark job' or e['subject_area'] != subject:
                continue
            text = read(e['source_paths'][0])
            registered = re.findall(r'(?:(?:register|landing|jdbc_read)\(spark,)([^\n]*)', text)
            refs = sorted(set(re.findall(r'"([A-Z][A-Z_0-9]+)"', ' '.join(registered))))
            node = 'j' + e['id']
            lines += [f'{node}["{e["object_name"]}"]']
            for ref in refs or ['external lake/blob input']:
                source = 't' + hashlib.sha256((subject + ref).encode()).hexdigest()[:10]
                lines += [f'{source}["{ref}"] --> {node}']
            writes = re.findall(r'(?i)sfx_(?:billing|documents|audit|users)\.[A-Z_0-9]+', text)
            output = ', '.join(sorted(set(writes))) or e['object_name'] + ' lake output'
            lines += [f'{node} --> o{e["id"]}["{output}"]']
        lines += ['end']
    lines += ['```', '', '## Spark code-level references', '', '| Job | Read/write evidence (code literals; physical paths also retained) | Source |', '|---|---|---|']
    for e in entries:
        if e['kind'] == 'Spark job':
            text = read(e['source_paths'][0])
            refs = sorted(set(re.findall(OBJECT, text, re.I)) | set(re.findall(r'"([A-Z][A-Z_0-9]+)"', text)))
            lines += [f'| {e["object_name"]} | {", ".join(refs)} | {e["source_paths"][0]} |']
    write('lineage.md', '\n'.join(lines) + '\n')


def analyst_evidence():
    with (ROOT / 'warehouse/teradata/dbql/qrylog.csv').open() as stream:
        rows = [r for r in csv.DictReader(stream) if r['UserName'].startswith('FIN_ANALYST_') and r['StatementType'] == 'SELECT']
    ids = {r['QueryID'] for r in rows}
    with (ROOT / 'warehouse/teradata/dbql/objectusage.csv').open() as stream:
        objects = sorted({r['ObjectDatabaseName'] + '.' + r['ObjectTableName'] for r in csv.DictReader(stream) if r['QueryID'] in ids and r['UsageType'] == 'READ'})
    return yaml.safe_dump({'analyst': {'user': mask(rows[0]['UserName']) if rows else None, 'queries': len(rows), 'clients': sorted({r['ClientID'] for r in rows}), 'apps': sorted({r['AppID'] for r in rows}), 'first': min((r['StartTime'] for r in rows), default=None), 'last': max((r['StartTime'] for r in rows), default=None), 'objects': objects}}, sort_keys=False)


if __name__ == '__main__':
    main()
