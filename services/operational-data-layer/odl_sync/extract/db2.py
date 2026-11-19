import time
import ibm_db_dbi

from . import Extract, ExtractError, SourceRecord, raw_strings, rejected, sql_rows, transform
from ..normalize import customer_since, date_string, db2_key, db2_name, integer, money, text


def from_rows(customers, history):
    result = Extract('db2')

    def customer(row):
        key = db2_key(row['cust_no'])
        opened = date_string(row['opened_on'])
        ymd = integer(row['opened_ymd'])
        if int(opened.replace('-', '')) != ymd:
            raise ValueError('date_mismatch')
        return SourceRecord('db2', key, db2_name(row['full_name_hex']), text(row['address']),
                            dict(customer_since=customer_since(opened), source_record=dict(cust_no=key, opened_on=opened, opened_ymd=ymd), history=[]), raw_strings(row))

    result.records = list(transform(result, customers, 'cust_no', customer))
    parents = {r.key: r for r in result.records}

    def event(row):
        return db2_key(row['cust_no']), dict(history_id=integer(row['history_id']),
                    event_on=date_string(row['event_on']), amount=money(row['amount'])), row

    for key, value, raw in transform(result, history, 'history_id', event):
        if key not in parents:
            result.unplaced.append(rejected('db2', 'orphan_history', raw['history_id'], raw))
        else:
            parents[key].data['history'].append(value)
    for record in result.records:
        record.data['history'].sort(key=lambda r: r['history_id'])
    return result


def extract(settings):
    start = time.time()
    try:
        conn = ibm_db_dbi.connect(f'DATABASE={settings.db2_database};HOSTNAME={settings.db2_host};PORT={settings.db2_port};PROTOCOL=TCPIP;UID={settings.db2_user};PWD={settings.db2_password};', '', '')
    except Exception as error:
        raise ExtractError('connect') from error
    try:
        cur = conn.cursor()
        customers = list(sql_rows(cur, 'SELECT CUST_NO, HEX(FULL_NAME) AS FULL_NAME_HEX, ADDRESS, OPENED_ON, OPENED_YMD FROM ODL.CUSTMAST'))
        result = from_rows(customers, sql_rows(cur, 'SELECT HISTORY_ID, CUST_NO, EVENT_ON, AMOUNT FROM ODL.ACCTHIST'))
        result.checkpoint = start
        return result
    except Exception as error:
        raise ExtractError('read') from error
    finally:
        conn.close()
