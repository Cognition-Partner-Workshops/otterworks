"""Independent, full-row parity audit of the customer projection."""

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from contextlib import ExitStack, closing, nullcontext
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

import ibm_db_dbi
import oracledb
import psycopg
from bson.decimal128 import Decimal128
from pymongo import DESCENDING, MongoClient

from .config import Settings


def canonical(value):
    if isinstance(value, Decimal128):
        value = value.to_decimal()
    if isinstance(value, Decimal):
        return {'decimal': format(value.normalize(), 'f')}
    if isinstance(value, datetime):
        return {'datetime': value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc).isoformat(timespec='milliseconds')}
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(k): canonical(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [canonical(v) for v in value]
    return value


def serialized(value):
    return json.dumps(canonical(value), sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def row_hash(key, values):
    return hashlib.sha256(serialized([str(key), values]).encode()).hexdigest()


def profile(values, kind):
    values = [v.to_decimal() if isinstance(v, Decimal128) else v for v in values]
    nonnull = [v for v in values if v is not None]
    result = dict(non_null=len(nonnull), null=len(values) - len(nonnull),
                  distinct=len({serialized(v) for v in nonnull}),
                  min=min(nonnull) if nonnull else None, max=max(nonnull) if nonnull else None)
    if kind == 'money':
        result['sum'] = sum((Decimal(str(v)) for v in nonnull), Decimal(0))
    if kind == 'string':
        result.update(min_length=min(map(len, nonnull), default=None), max_length=max(map(len, nonnull), default=None))
    return result


def compare_profiles(expected, actual):
    return {name: dict(source=canonical(value), target=canonical(actual.get(name)),
                       passed=serialized(value) == serialized(actual.get(name))) for name, value in expected.items()}


@dataclass
class Table:
    source: str
    name: str
    key: str
    fields: dict
    sql: str
    sql_fields: dict
    target: list
    convert: object


def decoded(value):
    raw = bytes.fromhex(value)
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw.decode('cp037')


def tables():
    def cust(r):
        return dict(cust_no=r['cust_no'].rstrip(), name=decoded(r['full_name_hex']), address=r['address'],
                    customer_since=None if str(r['opened_on']) == '0001-01-01' else str(r['opened_on']),
                    raw_cust_no=r['cust_no'].rstrip(), opened_on=str(r['opened_on']), opened_ymd=int(r['opened_ymd']))

    def account(r):
        local = r['opened_at']
        return dict(account_id=int(r['account_id']), source_account_ids=[int(r['account_id'])], name=r['holder_name'], address=r['address'],
                    product_id=int(r['product_id']), product_name=r['product_name'], balance=Decimal(str(r['balance'])),
                    opened_at=local.replace(tzinfo=ZoneInfo('America/New_York'), fold=0).astimezone(timezone.utc),
                    opened_at_local=local.isoformat(), opened_at_tz='America/New_York')

    def projection(fields):
        return {'$project': {'_id': 0, **{k: '$' + v for k, v in fields.items()}}}

    db2_match = {'$match': {'source_keys.db2_cust_no': {'$type': 'string'}}}
    pg_match = {'$match': {'source_keys.crm_contact_id': {'$type': 'string'}}}
    return [
        Table('db2', 'ODL.CUSTMAST', 'cust_no',
              dict(cust_no='string', name='string', address='string', customer_since='string', raw_cust_no='string', opened_on='string', opened_ymd='number'),
              'SELECT CUST_NO, HEX(FULL_NAME) AS FULL_NAME_HEX, ADDRESS, OPENED_ON, OPENED_YMD FROM ODL.CUSTMAST',
              dict(cust_no='RTRIM(CUST_NO)', raw_cust_no='RTRIM(CUST_NO)', address='ADDRESS', opened_ymd='OPENED_YMD'),
              [db2_match, projection(dict(cust_no='source_keys.db2_cust_no', name='source_records.db2.name', address='source_records.db2.address', customer_since='customer_since', raw_cust_no='source_records.db2.cust_no', opened_on='source_records.db2.opened_on', opened_ymd='source_records.db2.opened_ymd'))], cust),
        Table('db2', 'ODL.ACCTHIST', 'history_id',
              dict(history_id='number', cust_no='string', event_on='string', amount='money'),
              'SELECT HISTORY_ID, CUST_NO, EVENT_ON, AMOUNT FROM ODL.ACCTHIST',
              dict(history_id='HISTORY_ID', cust_no='RTRIM(CUST_NO)', amount='AMOUNT'),
              [{'$unwind': '$account_history'}, projection(dict(history_id='account_history.history_id', cust_no='source_keys.db2_cust_no', event_on='account_history.event_on', amount='account_history.amount'))],
              lambda r: dict(history_id=int(r['history_id']), cust_no=r['cust_no'].rstrip(), event_on=str(r['event_on']), amount=Decimal(str(r['amount'])))),
        Table('oracle', 'ACCOUNTS', 'account_id',
              dict(account_id='number', source_account_ids='array', name='string', address='string', product_id='number', product_name='string', balance='money', opened_at='datetime', opened_at_local='string', opened_at_tz='string'),
              'SELECT a.account_id, a.holder_name, a.address, a.product_id, p.name AS product_name, a.balance, a.opened_at FROM accounts a LEFT JOIN products p ON p.product_id=a.product_id',
              dict(account_id='account_id', name='holder_name', address='address', product_id='product_id', product_name='product_name', balance='balance'),
              [{'$unwind': '$accounts'}, projection(dict(account_id='accounts.account_id', source_account_ids='source_keys.oracle_account_ids', name='source_records.oracle.name', address='source_records.oracle.address', product_id='accounts.product.id', product_name='accounts.product.name', balance='accounts.balance', opened_at='accounts.opened_at', opened_at_local='accounts.opened_at_local', opened_at_tz='accounts.opened_at_tz'))], account),
        Table('oracle', 'PRODUCTS', 'product_id', dict(product_id='number', name='string'),
              'SELECT product_id, name FROM products', dict(product_id='product_id', name='name'),
              [{'$unwind': '$accounts'}, {'$group': {'_id': {'product_id': '$accounts.product.id', 'name': '$accounts.product.name'}}}, projection(dict(product_id='_id.product_id', name='_id.name'))],
              lambda r: dict(product_id=int(r['product_id']), name=r['name'])),
        Table('postgres', 'crm.contacts', 'contact_id', dict(contact_id='string', name='string', address='string', credit='money'),
              'SELECT contact_id, full_name, address, credit FROM crm.contacts', dict(name='full_name', address='address'),
              [pg_match, projection(dict(contact_id='source_keys.crm_contact_id', name='source_records.postgres.name', address='source_records.postgres.address', credit='crm.credit'))],
              lambda r: dict(contact_id=str(r['contact_id']).lower(), name=r['full_name'], address=r['address'], credit=Decimal(str(r['credit'])).quantize(Decimal('.01'), rounding=ROUND_HALF_EVEN))),
        Table('postgres', 'crm.service_cases', 'case_id', dict(case_id='string', contact_id='string', subject='string', opened_at='datetime'),
              'SELECT case_id, contact_id, subject, opened_at FROM crm.service_cases', dict(subject='subject'),
              [{'$unwind': '$crm.service_cases'}, projection(dict(case_id='crm.service_cases.case_id', contact_id='source_keys.crm_contact_id', subject='crm.service_cases.subject', opened_at='crm.service_cases.opened_at'))],
              lambda r: dict(case_id=str(r['case_id']).lower(), contact_id=str(r['contact_id']).lower(), subject=r['subject'], opened_at=r['opened_at'].replace(tzinfo=timezone.utc))),
        Table('postgres', 'crm.subscription_snapshots', 'contact_id', dict(contact_id='string', status='string'),
              'SELECT contact_id, status FROM crm.subscription_snapshots', dict(status='status'),
              [pg_match, {'$match': {'crm.subscription_status': {'$exists': True}}}, projection(dict(contact_id='source_keys.crm_contact_id', status='crm.subscription_status'))],
              lambda r: dict(contact_id=str(r['contact_id']).lower(), status=r['status']))]


def sql_rows(conn, query):
    with closing(conn.cursor()) as cursor:
        cursor.execute(query)
        names = [c[0].lower() for c in cursor.description]
        while rows := cursor.fetchmany(2000):
            for row in rows:
                yield dict(zip(names, row))


def source_profiles(conn, table, expected):
    profiles = {field: profile([r[field] for r in expected], kind) for field, kind in table.fields.items()}
    aggregates = ['COUNT(*) AS total_rows']
    aliases = []
    for i, (field, expr) in enumerate(table.sql_fields.items()):
        if table.source == 'postgres' and table.fields[field] == 'string':
            expr = f'({expr} COLLATE "C")'
        operations = dict(non_null=f'COUNT({expr})', distinct=f'COUNT(DISTINCT {expr})', min=f'MIN({expr})', max=f'MAX({expr})')
        if table.fields[field] == 'money':
            operations['sum'] = f'SUM({expr})'
        if table.fields[field] == 'string':
            function = 'CHAR_LENGTH' if table.source == 'postgres' else 'LENGTH'
            operations.update(min_length=f'MIN({function}({expr}))', max_length=f'MAX({function}({expr}))')
        for stat, expression in operations.items():
            alias = f'f{i}_{stat}'
            aliases.append((field, stat, alias))
            aggregates.append(f'{expression} AS {alias}')
    row = next(sql_rows(conn, 'SELECT ' + ', '.join(aggregates) + f' FROM ({table.sql}) parity_source'))
    for field, stat, alias in aliases:
        value = row[alias]
        if stat in ('non_null', 'distinct', 'min_length', 'max_length') and value is not None:
            value = int(value)
        if stat == 'sum':
            value = Decimal(str(value or 0))
        if stat in ('min', 'max') and table.fields[field] == 'number' and value is not None:
            value = int(value)
        profiles[field][stat] = value
    for field in table.sql_fields:
        profiles[field]['null'] = int(row['total_rows']) - profiles[field]['non_null']
    return int(row['total_rows']), profiles


def target_profile(collection, pipeline, field, kind):
    value = '$' + field
    nonnull = {'$ne': [{'$ifNull': [value, None]}, None]}
    group = dict(_id=None, total={'$sum': 1}, non_null={'$sum': {'$cond': [nonnull, 1, 0]}},
                 values={'$addToSet': {'$ifNull': [value, None]}}, min={'$min': value}, max={'$max': value})
    if kind == 'money':
        group['sum'] = {'$sum': value}
    if kind == 'string':
        length = {'$cond': [nonnull, {'$strLenCP': value}, None]}
        group.update(min_length={'$min': length}, max_length={'$max': length})
    project = dict(_id=0, non_null=1, null={'$subtract': ['$total', '$non_null']},
                   distinct={'$size': {'$setDifference': ['$values', [None]]}}, min=1, max=1)
    for stat in ('sum', 'min_length', 'max_length'):
        if stat in group:
            project[stat] = 1
    rows = list(collection.aggregate(pipeline + [{'$group': group}, {'$project': project}], allowDiskUse=True))
    if not rows:
        return profile([], kind)
    return rows[0]


def unplaced_for(table, exceptions):
    selected = []
    raw_keys = {'ODL.CUSTMAST': ('cust_no', 'full_name_hex'), 'ODL.ACCTHIST': ('history_id',),
                'ACCOUNTS': ('account_id',), 'PRODUCTS': ('product_id', 'name'),
                'crm.contacts': ('contact_id', 'full_name'), 'crm.service_cases': ('case_id',),
                'crm.subscription_snapshots': ('contact_id', 'status')}
    for exception in exceptions:
        if exception['reason'] not in ('transform_failed', 'duplicate_match_key', 'orphan_history', 'orphan_service_case', 'orphan_subscription'):
            continue
        if not any(k.startswith(table.source + ':') for k in exception['source_keys']):
            continue
        detail = exception.get('detail', {})
        if all(k in detail for k in raw_keys[table.name]):
            selected.append(exception)
    return selected


def compare_rows(expected, actual, key_field, unplaced_keys=(), limit=20):
    left = defaultdict(list)
    right = defaultdict(list)
    for row in expected:
        left[str(row[key_field])].append(row)
    for row in actual:
        right[str(row.get(key_field))].append(row)
    unplaced_keys = set(unplaced_keys)
    matched = mismatched = 0
    missing = sorted(set(left) - set(right) - unplaced_keys)
    extra = sorted(set(right) - set(left))
    differing = []
    for key in sorted(set(left) & set(right)):
        if len(left[key]) == len(right[key]) == 1 and row_hash(key, left[key][0]) == row_hash(key, right[key][0]):
            matched += 1
        else:
            mismatched += 1
            differing.append(key)
    hash_result = dict(matched=matched, mismatched=mismatched, missing_in_target=len(missing), extra_in_target=len(extra),
                       unplaced=len(set(left) & unplaced_keys), duplicate_source_keys=sum(len(v) > 1 for v in left.values()),
                       duplicate_target_keys=sum(len(v) > 1 for v in right.values()),
                       differing_keys=differing[:limit], missing_keys=missing[:limit], extra_keys=extra[:limit])
    hash_result['passed'] = not any(hash_result[k] for k in ('mismatched', 'missing_in_target', 'extra_in_target', 'duplicate_source_keys', 'duplicate_target_keys'))
    keys = sorted(set(left) - unplaced_keys)
    sampled = [k for k in keys if int(hashlib.sha256(k.encode()).hexdigest(), 16) % 100 == 0]
    if len(keys) <= 4:
        sampled = keys
    differences = []
    fields_compared = 0
    for key in sampled:
        source_row = left[key][0]
        target_row = right[key][0] if key in right else {}
        for field, value in source_row.items():
            fields_compared += 1
            if field not in target_row or serialized(value) != serialized(target_row[field]):
                differences.append(dict(key=key, field=field, expected=canonical(value), actual=canonical(target_row.get(field))))
    return hash_result, dict(size=len(sampled), fields_compared=fields_compared, differences=differences,
                             difference_count=len(differences), keys=sampled, passed=not differences)


def audit_table(conn, collection, table, exceptions):
    raw = list(sql_rows(conn, table.sql))
    expected = []
    raw_by_key = {}
    transform_errors = []
    for row in raw:
        try:
            converted = table.convert(row)
            expected.append(converted)
            raw_by_key[str(converted[table.key])] = {k: str(v) for k, v in row.items()}
        except (ValueError, TypeError, ArithmeticError, KeyError) as error:
            transform_errors.append(dict(key=str(row.get(table.key)), error=type(error).__name__))
    source_count, profiles = source_profiles(conn, table, expected)
    actual = list(collection.aggregate(table.target, allowDiskUse=True))
    unplaced = unplaced_for(table, exceptions)
    unplaced_keys = {e['source_keys'][0].split(':', 1)[1].rstrip() for e in unplaced}
    count = dict(source=source_count, placed=len(actual), unplaced=len(unplaced),
                 passed=source_count == len(actual) + len(unplaced), transform_errors=transform_errors)
    placed_expected = [r for r in expected if str(r[table.key]) not in unplaced_keys]
    profile_checks = {}
    for field, kind in table.fields.items():
        expected_profile = profiles[field] if not unplaced else profile([r[field] for r in placed_expected], kind)
        target = target_profile(collection, table.target, field, kind)
        profile_checks[field] = compare_profiles(expected_profile, target)
    profile_result = dict(fields=profile_checks, passed=all(s['passed'] for f in profile_checks.values() for s in f.values()),
                          basis='placed source rows; SQL aggregates where transform is SQL-expressible')
    hashes, samples = compare_rows(expected, actual, table.key, unplaced_keys)
    hashes['unplaced'] = len(unplaced)
    expected_by_key = {str(r[table.key]): r for r in expected}
    actual_by_key = {str(r.get(table.key)): r for r in actual}
    samples['rows'] = [dict(key=key, raw_source=raw_by_key[key], expected=canonical(expected_by_key[key]),
                            actual=canonical(actual_by_key.get(key, {}))) for key in samples.pop('keys')]
    for difference in samples['differences']:
        difference['raw_source'] = raw_by_key.get(difference['key'])
    accounted_transform_errors = all(e['key'].rstrip() in unplaced_keys for e in transform_errors)
    count['passed'] = count['passed'] and accounted_transform_errors
    return dict(count=count, profile=profile_result, keyed_hash=hashes, sampled_values=samples)


def write_csv(report, path):
    with (nullcontext(path) if hasattr(path, 'write') else Path(path).open('w', newline='')) as output:
        fields = ['run_id', 'source', 'table', 'depth', 'check', 'field', 'source_value', 'target_value', 'status', 'detail']
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for table_name, table in report['tables'].items():
            for depth, result in table['depths'].items():
                base = dict(run_id=report['run_id'], source=table['source'], table=table_name, depth=depth)
                if depth == 'profile':
                    for field, checks in result['fields'].items():
                        for check, values in checks.items():
                            writer.writerow(dict(base, check=check, field=field, source_value=serialized(values['source']), target_value=serialized(values['target']), status='pass' if values['passed'] else 'fail', detail=''))
                else:
                    summary = {k: v for k, v in result.items() if k not in ('rows', 'differences')}
                    writer.writerow(dict(base, check='summary', field='', source_value=result.get('source', ''), target_value=result.get('placed', ''), status='pass' if result['passed'] else 'fail', detail=serialized(summary)))
                    if depth == 'sampled_values':
                        for row in result.get('rows', []):
                            for field, value in row['expected'].items():
                                actual = row['actual'].get(field)
                                passed = field in row['actual'] and serialized(value) == serialized(actual)
                                writer.writerow(dict(base, check='value', field=field, source_value=serialized(value), target_value=serialized(actual), status='pass' if passed else 'fail', detail=serialized(dict(key=row['key'], raw_source=row['raw_source']))))


def validate_run_id(run_id):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', run_id) or run_id == 'latest' or run_id.endswith('.csv'):
        raise ValueError('run_id must be a URL-safe identifier, not latest or ending in .csv')
    return run_id


def run(settings, run_id, csv_path):
    validate_run_id(run_id)
    with ExitStack() as stack:
        db2 = stack.enter_context(closing(ibm_db_dbi.connect(f'DATABASE={settings.db2_database};HOSTNAME={settings.db2_host};PORT={settings.db2_port};PROTOCOL=TCPIP;UID={settings.db2_user};PWD={settings.db2_password};', '', '')))
        oracle = stack.enter_context(closing(oracledb.connect(user=settings.oracle_user, password=settings.oracle_password, dsn=settings.oracle_dsn)))
        oracle.outputtypehandler = lambda cursor, metadata: cursor.var(oracledb.DB_TYPE_VARCHAR, arraysize=cursor.arraysize, outconverter=Decimal) if metadata.type_code == oracledb.DB_TYPE_NUMBER else None
        postgres = stack.enter_context(psycopg.connect(**settings.postgres))
        client = stack.enter_context(MongoClient(**settings.mongo, tz_aware=True))
        db = client[settings.mongo_database]
        exceptions = list(db.mapping_exceptions.find())
        connections = dict(db2=db2, oracle=oracle, postgres=postgres)
        report = dict(run_id=run_id, generated_at=datetime.now(timezone.utc), passed=True, tables={},
                      exception_summary=dict(Counter(e['reason'] for e in exceptions)))
        for table in tables():
            depths = audit_table(connections[table.source], db.customers, table, exceptions)
            report['tables'][table.name] = dict(source=table.source, depths=depths)
        report['passed'] = all(depth['passed'] for table in report['tables'].values() for depth in table['depths'].values())
        write_csv(report, csv_path)
        db.parity_reports.create_index('run_id', unique=True)
        db.parity_reports.create_index([('generated_at', DESCENDING)])
        stored = json.loads(serialized(report))
        stored['generated_at'] = report['generated_at']
        db.parity_reports.replace_one({'run_id': run_id}, stored, upsert=True)
        return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True, type=validate_run_id)
    parser.add_argument('--csv', type=Path)
    args = parser.parse_args()
    report = run(Settings.environment(), args.run_id, args.csv or Path(f'odl-parity-{args.run_id}.csv'))
    summary = dict(run_id=report['run_id'], passed=report['passed'], exception_summary=report['exception_summary'], tables={})
    for name, table in report['tables'].items():
        depths = table['depths']
        summary['tables'][name] = dict(depths={k: v['passed'] for k, v in depths.items()},
                                      hashes=depths['keyed_hash'], sample_size=depths['sampled_values']['size'], sample_diff_count=depths['sampled_values']['difference_count'])
    print(json.dumps(summary, sort_keys=True), flush=True)
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
