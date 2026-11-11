"""Report observed consumer reads, merging delayed and recent query history."""
import argparse
from collections import defaultdict
import re

from ledger import records
from sfx_conn import ROOT, connect

EXPECTED = ('report-service', 'analytics-service', 'billing-service', 'legacy-billing',
            'admin-service', 'bi-semantic', 'notebook', 'partner-extract')


def compat_objects(query_text):
    return sorted({'COMPAT.' + name.upper() for name in re.findall(
        r'\bCOMPAT"?\s*\.\s*"?([A-Z_][A-Z0-9_]*)', query_text or '', re.I)})


def read_history(cursor, run, hours):
    landed = records(cursor, (ROOT / 'consumer_reads.sql').read_text(),
                     (hours, '%' + run + '%', run))
    recent = records(cursor, '''SELECT QUERY_ID, START_TIME, ROWS_PRODUCED, QUERY_TEXT,
            TRY_PARSE_JSON(QUERY_TAG):consumer::VARCHAR AS CONSUMER
        FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
            END_TIME_RANGE_START=>DATEADD('hour', -%s, CURRENT_TIMESTAMP()), RESULT_LIMIT=>10000))
        WHERE START_TIME >= DATEADD('hour', -%s, CURRENT_TIMESTAMP())
          AND QUERY_TAG ILIKE %s AND TRY_PARSE_JSON(QUERY_TAG):run::VARCHAR = %s
          AND TRY_PARSE_JSON(QUERY_TAG):act::VARCHAR = 'consumers'
          AND TRY_PARSE_JSON(QUERY_TAG):consumer::VARCHAR IS NOT NULL
          AND QUERY_TYPE='SELECT' AND EXECUTION_STATUS='SUCCESS'
    ''', (hours, hours, '%' + run + '%', run))
    freshness = records(cursor, '''SELECT MAX(START_TIME) AS QUERY_MAX_START
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME >= DATEADD('hour', -%s, CURRENT_TIMESTAMP())''', (hours,))[0]['query_max_start']
    return landed, recent, freshness


def summarize(landed, recent, freshness):
    known = {row['query_id']: row for row in landed}
    merged = {**{row['query_id']: row for row in recent}, **known}
    groups = defaultdict(list)
    for row in merged.values():
        groups[row['consumer'], row['start_time'].date()].append(row)
    result = []
    for (consumer, day), rows in sorted(groups.items()):
        pending = any(row['query_id'] not in known for row in rows)
        pending |= freshness is None or max(row['start_time'] for row in rows) > freshness
        objects = sorted({obj for row in rows for obj in compat_objects(row['query_text'])})
        result.append(dict(consumer=consumer, day=day, reads=len(rows),
            rows_produced=('pending' if any(r['rows_produced'] is None for r in rows)
                           else sum(r['rows_produced'] for r in rows)),
            objects_read=objects or ['unknown'], account_usage='pending' if pending else 'landed'))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', default='sfx-d1110')
    parser.add_argument('--hours', type=int, default=24)
    args = parser.parse_args()
    if not 1 <= args.hours <= 168:
        parser.error('--hours must be between 1 and 168')
    with connect('ops', 'consumer_reads') as conn, conn.cursor() as cursor:
        landed, recent, freshness = read_history(cursor, args.run, args.hours)
    report = summarize(landed, recent, freshness)
    print(f'ACCOUNT_USAGE freshness: {freshness}; lags up to ~3h')
    print('Observed reads only; recent history is limited to 10000 visible queries. Days use session timezone.')
    print('Objects read are best-effort COMPAT names from query text, not complete lineage.')
    print('consumer | day | reads | rows_produced | objects_read | account_usage')
    for row in report:
        print(' | '.join(str(row[key]) for key in ('consumer', 'day', 'reads', 'rows_produced', 'objects_read', 'account_usage')))
    observed = {row['consumer'] for row in report}
    for consumer in EXPECTED:
        if consumer not in observed:
            print(f'{consumer} | no reads yet (observed history; ACCOUNT_USAGE may be pending)')


if __name__ == '__main__':
    main()
