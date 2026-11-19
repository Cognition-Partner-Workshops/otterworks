"""Source-derived table lineage for the bounded daily-chain SQL estate."""

import ast
import re

from lakehouse.runtime.layout import ROOT


WAREHOUSE = ROOT.parent / 'warehouse/teradata'
RELATION = r'SFX_[A-Z]+\.[A-Z_][A-Z_0-9]*'


def stages():
    tree = ast.parse((WAREHOUSE / 'jobs/daily_chain').read_text())
    values = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body
              if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
              and node.targets[0].id in ('CORE', 'REPORTS')}
    return ('setup', 'generate', 'staging', *values['CORE'], *values['REPORTS'],
            'jobs/reconcile', 'audit/11_reconciliation')


def lineage(stage):
    if stage in ('setup', 'generate', 'staging'):
        return set(), set()
    if stage == 'jobs/reconcile':
        source = (WAREHOUSE / 'jobs/reconcile').read_text()
        assert "'.STG_' + args.table.upper()" in source and "'.' + args.table.upper()" in source
        tree = ast.parse((WAREHOUSE / 'jobs/daily_chain').read_text())
        arguments = next(node.args[0].elts for node in ast.walk(tree) if isinstance(node, ast.Call)
                         and isinstance(node.func, ast.Attribute) and node.func.attr == 'run'
                         and node.args and isinstance(node.args[0], ast.List)
                         and any(isinstance(value, ast.Constant) and value.value == '--table'
                                 for value in node.args[0].elts))
        values = [value.value if isinstance(value, ast.Constant) else None for value in arguments]
        area, table = values[values.index('--area') + 1].upper(), values[values.index('--table') + 1].upper()
        writes = set(re.findall(r'\b(?:INSERT\s+INTO|DELETE\s+FROM)\s+('+RELATION+')', source.upper()))
        assert writes
        return {f'SFX_{area}.STG_{table}', f'SFX_{area}.{table}'}, writes
    text = (WAREHOUSE / 'scripts' / (stage + '.bteq')).read_text().upper()
    definitions = {}
    for folder in ('macros', 'procedures'):
        for path in (WAREHOUSE / folder).glob('*.sql'):
            sql = path.read_text().upper()
            name = re.search(r'(?:MACRO|PROCEDURE)\s+('+RELATION+')', sql)
            if name:
                definitions[name[1]] = sql
    pending = re.findall(r'\b(?:CALL|EXEC)\s+('+RELATION+')', text)
    expanded = set()
    while pending:
        name = pending.pop()
        if name in expanded:
            continue
        expanded.add(name)
        sql = definitions[name]
        text += '\n' + sql
        pending += re.findall(r'\b(?:CALL|EXEC)\s+('+RELATION+')', sql)
    writes = set(re.findall(r'\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM|MERGE\s+INTO)\s+('+RELATION+')', text))
    reads = set(re.findall(r'\b(?:FROM|JOIN|USING)\s+('+RELATION+')', text))
    reads |= set(re.findall(r'\bUPDATE\s+('+RELATION+')', text))
    assert set(re.findall(RELATION, text)) <= reads | writes | expanded
    views = {}
    for path in (WAREHOUSE / 'ddl').glob('*/*views.sql'):
        views.update(re.findall(r'(?:REPLACE|CREATE)\s+VIEW\s+('+RELATION+r')\s+AS\s+(.*?);',
                                path.read_text().upper(), re.S))
    pending = list(reads & views.keys())
    expanded = set()
    while pending:
        name = pending.pop()
        if name not in expanded:
            expanded.add(name)
            children = set(re.findall(r'\b(?:FROM|JOIN)\s+('+RELATION+')', views[name]))
            reads |= children
            pending += list(children & views.keys())
    return reads, writes


def ancestors(nodes, identity):
    result, pending = set(), list(nodes[identity]['depends_on'])
    while pending:
        name = pending.pop()
        if name not in result:
            result.add(name)
            pending += nodes[name]['depends_on']
    return result
