"""Read-only follow-up evidence for the already completed UNT-10 mark runs."""
from collections import Counter
from datetime import timedelta
import json
import re

from . import evidence_live
from .evidence import OUT, dump, sha
from .evidence_unt3 import control_snapshot
from .harness import connection

DEST = OUT / 'unt10_addendum'
EXPECTED_SHA = 'd6c325fc216f3e89c7c3eec46302c3754334a15b0ed4fd9c2f4a70c393e5d6d5'
ANCHORS = ('01c85440-030d-1e7f-0035-065b001bbade',
           '01c85442-030d-2128-0035-065b001b4e9a')


def guard(sql):
    if not re.match(r'^(SELECT|SHOW|DESCRIBE)\s', sql, re.I):
        raise ValueError('Evidence SQL must start with SELECT, SHOW or DESCRIBE')
    # No stacked statements, including a read followed by a write.
    if ';' in re.sub(r"'(?:''|[^'])*'", "''", sql):
        raise ValueError('Evidence SQL must contain exactly one statement')


class Queries(evidence_live.Queries):
    def run(self, sql):
        guard(sql)
        return super().run(sql)


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def capture(q, name, sql, optional=False):
    try:
        columns, rows = q.run(sql)
        result = {'qid': q.records[-1]['qid'],
                  'rows': [dict(zip(columns, r)) for r in rows]}
    except Exception as error:
        if not optional:
            raise
        result = {'qid': q.records[-1].get('qid'), 'error': str(error)}
    dump(DEST / (name + '.json'), json.loads(json.dumps(result, default=str)))
    return result


def merge_checks(text):
    normalized = re.sub(r'\s+', '', text).upper()
    values = re.search(r"SELECT\s+'((?:''|[^'])*)'\s+(?:AS\s+)?FOLDER\s*,\s*"
                       r"'((?:''|[^'])*)'\s+(?:AS\s+)?MAPPING\s*,\s*"
                       r"'((?:''|[^'])*)'\s+(?:AS\s+)?OWNER_EFFORT", text, re.I)
    return {'key_guard': 'ONT.FOLDER=S.FOLDERANDT.MAPPING=S.MAPPING' in normalized,
            'owner_guard': 'WHENMATCHEDANDT.OWNER_EFFORT=S.OWNER_EFFORT' in normalized,
            'no_insert_delete': not re.search(r'\b(?:INSERT|DELETE)\b|WHEN\s+NOT\s+MATCHED', text, re.I),
            'literals': dict(zip(('folder', 'mapping', 'owner'),
                                 [v.replace("''", "'") for v in values.groups()])) if values else None}


def collect(q):
    summary = {'control': control_snapshot(q, DEST)}
    control = json.loads((DEST / 'control.json').read_text())
    rows = [{c: v[1] for c, v in zip(control['columns'], row)} for row in control['rows']]
    summary['control'].update(
        expected_sha256=EXPECTED_SHA, sha_matches=summary['control']['sha256'] == EXPECTED_SHA,
        owner_counts=dict(Counter(r['OWNER_EFFORT'] for r in rows)),
        distinct_keys=len({(r['FOLDER'], r['MAPPING']) for r in rows}),
        migrations_page=[{c: r[c] for c in ('FOLDER', 'MAPPING', 'STATUS', 'AMBER_REASON', 'VERIFIED_AT')}
                         for r in rows if r['OWNER_EFFORT'] == 'migrations-page'])
    fields = 'QUERY_ID,QUERY_TEXT,QUERY_TAG,START_TIME,END_TIME,ROWS_PRODUCED,EXECUTION_STATUS,USER_NAME'
    anchors = capture(q, 'anchors', f'SELECT {fields} FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY '
                      f"WHERE QUERY_ID IN ({','.join(map(literal, ANCHORS))}) ORDER BY START_TIME")
    if len(anchors['rows']) != 2:
        raise ValueError('Both boundary readbacks must be available before collecting history')
    start = min(r['START_TIME'] for r in anchors['rows']) - timedelta(seconds=1)
    end = max(r['END_TIME'] for r in anchors['rows']) + timedelta(seconds=1)
    summary['window'] = {'start': str(start), 'end': str(end), 'anchors_qid': anchors['qid']}
    history = capture(q, 'history', f'SELECT {fields} FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY '
                      f'WHERE START_TIME >= TO_TIMESTAMP_TZ({literal(start)}) '
                      f'AND START_TIME <= TO_TIMESTAMP_TZ({literal(end)}) '
                      "AND USER_NAME=CURRENT_USER() AND EXECUTION_STATUS='SUCCESS' "
                      "AND END_TIME>=START_TIME ORDER BY START_TIME")
    merges = [r for r in history['rows'] if re.match(r'^\s*MERGE\b', r['QUERY_TEXT'], re.I)
              and 'MIGRATION_CONTROL' in r['QUERY_TEXT'].upper()]
    summary['history_qid'] = history['qid']
    summary['merges'] = [{'qid': r['QUERY_ID'], **merge_checks(r['QUERY_TEXT'])} for r in merges]
    summary['other_non_reads'] = [r for r in history['rows'] if r not in merges
        and 'MIGRATION_CONTROL' in r['QUERY_TEXT'].upper()
        and not re.match(r'^\s*(SELECT|SHOW|DESCRIBE)\b', r['QUERY_TEXT'], re.I)]
    ids = ','.join(literal(r['QUERY_ID']) for r in merges)
    if ids:
        summary['affected_rows'] = capture(q, 'affected_rows',
            'SELECT QUERY_ID,ROWS_UPDATED,ROWS_INSERTED,ROWS_DELETED FROM '
            f'SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY WHERE QUERY_ID IN ({ids}) ORDER BY QUERY_ID', True)
    summary['result_scans'] = {r['QUERY_ID']: capture(q, 'result_scan_' + r['QUERY_ID'],
        f"SELECT * FROM TABLE(RESULT_SCAN({literal(r['QUERY_ID'])}))", True) for r in merges}
    summary['tasks'] = capture(q, 'tasks',
        "SHOW TASKS LIKE 'SFX_D1110_PC_AUDIT%' IN SCHEMA SFX_D1110_AFTER.PC_AUDIT")
    summary['task_history'] = capture(q, 'task_history',
        'SELECT * FROM SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY WHERE RUN_ID=1794358031749 '
        "AND DATABASE_NAME='SFX_D1110_AFTER' AND SCHEMA_NAME='PC_AUDIT' ORDER BY SCHEDULED_TIME")
    summary['merge_checks_pass'] = len(merges) == 16 and all(
        all(m[k] for k in ('key_guard', 'owner_guard', 'no_insert_delete', 'literals'))
        for m in summary['merges'])
    dump(DEST / 'summary.json', json.loads(json.dumps(summary, default=str)))
    return summary


def main():
    if DEST.exists():
        raise ValueError('Preserve previous evidence: output directory already exists')
    DEST.mkdir(parents=True)
    previous = evidence_live.LIVE
    evidence_live.LIVE = DEST
    try:
        with connection('parity', 'unt10_addendum') as conn, conn.cursor() as cursor:
            summary = collect(Queries(cursor))
    finally:
        evidence_live.LIVE = previous
        hashes = {p.name: sha(p) for p in sorted(DEST.iterdir()) if p.is_file()}
        dump(DEST / 'manifest.json', {'files': hashes,
             'integrity': 'SHA256SUMS includes manifest; SHA256SUMS cannot hash itself'})
        hashes['manifest.json'] = sha(DEST / 'manifest.json')
        (DEST / 'SHA256SUMS').write_text(''.join(f'{v}  {k}\n' for k, v in sorted(hashes.items())))
    print(json.dumps(summary, indent=2, default=str))


if __name__ == '__main__':
    main()
