"""Local retirement evidence only; never target conversion or retirement approval."""
import json
import os
from pathlib import Path
import re
import sys
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'migration/dw-exit/parity'))
import object_board as board
import yaml
from assess import before_state_root, dbql, BEFORE_STATE


def dependency_check(manifest, object_id, lineage):
    objects = {obj['id']: obj for obj in manifest['objects']}
    edges = {tuple(edge) for edge in manifest['dependencies']}
    edges.update(re.findall(r'\b(n[0-9a-f]{16}) --> (n[0-9a-f]{16})\b', lineage))
    for obj in objects.values():
        if obj['kind'] == 'table' and '.STG_' in obj['name']:
            edges.update((obj['id'], other['id']) for other in objects.values()
                         if other['name'] == obj['name'].replace('.STG_', '.'))
    pending, seen = [object_id], set()
    while pending:
        node = pending.pop()
        for source, target in edges:
            if source == node and target not in seen:
                seen.add(target)
                pending.append(target)
    dependents = [{'id': node, 'name': objects.get(node, {}).get('name', node),
                   'target_type': objects.get(node, {}).get('target_type', 'unknown')}
                  for node in sorted(seen)]
    return {'pass': all(d['target_type'] == 'retire' for d in dependents),
            'downstream_dependents': dependents,
            'sources': ['manifest.dependencies (retire edges excluded by assess.py)',
                        'lineage.md data-dependency arrows', 'assess.py STG-to-core inference']}


def build():
    manifest = yaml.safe_load((ROOT / 'migration/dw-exit/manifest.yaml').read_text())
    group = board.load_group(HERE)
    objects = board.select_group(manifest, group)['objects']
    names = {name for obj in objects for name in obj['output_relations']}
    ns = os.environ.get('NS', board.RunConfig.from_env().before_namespace)
    port = os.environ.get('TD_PG_PORT', str(54500 + zlib.crc32(ns.encode()) % 1000))
    dsn = os.environ.get('BOARD_SOURCE_DSN',
                         f'host=127.0.0.1 port={port} dbname=teradata user=postgres')
    snapshot, ready, errors = board.source_snapshot(dsn, names)
    queries, usage, catalog, dead = dbql(before_state_root())
    lineage = (ROOT / 'migration/dw-exit/lineage.md').read_text()
    result = []
    try:
        for obj in objects:
            counts = {name: snapshot.table(board.relation(name)).count('*').fetchone()[0]
                      if name in ready else None for name in obj['output_relations']}
            deps = dependency_check(manifest, obj['id'], lineage)
            hits = [row for row in usage if row['ObjectDatabaseName'] + '.' + row['ObjectTableName']
                    in obj['output_relations']]
            declared = (obj['target_type'] == 'retire' and obj['target'] == 'NONE'
                        and obj['name'] in manifest['dead'] + manifest['dead_dependents'])
            result.append({'id': obj['id'], 'name': obj['name'], 'source_row_counts': counts,
                           'source_errors': {n: errors[n] for n in counts if n in errors},
                           'row_count_scope': 'declared outputs; fastload count is its STG output, not executions',
                           'dependencies': deps,
                           'dbql': {'usage_events': len(hits),
                                    'read_events': sum(r['UsageType'] == 'READ' for r in hits),
                                    'query_count': len({r['QueryID'] for r in hits}),
                                    'catalog_dead_outputs': [n for n in counts if n in dead]},
                           'retirement_check': 'pass' if declared and deps['pass'] and not hits
                           and all(n is not None for n in counts.values()) else 'fail'})
    finally:
        snapshot.close()
    return {'run_token': board.RunConfig.from_env().token,
            'scope': 'local supporting evidence; board remains red; not retirement approval',
            'source': 'object_board.source_snapshot PostgreSQL Teradata emulator; same DSN resolution',
            'usage_basis': {'snapshot_commit': BEFORE_STATE, 'window_inclusive': ['2026-08-12', '2026-11-09'],
                            'method': 'assess.dbql joins objectusage.csv to qrylog.csv by QueryID in window',
                            'query_history_sql': 'query_history*.sql measures Snowflake prove/assess runs, not legacy DBQL; not executed',
                            'window_query_count': len(queries)},
            'non_retired_readers': [{
                'id': 'nadfca1251f9b6a28', 'name': 'user_pref_json_flatten',
                'target_type': 'dbt_model', 'group': 'users/spark-jobs',
                'source': 'etl/spark/jobs/py/user_pref_json_flatten.py',
                'dependency': 'landing psv only, not Teradata tables or fastload',
                'evidence': 'landing(spark, "USER_PREF") uses common/runtime.py CSV reader; save has no jdbc_table',
                'landing': '${LANDING_DIR}/users/USER_PREF/*.psv',
                'owner_decision': 'Preserve landing feed for this live reader; retirement does not authorize deleting it.'}],
            'repository_reader_review': {
                'scope': 'tracked SQL/Python/ETL sources reviewed with USER_PREF/users_user_pref/V_USER_SETTINGS search',
                'teradata_reader': 'warehouse/teradata/ddl/users/10_views.sql: V_USER_SETTINGS joins USER_PREF; also retired',
                'other_references': ['warehouse/dbt/models/sources.yml and staging/spark/sources.yml are source declarations',
                                     'warehouse/snowpark/user_pref_json_flatten.py reads SPARK_RAW_USERS.USER_PREF, not SFX_USERS',
                                     'warehouse/snowflake/migrations declares/loads RAW_USERS.USER_PREF, not SFX_USERS',
                                     'seed, fixtures, schemas and DBQL generation are not live table readers'],
                'limitation': 'Static repository evidence only; external readers outside captured DBQL are not ruled out'},
            'decision_notes': ['STG_USER_PREF has DBQL usage but no reads; its fastload inherits output usage, not execution attribution. Conservative retirement_check fails these two pending review.'],
            'objects': result,
            'summary': {'objects': len(result), 'pass': sum(o['retirement_check'] == 'pass' for o in result),
                        'fail': sum(o['retirement_check'] == 'fail' for o in result),
                        'board_status_changed': False}}


if __name__ == '__main__':
    evidence = build()
    (HERE / 'retirement.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence['summary'], sort_keys=True))
