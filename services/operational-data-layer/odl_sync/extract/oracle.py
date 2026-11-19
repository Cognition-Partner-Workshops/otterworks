import time
from decimal import Decimal
import oracledb
from bson.int64 import Int64

from . import Extract, ExtractError, SourceRecord, raw_strings, sql_rows, transform
from ..normalize import integer, money, oracle_time, text


def from_rows(accounts, products):
    result = Extract('oracle')
    catalog = {}
    for product in transform(result, products, 'product_id', lambda r: dict(id=integer(r['product_id']), name=text(r['name']))):
        catalog[product['id']] = product

    def account(row):
        key = Int64(integer(row['account_id']))
        product = catalog[integer(row['product_id'])]
        opened, ambiguous = oracle_time(row['opened_at'])
        data = dict(account_id=key, product=product, balance=money(row['balance']),
                    opened_at=opened, opened_at_local=row['opened_at'].isoformat(), opened_at_tz='America/New_York')
        return SourceRecord('oracle', str(key), text(row['holder_name']), text(row['address']),
                            dict(account=data, ambiguous=ambiguous), raw_strings(row))

    result.records = list(transform(result, accounts, 'account_id', account))
    return result


def extract(settings):
    start = time.time()
    try:
        conn = oracledb.connect(user=settings.oracle_user, password=settings.oracle_password, dsn=settings.oracle_dsn)
    except Exception as error:
        raise ExtractError('connect') from error
    try:
        cur = conn.cursor()
        cur.outputtypehandler = lambda cursor, metadata: cursor.var(oracledb.DB_TYPE_VARCHAR, arraysize=cursor.arraysize, outconverter=Decimal) if metadata.type_code == oracledb.DB_TYPE_NUMBER else None
        products = list(sql_rows(cur, 'SELECT product_id, name FROM products'))
        result = from_rows(sql_rows(cur, 'SELECT account_id, holder_name, address, product_id, balance, opened_at FROM accounts'), products)
        result.checkpoint = start
        return result
    except Exception as error:
        raise ExtractError('read') from error
    finally:
        conn.close()
