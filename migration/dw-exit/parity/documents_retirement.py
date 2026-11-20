"""Confirm documents retirement classifications without authorizing deletion."""
import csv
from pathlib import Path

from assess import BEFORE_STATE, before_state_root, dbql
from .owner_decisions import decision_registry


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
    decisions = [d for d in decision_registry() if d.get('decision_id') == 'sfg1120-search-history-retirement' and d.get('status') == 'approved']
    pinned = before_state_root()
    results = {}
    for obj in objects:
        if obj['target_type'] != 'retire' or obj['name'] not in ('SFX_DOCUMENTS.V_SEARCH_HISTORY', 'SFX_DOCUMENTS.SEARCH_INDEX_LOG'):
            continue
        name = obj['name']
        relation, = obj['output_relations']
        baseline = query_usage(pinned, relation)
        current = query_usage(ROOT, relation)
        results[name] = {
            'status': 'retired' if decisions else 'red', 'deletion_approved': bool(decisions),
            'decision_id': decisions[0]['decision_id'] if decisions else None,
            'drop_order': decisions[0]['drop_order'] if decisions else [],
            'preserve': ['Spark SEARCH_INDEX_LOG landing feed', 'DOCUMENTS.STG_SEARCH_INDEX_LOG', 'documents_search_index_log'],
            'window_inclusive': WINDOW,
            'baseline_commit': BEFORE_STATE, 'checked_relation': relation,
            'baseline_reads': sum(q['usage']=='READ' for q in baseline),
            'checkout_reads': sum(q['usage']=='READ' for q in current),
            'baseline_queries': baseline, 'checkout_queries': current,
            'dependencies': DEPENDENCIES[name],
            'reason': ('Owner-approved joint retirement: drop V_SEARCH_HISTORY before SEARCH_INDEX_LOG; preserve live staging/TPT and Spark landing. Board generation performs no drops.'
                       if decisions else 'Search-history retirement lacks approved owner decision'),
        }
    return results
