"""Static Spark estate and packaged listener-history evidence (working tree only)."""

import ast
import importlib.util
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import yaml

NON_READER_PREFIXES = ('warehouse/dbt/', 'warehouse/snowflake/', 'warehouse/parity/',
                       'warehouse/snowpark/', 'warehouse/pipeline/', 'migration/',
                       'etl/airflow/', 'docs/')


def observation_window(runs):
    newest = max((run['start'][:10] for applications in runs.values() for run in applications), default=None)
    if newest is None:
        return None
    end = date.fromisoformat(newest)
    return [(end - timedelta(days=89)).isoformat(), end.isoformat()]


def non_reader_reason(path, registry):
    if path.startswith(NON_READER_PREFIXES) or Path(path).suffix.lower() == '.md':
        return 'migration/replacement artifact or documentation, not legacy output consumption'
    if any(path.startswith(c.get('path', '') + '/') for c in registry):
        return None
    parts = Path(path).parts
    code = {'.py', '.scala', '.sql', '.java', '.kt', '.js', '.ts', '.tsx', '.jsx',
            '.cs', '.go', '.rb', '.rs', '.ipynb', '.r', '.sh'}
    if set(parts) & {'services', 'clients', 'client', 'notebooks', 'notebook'} and Path(path).suffix.lower() in code:
        return None
    return 'not registered-consumer or service/client/notebook code'


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def history(base):
    # compute_baseline imports eventlog by its local module name.
    eventlog = load_module('eventlog', base / 'eventlog.py')
    previous = sys.modules.get('eventlog')
    sys.modules['eventlog'] = eventlog
    try:
        summarize = load_module('spark_baseline', base / 'compute_baseline.py').summarize
    finally:
        if previous is None:
            del sys.modules['eventlog']
        else:
            sys.modules['eventlog'] = previous
    runs = defaultdict(list)
    for path in sorted((base / 'eventlogs').glob('*.zstd')):
        name, run = summarize(eventlog.read_events(path))
        runs[name].append(run)
    baseline = json.loads((base / 'baseline.json').read_text())
    for name, expected in baseline['jobs'].items():
        if expected not in runs[name]:
            raise ValueError('Spark baseline differs from event logs: ' + name)
    return runs


def parse_source(text, scala=False):
    inputs, outputs, jdbc_reads, jdbc_writes = set(), set(), set(), set()
    if scala:
        for match in re.finditer(r'BatchSupport\.(landing|register)\(spark,\s*"([^"]+)"((?:\s*,\s*"[^"]+")+)\)', text):
            inputs.update((match[2], table) for table in re.findall(r'"([^"]+)"', match[3]))
        for match in re.finditer(r'BatchSupport\.save(?:Partition)?\([^\n]*?,\s*"([^"]+)",\s*"([^"]+)"(?:,\s*Some\("([^"]+)"\))?', text):
            outputs.add(match[1] + '/' + match[2])
            if match[3]:
                jdbc_writes.add(match[3].upper())
    else:
        tree = ast.parse(text)
        for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
            name = call.func.id if isinstance(call.func, ast.Name) else ''
            def string(index):
                arg = call.args[index] if len(call.args) > index else None
                return arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else None
            if name in ('landing', 'register'):
                for index in range(1, len(call.args)):
                    if string(index):
                        inputs.add((None, string(index)))
            elif name == 'jdbc_read' and string(1):
                jdbc_reads.add(string(1).upper())
            elif name in ('save', 'save_partition') and string(1) and string(2):
                outputs.add(string(1) + '/' + string(2))
                target = string(3) if name == 'save' else None
                target = next((kw.value.value for kw in call.keywords if kw.arg == 'jdbc_table'
                               and isinstance(kw.value, ast.Constant)), target)
                if target:
                    jdbc_writes.add(target.upper())
            elif name == 'save_jdbc_refresh' and string(1):
                jdbc_writes.add(string(1).upper())
    lake_refs = set(re.findall(r'/opt/lake/([\w]+/[\w]+)', text))
    # Direct parquet writers do not use save().
    if re.search(r'\.write\b', text):
        for match in re.finditer(r'\.parquet\(\s*["\']/opt/lake/([\w]+/[\w]+)', text):
            outputs.add(match[1])
    labels = set()
    for label, pattern in {
        'udf': r'\budf\b', 'rdd': r'\.rdd\b', 'window': r'\bWindow\b|\bOVER\s*\(',
        'graph': r'\bedges\b|\bparents\b', 'binary': r'binaryFile|extract_document',
        'stateful': r'groupByKey|mapWithState|updateStateByKey|\bvar labels\b',
    }.items():
        if re.search(pattern, text, re.I):
            labels.add(label)
    if jdbc_reads or jdbc_writes:
        labels.add('jdbc')
    return dict(inputs=inputs, outputs=outputs, jdbc_reads=jdbc_reads, jdbc_writes=jdbc_writes,
                lake_reads=lake_refs - outputs, constructs=labels)


def cron(text):
    lines = [line.strip() for line in text.splitlines() if '/submit/' in line]
    enabled = [line for line in lines if not line.startswith('#')]
    schedules = [' '.join(line.lstrip('# ').split()[:5]) for line in (enabled or lines)]
    return {'state': 'enabled' if enabled else 'disabled' if lines else 'missing',
            'schedule': '; '.join(schedules) or None}


def analyze(root, scanned, registry):
    base = root / 'etl/spark'
    runs = history(base / 'history')
    window = observation_window(runs)
    schema_tree = ast.parse((base / 'jobs/py/common/schemas.py').read_text())
    tables = ast.literal_eval(next(node.value for node in schema_tree.body
                                  if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'TABLES' for t in node.targets)))
    areas = {table: area for area, names in tables.items() for table in names}
    names = set((base / 'jobs.txt').read_text().split())
    registries = {path.stem: yaml.safe_load(path.read_text()) for path in (base / 'jobs/registry').glob('*.yaml')}
    names |= registries.keys()
    jobs = {}
    for name in sorted(names):
        reg = registries.get(name, {})
        path = base / 'jobs/py' / (name + '.py')
        if not path.exists():
            candidates = [p for p in (base / 'scala/src/main/scala').rglob('*.scala')
                          if re.search(r'\bsession\("' + re.escape(name) + r'"\)', p.read_text())]
            if len(candidates) != 1:
                raise ValueError('Cannot resolve Spark source: ' + name)
            path = candidates[0]
        text = path.read_text()
        parsed = parse_source(text, path.suffix == '.scala')
        parsed['inputs'] = {(area or areas[table], table) for area, table in parsed['inputs']}
        output_areas = {p.split('/')[0] for p in parsed['outputs']}
        area = reg.get('subject_area', reg.get('area'))
        if not area:
            if len(output_areas) != 1:
                raise ValueError('Cannot resolve Spark output area: ' + name)
            area = output_areas.pop()
        job_runs = runs[name]
        window_runs = [run for run in job_runs if window and window[0] <= run['start'][:10] <= window[1]]
        cron_path = base / 'cron.d' / name
        parsed.update(name=name, source=str(path.relative_to(root)), text=text, area=area,
                      readers=[], non_reader_mentions=[], run_evidence={
                          'window': window, 'runs_in_window': len(window_runs),
                          'last_run': max((r['start'] for r in job_runs), default=None),
                          'executor_hours': round(sum(r['executor_hours'] for r in job_runs), 9),
                          'executor_hours_in_window': round(sum(r['executor_hours'] for r in window_runs), 9),
                          'applications': job_runs,
                          'cron': cron(cron_path.read_text() if cron_path.exists() else '')})
        jobs[name] = parsed
    files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
    external = {}
    for name in files:
        if not scanned(name) or name.startswith('etl/spark/'):
            continue
        path = root / name
        if path.is_file():
            external[name] = path.read_text(errors='ignore')
    for name, job in jobs.items():
        for other, reader in jobs.items():
            if other != name and (job['outputs'] & reader['lake_reads'] or job['jdbc_writes'] & reader['jdbc_reads']):
                job['readers'].append({'kind': 'spark_job', 'name': other, 'path': reader['source']})
        for path, text in sorted(external.items()):
            lake_hits = [output for output in job['outputs'] if re.search(r'(?<![\w])' + re.escape(output) + r'(?![\w])', text)]
            # JDBC output readership requires a read site, not merely a write target mention.
            jdbc_hits = [table for table in job['jdbc_writes'] if re.search(r'\b(?:FROM|JOIN)\s+' + re.escape(table) + r'\b', text, re.I)]
            if lake_hits or jdbc_hits:
                accounts = [c['teradata_service_account'] for c in registry if path.startswith(c.get('path', '') + '/')]
                mention = {'kind': 'repo', 'path': path, 'accounts': accounts,
                           'relations': sorted(lake_hits + jdbc_hits)}
                reason = non_reader_reason(path, registry)
                if reason:
                    job['non_reader_mentions'].append({**mention, 'reason': reason})
                else:
                    job['readers'].append(mention)
        job['run_evidence']['readers'] = job['readers']
        job['run_evidence']['non_reader_mentions'] = job['non_reader_mentions']
    return jobs
