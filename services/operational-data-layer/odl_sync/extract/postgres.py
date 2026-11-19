import time
import psycopg

from . import Extract, ExtractError, SourceRecord, duplicate_parent_keys, raw_strings, rejected, sql_rows, transform
from ..normalize import money, text, utc_time, uuid_key


def from_rows(contacts, cases, subscriptions):
    result = Extract('postgres')

    def contact(row):
        key = uuid_key(row['contact_id'])
        return SourceRecord('postgres', key, text(row['full_name']), text(row['address']),
                            dict(contact_id=key, credit=money(row['credit'], rounded=True), service_cases=[]), raw_strings(row))

    result.records = list(transform(result, contacts, 'contact_id', contact))
    parents = {r.key: r for r in result.records}
    duplicates = duplicate_parent_keys(result.records)

    def case(row):
        return uuid_key(row['contact_id']), dict(case_id=uuid_key(row['case_id']), subject=text(row['subject']), opened_at=utc_time(row['opened_at'])), row

    for key, value, raw in transform(result, cases, 'case_id', case):
        if key not in parents:
            result.unplaced.append(rejected('postgres', 'orphan_service_case', raw['case_id'], raw))
        else:
            parents[key].data['service_cases'].append(value)
            if key in duplicates:
                parents[key].dependents.append(('orphan_service_case', value['case_id'], raw))

    def subscription(row):
        return uuid_key(row['contact_id']), text(row['status']), row

    for key, value, raw in transform(result, subscriptions, 'contact_id', subscription):
        if key not in parents:
            result.unplaced.append(rejected('postgres', 'orphan_subscription', key, raw))
        else:
            parents[key].data['subscription_status'] = value
            if key in duplicates:
                parents[key].dependents.append(('orphan_subscription', key, raw))
    for record in result.records:
        record.data['service_cases'].sort(key=lambda r: r['case_id'])
    return result


def extract(settings):
    start = time.time()
    try:
        conn = psycopg.connect(**settings.postgres)
    except Exception as error:
        raise ExtractError('connect') from error
    try:
        with conn.cursor() as cur:
            contacts = list(sql_rows(cur, 'SELECT contact_id, full_name, address, credit FROM crm.contacts'))
            cases = list(sql_rows(cur, 'SELECT case_id, contact_id, subject, opened_at FROM crm.service_cases'))
            result = from_rows(contacts, cases, sql_rows(cur, 'SELECT contact_id, status FROM crm.subscription_snapshots'))
            result.checkpoint = start
            return result
    except Exception as error:
        raise ExtractError('read') from error
    finally:
        conn.close()
