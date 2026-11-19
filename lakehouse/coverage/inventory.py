"""Discover migration units without importing or executing legacy code."""

import ast
import hashlib
import re
from pathlib import Path

import yaml
from defusedxml import ElementTree as ET

from lakehouse.runtime.layout import ROOT

REPO = ROOT.parent


def discover(root=REPO):
    root = Path(root)
    objects = {}

    def add(kind, name, path, line=None, **metadata):
        relative = path.relative_to(root).as_posix()
        source = relative + (f'#L{line}' if line else '')
        identity = f'{kind}:{name}'
        if identity not in objects:
            objects[identity] = {'id': identity, 'kind': kind, 'name': name,
                                 'source': source, 'sources': [], **metadata}
        if source not in objects[identity]['sources']:
            objects[identity]['sources'].append(source)

    warehouse = root / 'warehouse/teradata'
    for directory in ('ddl', 'macros', 'procedures', 'dbql'):
        for path in sorted((warehouse / directory).rglob('*.sql')):
            text = path.read_text()
            text = re.sub(r'/\*.*?\*/|--[^\n]*', lambda m: re.sub(r'[^\n]', ' ', m[0]), text, flags=re.S)
            pattern = r'\b(?:CREATE\s+(?:OR\s+REPLACE\s+)?|REPLACE\s+)(?:(?:MULTISET|SET|VOLATILE)\s+)?(TABLE|VIEW|MACRO|PROCEDURE)\s+([\w]+\.[\w]+)'
            for match in re.finditer(pattern, text, re.I):
                add('teradata_' + match[1].lower(), match[2].upper(), path,
                    text.count('\n', 0, match.start()) + 1)
    for directory in (warehouse / 'scripts', warehouse / 'dbql', root / 'consumers/partner-extract/sql'):
        for path in sorted(directory.rglob('*')):
            if path.suffix.lower() in ('.bteq', '.sql') and path.name != 'schema.sql':
                add('bteq_script', path.relative_to(root).as_posix(), path)
    for directory, kind, suffix in (('fastload', 'fastload', '.fl'), ('tpt', 'tpt', '.tpt')):
        for path in sorted((warehouse / 'load' / directory).glob('*' + suffix)):
            add(kind, path.relative_to(root).as_posix(), path)

    xml_tags = {'MAPPING': 'mapping', 'WORKFLOW': 'workflow', 'SESSION': 'session',
                'WORKLET': 'worklet', 'TASK': 'task', 'CONFIG': 'config',
                'SOURCE': 'source', 'TARGET': 'target', 'SCHEDULER': 'scheduler',
                'MAPPLET': 'mapplet'}
    for path in sorted((root / 'etl/informatica/repository').rglob('*')):
        if path.suffix.lower() != '.xml':
            continue
        for folder in ET.parse(path).getroot().iter('FOLDER'):
            def visit(element, scope=()):
                kind = xml_tags.get(element.tag)
                if element.tag == 'TRANSFORMATION' and element.get('REUSABLE') == 'YES':
                    kind = 'transformation'
                if kind and element.get('NAME'):
                    qualifiers = scope if element.tag in ('TASK', 'SESSION', 'SCHEDULER') and element.get('REUSABLE') != 'YES' else ()
                    name = '.'.join((folder.attrib['NAME'], *qualifiers, element.attrib['NAME']))
                    add('informatica_' + kind, name, path)
                if element.tag in ('WORKFLOW', 'WORKLET'):
                    scope = (*scope, element.attrib['NAME'])
                for child in element:
                    visit(child, scope)
            visit(folder)
    for path in sorted((root / 'etl/informatica/params').glob('*.par')):
        if re.search(r'^\$\$\w+\s*=', path.read_text(), re.M):
            add('informatica_param', path.relative_to(root).as_posix(), path)
    for path in sorted((root / 'etl/informatica/config').glob('*.yaml')):
        content = yaml.safe_load(path.read_text()) or {}
        for name, config in content.get('connections', {}).items():
            if any(key in config for key in ('default_database', 'code_page', 'sql', 'pre_sql', 'post_sql')):
                add('informatica_config', path.relative_to(root).as_posix() + '#' + name, path)

    spark = root / 'etl/spark'
    job_list = spark / 'jobs.txt'
    if job_list.exists():
        for line, name in enumerate(job_list.read_text().splitlines(), 1):
            name = name.lstrip('#').strip()
            if re.fullmatch(r'\w+', name):
                add('spark_job', name, job_list, line)
    for path in sorted((spark / 'jobs/py').glob('*.py')):
        if path.name != '__init__.py':
            add('spark_job', path.stem, path, language='python')
            objects[f'spark_job:{path.stem}']['language'] = 'python'
    classes = {}
    for path in sorted((spark / 'submit').glob('*.sh')):
        add('spark_submit', path.relative_to(root).as_posix(), path)
        match = re.search(r'--class\s+([\w.]+)', path.read_text())
        if match:
            classes[match[1].split('.')[-1]] = path.stem
    for path in sorted((spark / 'k8s').glob('*.yaml')):
        app = yaml.safe_load(path.read_text())
        if app.get('kind') == 'SparkApplication':
            add('spark_job', path.stem, path)
    for path in sorted((spark / 'conf').glob('*')):
        if path.is_file():
            add('spark_config', path.relative_to(root).as_posix(), path)
    for path in sorted((spark / 'scala/src/main/scala').rglob('*.scala')):
        names = re.findall(r'\bobject\s+(\w+)', path.read_text())
        for name in names:
            if re.search(r'\bdef\s+main\s*\(', path.read_text()):
                job = classes.get(name, name)
                add('spark_job', job, path, language='scala')
                objects[f'spark_job:{job}']['language'] = 'scala'
            else:
                add('spark_library', path.relative_to(root).as_posix(), path)
    for path in sorted((spark / 'jobs/py/common').glob('*.py')):
        if path.read_text().strip():
            add('spark_library', path.relative_to(root).as_posix(), path)
    for path in sorted((root / 'etl/scripts').glob('*.py')):
        add('etl_script', path.relative_to(root).as_posix(), path)
    for path in (root / 'etl/run.sh', spark / 'run.sh', warehouse / 'jobs/daily_chain', warehouse / 'jobs/reconcile'):
        if path.exists():
            add('batch_runner', path.relative_to(root).as_posix(), path)
    for path in sorted((root / 'consumers/partner-extract/bin').glob('*.sh')):
        add('consumer_script', path.relative_to(root).as_posix(), path)
    config = root / 'etl/config.ini'
    if config.exists():
        add('etl_config', config.relative_to(root).as_posix(), config)
    for path in (root / 'etl/crontab', warehouse / 'jobs/crontab.example'):
        if not path.exists():
            continue
        for number, raw in enumerate(path.read_text().splitlines(), 1):
            disabled = raw.lstrip().startswith('#')
            line = raw.lstrip().removeprefix('#').strip()
            match = re.fullmatch(r'((?:[\d*/,-]+\s+){5})(.+)', line)
            if match:
                digest = hashlib.sha256(match[2].encode()).hexdigest()[:12]
                add('cron_entry', path.relative_to(root).as_posix() + '#' + digest, path,
                    number, disabled=disabled)
    chain = warehouse / 'jobs/daily_chain'
    if chain.exists():
        tree = ast.parse(chain.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ('CORE', 'REPORTS') for t in node.targets):
                for item in node.value.elts:
                    add('cron_entry', chain.relative_to(root).as_posix() + '#stage=' + ast.literal_eval(item), chain, item.lineno)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'stage' and node.args and isinstance(node.args[0], ast.Constant):
                add('cron_entry', chain.relative_to(root).as_posix() + '#stage=' + str(node.args[0].value), chain, node.lineno)
    registry = root / 'consumers/registry.yaml'
    if registry.exists():
        for consumer in yaml.safe_load(registry.read_text())['consumers']:
            add('consumer', consumer['name'], registry, consumer_path=consumer['path'])
    for path in sorted((root / 'consumers/bi').rglob('*')):
        if path.is_file() and path.suffix.lower() not in ('.md', '.txt'):
            add('bi_artifact', path.relative_to(root).as_posix(), path)
    return dict(sorted(objects.items()))
