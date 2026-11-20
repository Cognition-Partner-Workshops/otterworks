"""Explicit owner-approved comparison contracts, retaining raw legacy measurements."""
from pathlib import Path
from collections import Counter
import duckdb
from . import ladder
import json
import csv
from functools import lru_cache


ROOT = Path(__file__).resolve().parents[3]

SFG1120_DECISIONS = [
    dict(decision_id='sfg1120-char-trailing-padding', status='approved', action='comparison',
         new_behaviour='Ignore trailing ASCII blanks on DDL-declared CHAR columns only in parity; VARCHAR remains exact.'),
    dict(decision_id='sfg1120-login-event-keep-all', status='approved', action='retain',
         board_objects=['SFX_USERS.LOGIN_EVENT', 'm_SFX_LOGIN_EVENT', 's_m_SFX_LOGIN_EVENT'],
         new_behaviour='Keep every LOGIN_EVENT row using BTEQ semantics; retire the PowerCenter router drop.'),
    dict(decision_id='sfg1120-search-staging-retained', status='approved', action='retain',
         board_objects=['SFX_DOCUMENTS.STG_SEARCH_INDEX_LOG', 'documents_search_index_log'],
         new_behaviour='Keep staging and dbt model until Finance agrees an alternative.'),
    dict(decision_id='sfg1120-search-history-retirement', status='approved', action='retire',
         board_objects=['SFX_DOCUMENTS.V_SEARCH_HISTORY', 'SFX_DOCUMENTS.SEARCH_INDEX_LOG'],
         drop_order=['SFX_DOCUMENTS.V_SEARCH_HISTORY', 'SFX_DOCUMENTS.SEARCH_INDEX_LOG'],
         new_behaviour='Retire search history view and table together; drop view before table.'),
    dict(decision_id='sfg1120-user-pref-retirement', status='approved', action='retire',
         board_objects=['SFX_USERS.USER_PREF', 'SFX_USERS.STG_USER_PREF', 'users_user_pref', 'SFX_USERS.V_USER_SETTINGS'],
         preserve=['Spark PREF_JSON landing feed'],
         new_behaviour='Retire preference table, staging, dbt model and settings view; keep the Spark PREF_JSON landing feed.'),
    dict(decision_id='sfg1120-storage-finance-confirmation', status='approved-pending-confirmation', action='deviation',
         board_objects=['10_storage_monthly', 'SFX_BILLING.USAGE_DAILY', 'SFX_BILLING.INVOICE_LINE'],
         confirmation='Pending Finance invoice confirmation',
         new_behaviour='Storage decision amber extends to monthly storage, usage daily and invoice line pending Finance invoice confirmation.'),
]


def decision_registry():
    return [*json.loads((ROOT/'migration/dw-exit/audit/decisions.json').read_text()),
            *json.loads((ROOT/'migration/dw-exit/dbc/decisions.json').read_text()),
            *SFG1120_DECISIONS]


def approved_char_padding():
    return next(decision for decision in SFG1120_DECISIONS
                if decision['decision_id'] == 'sfg1120-char-trailing-padding')['status'] == 'approved'


def approved_retirements():
    return [decision for decision in json.loads((ROOT/'migration/dw-exit/audit/decisions.json').read_text())
            if decision.get('status') == 'approved' and decision.get('action') == 'retire']


def approved_summary_ids():
    return any(d.get('decision_id') == 'audit-summary-stable-ids' and d.get('status') == 'approved'
               for d in json.loads((ROOT/'migration/dw-exit/audit/decisions.json').read_text()))


@lru_cache(maxsize=1)
def retirement_dbql():
    from assess import before_state_root, BEFORE_STATE
    from .provenance import link
    def usage(root):
        directory = root / 'warehouse/teradata/dbql'
        queries = {r['QueryID']:r for r in csv.DictReader((directory/'qrylog.csv').open())
                   if '2026-08-12' <= r['StartTime'][:10] <= '2026-11-09'}
        result = {}
        for name in ('AUDIT_EVENT_ARCHIVE', 'M_ARCHIVE_OVERVIEW', 'STG_AUDIT_EVENT_ARCHIVE'):
            hits = [dict(record, query=queries[record['QueryID']])
                    for record in csv.DictReader((directory/'objectusage.csv').open())
                    if record['QueryID'] in queries and record['ObjectDatabaseName'] == 'SFX_AUDIT'
                    and record['ObjectTableName'] == name]
            result['SFX_AUDIT.'+name] = dict(reads=sum(r['UsageType']=='READ' for r in hits),
                writes=sum(r['UsageType']!='READ' for r in hits), records=hits)
        return result
    return dict(window=['2026-08-12','2026-11-09'], assessment_commit=BEFORE_STATE,
        assessment_usage=usage(before_state_root()), current_checkout_usage=usage(ROOT),
        files=[link('warehouse/teradata/dbql/'+name) for name in ('qrylog.csv','objectusage.csv','tablesv.csv')],
        caveat='Staging archive has a setup-day svc_report_recon COUNT(*) read, not zero readership. Retirement is owner approved; no physical deletion.',
        callers=['AUDIT_EVENT -> m_SFX_AUDIT_EVENT_ARCHIVE -> AUDIT_EVENT_ARCHIVE -> M_ARCHIVE_OVERVIEW',
                 's_m_SFX_AUDIT_EVENT_ARCHIVE is disabled in wf_SFX_AUDIT_DAILY',
                 'archive landing -> audit_audit_event_archive -> STG_AUDIT_EVENT_ARCHIVE'])


def apply_retirement(row, obj, decisions):
    for decision in decisions:
        if (obj.get('subject_area') == 'audit' and obj.get('target_type') == 'retire'
                and decision.get('decision_id') == 'audit-archive-retirement'
                and decision.get('status') == 'approved'
                and row['name'] in decision.get('board_objects', [])):
            row.update(status='retired', decision_state='approved', reason=decision['new_behaviour'],
                       retirement_evidence={'decision_id':decision['decision_id'],
                                            'owner_approved':True, 'manifest_target':'retire',
                                            'dbql':retirement_dbql()})
    return row


def missing_fields(db, source, target, raw, decision):
    def relation(name):
        quoted = '.'.join(ladder.identifier(part) for part in name.split('.'))
        # Validated, quoted local relation identifiers; row values never become SQL.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        cursor = db.execute('SELECT * FROM '+quoted)
        return [column[0] for column in cursor.description], cursor.fetchall()
    columns, before = relation(source)
    target_columns, after = relation(target)
    missing = set(decision['missing_fields']) & set(columns)
    ignored = set(decision.get('ignored_fields', [])) & set(columns)
    excluded = missing | ignored
    scope = decision.get('missing_rows', {})
    scope_columns_valid = set(scope) <= set(columns)
    def omitted(row):
        return bool(scope) and scope_columns_valid and all(
            row[columns.index(column)] in values for column,values in scope.items())
    kept = [index for index,column in enumerate(columns) if column not in excluded]
    project = lambda rows: Counter(tuple(ladder.canonical(row[index]) for index in kept) for row in rows)
    old, new = project(before), project(after) if columns == target_columns else Counter()
    allowed = project([row for row in before if omitted(row)])
    missing_rows, extra_rows = old-new, new-old
    outside_scope = missing_rows-allowed
    unavailable = columns == target_columns and all(
        row[index] is None for row in after for index,column in enumerate(columns) if column in missing)
    passed = columns == target_columns and not outside_scope and not extra_rows and unavailable and scope_columns_valid
    return {**raw, 'owner_decision':{
        'decision_id':decision['decision_id'], 'scope_valid':passed,
        'missing_fields':sorted(missing), 'ignored_fields':sorted(ignored),
        'missing_row_scope':scope, 'excluded_source_rows':sum((missing_rows & allowed).values()),
        'unavailable_fields_are_null':unavailable,
        'approved_comparison':{'passed':passed, 'row_count':{'before':len(before),'after':len(after)},
                               'removed_rows':sum(outside_scope.values()), 'added_rows':sum(extra_rows.values()),
                               'compared_columns':[columns[index] for index in kept]},
    }}


def apply_deviation(row, measurements, decisions):
    failed = [value for value in measurements.values() if not value['passed']]
    if row['status'] != 'red' or not failed:
        return row
    registered = {d.get('decision_id'):d for d in decisions if d.get('decision_id')}
    proofs = [value.get('owner_decision',{}) for value in failed]
    approvals = [registered.get(proof.get('decision_id'),{}) for proof in proofs]
    if not all(proof.get('scope_valid') is True and
               proof.get('approved_comparison',{}).get('passed') is True and
               decision.get('status') in ('approved','approved-pending-confirmation')
               for proof,decision in zip(proofs,approvals)):
        return row
    pending = [d for d in approvals if d['status']=='approved-pending-confirmation']
    state = 'amber' if pending else 'approved_deviation'
    row.update(measurement_status='red',status=state,local_duckdb=state,
               decision_state='approved-pending-confirmation' if pending else 'approved',
               reason='; '.join(dict.fromkeys(d['confirmation'] if pending and d in pending
                   else d['new_behaviour'] for d in approvals)),
               owner_decision_evidence=proofs)
    return row
