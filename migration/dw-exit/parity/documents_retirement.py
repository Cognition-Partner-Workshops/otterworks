"""Confirm documents retirement classifications without authorizing deletion."""
import csv
from pathlib import Path

from assess import BEFORE_STATE, before_state_root, dbql


ROOT = Path(__file__).resolve().parents[3]
DBQL = Path('warehouse/teradata/dbql')
WINDOW = ['2026-08-12', '2026-11-09']
DEPENDENCIES = {
    'SFX_DOCUMENTS.SEARCH_INDEX_LOG': ['warehouse/teradata/ddl/documents/10_views.sql'],
    'SFX_DOCUMENTS.STG_SEARCH_INDEX_LOG': ['warehouse/teradata/load/tpt/documents_search_index_log.tpt'],
    'documents_search_index_log': ['warehouse/teradata/load/tpt/documents_search_index_log.tpt',
                                   'etl/spark/jobs/py/docs_search_log_parse.py'],
    'SFX_DOCUMENTS.V_SEARCH_HISTORY': ['warehouse/teradata/ddl/documents/10_views.sql'],
}


def query_usage(root, relation):
    queries, usage, _, _ = dbql(root)
    schema, name = relation.split('.')
    with (root/DBQL/'qrylog.csv').open() as stream:
        query_lines = {row['QueryID']: line for line, row in enumerate(csv.DictReader(stream), 2)}
    with (root/DBQL/'objectusage.csv').open() as stream:
        usage_lines = {tuple(row.values()): line for line, row in enumerate(csv.DictReader(stream), 2)}
    return [{
        'query_id': row['QueryID'], 'usage': row['UsageType'],
        'start': (query := queries[row['QueryID']])['StartTime'],
        'user': query['UserName'], 'client': query['ClientID'], 'application': query['AppID'],
        'error_code': int(query['ErrorCode']), 'query': query['QueryText'],
        'qrylog_line': query_lines[row['QueryID']], 'objectusage_line': usage_lines[tuple(row.values())],
    } for row in usage if (row['ObjectDatabaseName'], row['ObjectTableName']) == (schema, name)]


def measure(objects):
    pinned = before_state_root()
    results = {}
    for obj in objects:
        if obj['target_type'] != 'retire':
            continue
        name = obj['name']
        relation, = obj['output_relations']
        baseline = query_usage(pinned, relation)
        current = query_usage(ROOT, relation)
        results[name] = {
            'status': 'retired', 'deletion_approved': False, 'window_inclusive': WINDOW,
            'baseline_commit': BEFORE_STATE, 'checked_relation': relation,
            'baseline_reads': sum(q['usage']=='READ' for q in baseline),
            'checkout_reads': sum(q['usage']=='READ' for q in current),
            'baseline_queries': baseline, 'checkout_queries': current,
            'dependencies': DEPENDENCIES[name],
            'reason': ('No independent DBQL job signal; staging relation has one finance reconciliation read. Keep search-log landing.'
                       if obj['kind']=='tpt' else
                       'One setup-date reconciliation read; preserve until finance signs off.' if baseline else
                       'No relation reads in the assessment window; this is not deletion approval.'),
        }
    return results
