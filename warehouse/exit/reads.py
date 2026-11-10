"""Read attribution for the finance warehouse exit (all windows are UTC, half-open)."""
import argparse
import csv
import datetime as dt
import json
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ('2026-10-11', '2026-11-10')
OUT_OF_SCOPE = ('etl (out of scope)', 'parity tooling (out of scope)')


def timestamp(value):
    if isinstance(value, dt.datetime):
        return value.replace(tzinfo=dt.timezone.utc) if value.tzinfo is None else value.astimezone(dt.timezone.utc)
    return timestamp(dt.datetime.fromisoformat(value.replace('Z', '+00:00')))


def registry():
    return yaml.safe_load((ROOT / 'consumers/registry.yaml').read_text())['consumers']


def classify(row, consumers):
    account = row['username'].strip().lower()
    if account == 'svc_exit_parity':
        return 'parity tooling (out of scope)'
    if account.startswith('svc_etl_') or account == 'svc_fastload':
        return 'etl (out of scope)'
    for consumer in consumers:
        if account == consumer['teradata_service_account'].lower():
            return consumer['name']
    if row.get('appid', '').startswith('JupyterLab') or row.get('clientid', '').startswith('notebook-'):
        return 'finance-notebook'
    return 'unmanaged'


def teradata(csv_path=None):
    if csv_path:
        with open(csv_path, newline='') as handle:
            return [{k.lower(): v for k, v in row.items()} for row in csv.DictReader(handle)]
    import psycopg
    from psycopg.rows import dict_row
    params = {k: os.environ.get('TD_PG_' + env, default) for k, env, default in
              [('host', 'HOST', 'localhost'), ('port', 'PORT', '5432'),
               ('dbname', 'DB', 'teradata'), ('user', 'USER', 'postgres'), ('password', 'PASSWORD', '')]
              if not os.environ.get('TD_PG_DSN') or 'TD_PG_' + env in os.environ}
    with psycopg.connect(os.environ.get('TD_PG_DSN', ''), **params, row_factory=dict_row) as conn:
        return conn.execute('SELECT username,appid,clientid,starttime,statementtype,errorcode FROM dbc.qrylogv').fetchall()


def snowflake(since, until, phase='reads'):
    import snowflake.connector
    from cryptography.hazmat.primitives import serialization
    key = serialization.load_pem_private_key(os.environ['SNOWFLAKE_PRIVATE_KEY'].encode(), password=None)
    with snowflake.connector.connect(
        account=os.environ['SNOWFLAKE_ACCOUNT'], user=os.environ['SNOWFLAKE_USER'],
        role=os.environ['SNOWFLAKE_ROLE'], authenticator='SNOWFLAKE_JWT',
        private_key=key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()),
        database='SFX_D1110_AFTER', warehouse='SFX_D1110_OPS_WH',
        session_parameters={'TIMEZONE': 'UTC', 'QUERY_TAG': json.dumps({'run': 'sfx-d1110', 'act': 'exit', 'phase': phase})},
    ) as conn:
        with conn.cursor() as cur:
            rows = []
            now = dt.datetime.now(dt.timezone.utc)
            recent = max(timestamp(since), now - dt.timedelta(days=7) + dt.timedelta(seconds=5))
            sources = [('SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY', timestamp(since))]
            if recent < timestamp(until):
                sources.append(('TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(END_TIME_RANGE_START => %s::TIMESTAMP_LTZ, END_TIME_RANGE_END => %s::TIMESTAMP_LTZ, RESULT_LIMIT => 10000))', recent))
            for source, start in sources:
                params = (start, min(timestamp(until), now)) if source.startswith('TABLE') else ()
                cur.execute('SELECT QUERY_ID,START_TIME,QUERY_TAG,QUERY_TYPE,EXECUTION_STATUS FROM ' + source +
                            ' WHERE START_TIME >= %s AND START_TIME < %s', params + (timestamp(since), timestamp(until)))
                batch = cur.fetchall()
                if source.startswith('TABLE') and len(batch) >= 10000:
                    raise RuntimeError('Recent QUERY_HISTORY reached 10000 rows; narrow the reporting window')
                rows.extend(dict(zip(('query_id', 'start_time', 'query_tag', 'query_type', 'execution_status'), r)) for r in batch)
    return rows


def summarize(td, sf, consumers, since, until):
    lo, hi = timestamp(since), timestamp(until)
    consumer_names = {c['name'] for c in consumers}
    result = {c['name']: {'baseline': 0, 'teradata': 0, 'snowflake': 0, 'days': {}, 'accounts': {}} for c in consumers}
    for name in ('unmanaged', *OUT_OF_SCOPE):
        result[name] = {'baseline': 0, 'teradata': 0, 'snowflake': 0, 'days': {}, 'accounts': {}}
    for row in td:
        if row['statementtype'].strip().upper() != 'SELECT' or int(row['errorcode'] or 0):
            continue
        entry = result[classify(row, consumers)]
        account = row['username'].strip()
        entry['accounts'].setdefault(account, 0)
        time = timestamp(row['starttime'])
        if timestamp(BASELINE[0]) <= time < timestamp(BASELINE[1]):
            entry['baseline'] += 1
        if lo <= time < hi:
            entry['teradata'] += 1
            entry['accounts'][account] = entry['accounts'].get(account, 0) + 1
            day = entry['days'].setdefault(time.date().isoformat(), {'teradata': 0, 'snowflake': 0})
            day['teradata'] += 1
    seen = set()
    for row in sf:
        if row['query_id'] in seen:
            continue
        seen.add(row['query_id'])
        try:
            tag = json.loads(row['query_tag'] or '{}')
        except (ValueError, TypeError):
            continue
        if not isinstance(tag, dict) or tag.get('run') != 'sfx-d1110' or tag.get('act') != 'consumers':
            continue
        name = tag.get('consumer')
        time = timestamp(row['start_time'])
        if name not in consumer_names or row['query_type'] != 'SELECT' or row['execution_status'] != 'SUCCESS' or not lo <= time < hi:
            continue
        entry = result[name]
        entry['snowflake'] += 1
        entry['days'].setdefault(time.date().isoformat(), {'teradata': 0, 'snowflake': 0})['snowflake'] += 1
    return result


def arguments(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--since', required=True)
    parser.add_argument('--until', default=dt.datetime.now(dt.timezone.utc).isoformat())
    parser.add_argument('--csv', type=Path)
    parser.add_argument('--snowflake-json', type=Path, help='Offline QUERY_HISTORY rows; [] means none')
    parser.add_argument('--json', action='store_true')
    return parser


def collect(args, phase='reads'):
    if timestamp(args.since) >= timestamp(args.until):
        raise ValueError('--since must precede --until')
    sf = json.loads(args.snowflake_json.read_text()) if args.snowflake_json else snowflake(args.since, args.until, phase)
    return summarize(teradata(args.csv), sf, registry(), args.since, args.until)


def render(data):
    lines = ['client | baseline TD (30d) | window TD | window SF']
    for name, row in data.items():
        lines.append(f"{name} | {row['baseline']} | {row['teradata']} | {row['snowflake']}")
        for day, counts in sorted(row['days'].items()):
            lines.append(f"  {day}: TD={counts['teradata']} SF={counts['snowflake']}")
    return '\n'.join(lines)


if __name__ == '__main__':
    args = arguments(__doc__).parse_args()
    data = collect(args)
    print(json.dumps(data, indent=2) if args.json else render(data))
