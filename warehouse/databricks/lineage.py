"""Compare DBQL-derived source lineage with live Unity Catalog upstream sets."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

import sqlglot
from sqlglot import exp

from .baseline import literal
from .sql import Warehouse
from ..teradata.bteq.parser import split


def dependencies(statement, dialect='teradata'):
    tree = sqlglot.parse_one(statement, read=dialect)
    tables = {f'{t.db}.{t.name}'.lower() for t in tree.find_all(exp.Table)
              if t.db.lower().startswith('sfx_')}
    target = None
    if isinstance(tree, (exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create)):
        node = tree.this
        if isinstance(node, exp.Schema):
            node = node.this
        if isinstance(node, exp.Table):
            target = f'{node.db}.{node.name}'.lower()
    return target, tables - {target}


def leaves(graph, start):
    found, pending, seen = set(), [start], set()
    while pending:
        node = pending.pop()
        if node in seen:
            continue
        seen.add(node)
        parents = graph.get(node, set()) - {node}
        if parents:
            pending.extend(parents)
        else:
            found.add(node)
    return found


def source_graph(connection):
    graph, evidence = defaultdict(set), []
    query = """SELECT q.queryid,q.querytext,o.objectdatabasename,o.objecttablename,o.usagetype
      FROM dbc.dbc_qrylog q JOIN dbc.dbc_qrylogobjects o ON q.queryid=o.queryid
      WHERE q.errorcode=0 AND q.starttime::date=DATE '2026-11-09'
      ORDER BY q.queryid"""
    queries = {}
    for qid, text, database, table, usage in connection.execute(query).fetchall():
        item = queries.setdefault(qid, {'sql': text, 'read': set(), 'write': set(), 'execute': set()})
        key = usage.strip().lower()
        if key in item:
            item[key].add(f'{database}.{table}'.lower())
    if not queries:
        raise RuntimeError('DBQL exists but has no successful 2026-11-09 queries; cannot infer source lineage')
    for qid, item in queries.items():
        for target in item['write']:
            graph[target].update(item['read'] - {target})
        evidence.append({'query_id': qid, 'sql': item['sql'],
                         'read': sorted(item['read']), 'write': sorted(item['write']),
                         'execute': sorted(item['execute'])})
    executed = {name for item in queries.values() for name in item['execute']}
    supplements = []
    # DBQL's generated CALL rows mark expanded tables READ, not individual writes.
    for name, kind, body in connection.execute('SELECT name,kind,body FROM sfx_td.routines').fetchall():
        if name.lower() not in executed:
            continue
        for statement in split(body):
            match = re.search(r'\b(INSERT\s+INTO|MERGE\s+INTO|UPDATE|DELETE\s+FROM|SELECT)\b', statement, re.I)
            if not match:
                continue
            statement = statement[match.start():]
            target, parents = dependencies(statement)
            if kind == 'MACRO':
                target = name.lower()
            if target:
                graph[target].update(parents - {target})
                supplements.append({'routine': name, 'target': target, 'upstream': sorted(parents), 'sql': statement})
    for schema, name, definition in connection.execute("SELECT schemaname,viewname,definition FROM pg_views WHERE schemaname IN ('sfx_billing','sfx_users','sfx_documents')").fetchall():
        _, parents = dependencies(definition, 'postgres')
        graph[f'{schema}.{name}'].update(parents)
    return graph, {'dbql_sql': query, 'dbql_queries': evidence,
                   'executed_routine_supplements': supplements,
                   'method': 'DBQL READ/WRITE object usage, supplemented by sqlglot parsing executed routine bodies and source view definitions. DBQL is seeded history, not a live execution trace.'}


def source_name(object_name):
    subject, name = object_name.split('__', 1)
    return f'sfx_{subject}.{name}'


def normalize_uc(name, mapping):
    name = name.lower()
    if name.startswith('cpw.dbx_d1111_before.'):
        return source_name(name.rsplit('.', 1)[1])
    return mapping.get(name, name)


def compare_sets(spec, source, uc_rows):
    mapping = {'cpw.dbx_d1111_after.'+o['object']: source_name(o.get('before', o['object']))
               for o in spec['objects']}
    uc, original = defaultdict(set), defaultdict(set)
    for target, parent, *_ in uc_rows:
        if not parent:
            continue
        original[target.lower()].add(parent.lower())
        uc[normalize_uc(target, mapping)].add(normalize_uc(parent, mapping))
    result = []
    for obj in spec['objects']:
        target = 'cpw.dbx_d1111_after.'+obj['object']
        origin = mapping[target]
        left = leaves(source, origin)
        right = leaves(uc, origin) if original[target] else set()
        available = bool(original[target])
        source_direct = source.get(origin, set()) - {origin}
        uc_direct = {normalize_uc(parent, mapping) for parent in original[target]} - {origin}
        result.append({'object': obj['object'], 'teradata_object': origin,
                       'teradata_upstream': sorted(source_direct),
                       'uc_upstream': sorted(original[target] - {target}),
                       'teradata_leaf_inputs': sorted(left), 'uc_leaf_inputs': sorted(right),
                       'direct_upstream_match': available and source_direct == uc_direct,
                       'status': 'match' if available and left == right else 'different' if available else 'empty (possible ingestion lag or uncaptured view lineage)'})
    return result


def run(source, client, spec, receipts, output):
    graph, source_evidence = source_graph(source)
    ids = ','.join(literal(r['statement_id']) for r in receipts)
    views = [o['object'] for o in spec['objects'] if '__v_' in o['object']]
    view_names = ','.join(literal('cpw.dbx_d1111_after.'+name) for name in views) or "''"
    targets = ','.join(literal('cpw.dbx_d1111_after.'+o['object']) for o in spec['objects'])
    query = ("SELECT DISTINCT lower(target_table_full_name),lower(source_table_full_name),statement_id,direct_access "
             "FROM system.access.table_lineage WHERE event_date>=DATE '2026-11-11' "
             f"AND lower(target_table_full_name) IN ({targets}) "
             f"AND (statement_id IN ({ids}) OR lower(target_table_full_name) IN ({view_names})) "
             "AND source_table_full_name IS NOT NULL ORDER BY 1,2")
    response = client.execute(query, step='lineage-upstream')
    rows = compare_sets(spec, graph, response['rows'])
    data = {'measured_at': datetime.now(timezone.utc).isoformat(), 'source_evidence': source_evidence,
            'uc_sql': query, 'uc_response': response, 'objects': rows}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    prior = output.with_suffix('.json')
    if prior.exists():
        old = json.loads(prior.read_text())
        data['previous_uc_measurements'] = old.get('previous_uc_measurements', []) + [
            {'measured_at': old['measured_at'], 'response': old['uc_response']}]
    prior.write_text(json.dumps(data, indent=2))
    lines = ['# Billing lineage — dbx-d1111', '', source_evidence['method'], '',
             'Direct upstream sets are shown side by side. Matching compares transitive leaf staging inputs after mapping billing-owned aliases to source names; self/cycle edges are traversed without inventing inputs. UC writes are limited to fixed conversion receipt IDs; view-read lineage is included separately. Empty UC evidence is not counted as a match and must be re-queried after ingestion lag.', '',
             f"Tagged UC query statement ID: {response['statement_id']}", '',
             '| Object | Teradata upstream | Unity Catalog upstream | Direct set match | Leaf-set comparison |',
             '|---|---|---|---|---|']
    for row in rows:
        lines.append('| '+row['object']+' | '+', '.join(row['teradata_upstream'])+' | '+', '.join(row['uc_upstream'])+' | '+str(row['direct_upstream_match'])+' | '+row['status']+' |')
    lines += ['', f"Matching direct upstream sets: {sum(r['direct_upstream_match'] for r in rows)}/{len(rows)}.",
              f"Matching leaf input sets: {sum(r['status']=='match' for r in rows)}/{len(rows)}.", '',
              'Differences are lineage coverage/structure observations, not proof of value drift. In particular, seeded DBQL may omit chain statements and UC records reads of empty initializer tables.', '',
              'Full source query IDs, routine derivations, UC event statement IDs, leaf sets, and prior measurements are in lineage.json.']
    for row in rows:
        if row['status']=='different':
            left, right = set(row['teradata_leaf_inputs']), set(row['uc_leaf_inputs'])
            lines.append(f"- {row['object']}: source-only leaves {sorted(left)}; UC-only leaves {sorted(right)}")
    output.write_text('\n'.join(lines)+'\n')
    return data


def main():
    import psycopg

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, default=Path(__file__).with_name('billing')/'parity_spec.json')
    parser.add_argument('--receipts', type=Path, default=Path.home()/'dbx-evidence/fixed_receipts.json')
    parser.add_argument('--output', type=Path, default=Path.home()/'dbx-evidence/lineage.md')
    args = parser.parse_args()
    with psycopg.connect(os.environ['TD_DSN']) as source:
        source.execute('SET TRANSACTION READ ONLY')
        data = run(source, Warehouse(act='prove', consumer='billing'), json.loads(args.spec.read_text()),
                   json.loads(args.receipts.read_text()), args.output)
    print(f"Lineage: {sum(r['status']=='match' for r in data['objects'])}/{len(data['objects'])} matching upstream leaf sets; statement {data['uc_response']['statement_id']}")


if __name__ == '__main__':
    main()
