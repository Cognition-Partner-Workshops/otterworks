"""Explicit owner-approved comparison contracts, retaining raw legacy measurements."""
from pathlib import Path
import json
import csv
from functools import lru_cache


ROOT = Path(__file__).resolve().parents[3]


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
        if obj.get('target_type') == 'retire' and row['name'] in decision.get('board_objects', []):
            row.update(status='retired', decision_state='approved', reason=decision['new_behaviour'],
                       retirement_evidence={'decision_id':decision['decision_id'],
                                            'owner_approved':True, 'manifest_target':'retire',
                                            'dbql':retirement_dbql()})
    return row
