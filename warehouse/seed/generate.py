import argparse
import csv
import datetime as dt
import hashlib
import random
from pathlib import Path

try:
    from .columns import TABLES
    from .profiles import enrich
except ImportError:
    from columns import TABLES
    from profiles import enrich


RESERVED_START = 9_000_000_001
ACCOUNT_ROWS = 100
DOCUMENT_ROWS = 50
REFERENCES = {
    'OWNER_USER_ID': 'APP_USER', 'USER_ID': 'APP_USER', 'ACTOR_USER_ID': 'APP_USER',
    'CUSTOMER_ID': 'CUSTOMER_ACCOUNT', 'SUBSCRIPTION_ID': 'SUBSCRIPTION',
    'INVOICE_ID': 'INVOICE_HDR', 'DOCUMENT_ID': 'DOCUMENT', 'FOLDER_ID': 'FOLDER',
    'TEAM_ID': 'TEAM',
    'TAX_RATE_ID': 'TAX_RATE', 'GL_ACCOUNT_ID': 'GL_ACCOUNT', 'CREDIT_NOTE_ID': 'CREDIT_NOTE',
}
DATE_POINTS = ('2026-10-31', '2024-02-29', '2025-12-31', '2026-01-01', '1999-12-31', '2026-11-30')


def plan_code(index):
    return ('PRO', 'TEAM')[index - 1] if index <= 2 else f'PLAN{index:03d}'


def extra_count(name):
    if name in ('APP_USER', 'CUSTOMER_ACCOUNT', 'SUBSCRIPTION', 'INVOICE_HDR', 'DOC_VERSION', 'STORAGE_USAGE_DAILY'):
        return ACCOUNT_ROWS
    return DOCUMENT_ROWS if name == 'DOCUMENT' else 0


def make_row(table, key, rng, counts, business_date, seed=1110):
    date = business_date - dt.timedelta(days=(key - 1) % 3)
    row = {}
    for column in table.columns:
        name, kind = column.name, column.kind
        if name == table.names[0]:
            value = key
        elif name in REFERENCES:
            value = (key - 1) % counts[REFERENCES[name]] + 1
        elif name == 'PLAN_CODE':
            value = plan_code(key if table.name == 'PLAN_CATALOG' else rng.randrange(1, counts['PLAN_CATALOG'] + 1))
        elif name == 'CURRENCY_CD':
            value = 'USD'
        elif name == 'COUNTRY_CD':
            value = ('US', 'GB', 'DE', 'CA')[key % 4]
        elif name in ('STATUS_CD', 'RESULT_CD', 'DECISION_CD'):
            value = 'ACTIVE' if name == 'STATUS_CD' else ('SUCCESS' if name == 'RESULT_CD' else 'APPROVED')
        elif name == 'CONTENT_HASH':
            value = f'{key:064x}'
        elif name == 'TIMEZONE':
            value = 'UTC'
        elif kind == 'D':
            if name in ('CREATED_DT', 'START_DT', 'EFFECTIVE_DT', 'VALID_FROM', 'JOINED_DT', 'GRANTED_DT'):
                value = business_date - dt.timedelta(days=730)
            elif name in ('END_DT', 'VALID_TO'):
                value = business_date + dt.timedelta(days=365)
            elif name == 'PERIOD_START_DT':
                value = date.replace(day=1)
            else:
                value = date
            value = value.isoformat()
        elif kind == 'T':
            seconds = (key - 1) // counts['DOCUMENT'] if name == 'VERSION_TS' else (key - 1) % 86400
            value = (dt.datetime.combine(date, dt.time(12)) + dt.timedelta(seconds=seconds)).isoformat(sep=' ')
            if table.name == 'DOC_VERSION':
                value = (dt.datetime.combine(business_date, dt.time(12)) + dt.timedelta(seconds=seconds)).isoformat(sep=' ')
        elif kind in ('B', 'I'):
            if name == 'VERSION_NO':
                value = (key - 1) // counts['DOCUMENT'] + 1
            elif name == 'DIFFERENCE_COUNT':
                value = 0
            elif name in ('SOURCE_COUNT', 'TARGET_COUNT'):
                value = 100
            else:
                value = rng.randrange(1, 10000)
        elif kind in ('N', 'Q'):
            value = f'{rng.randrange(1, 10000) / (10000 if kind == "Q" else 100):.{4 if kind == "Q" else 2}f}'
        elif kind.startswith('C'):
            value = {'ROLE_CD': 'MEMBER', 'ACCESS_LEVEL': 'READ', 'METHOD_CD': 'CARD',
                     'SEVERITY_CD': 'LOW', 'STORAGE_CLASS': 'STANDARD', 'CLIENT_TYPE': 'WEB',
                     'EVENT_TYPE': 'READ', 'USAGE_TYPE': 'REQUEST', 'PROVIDER_CD': 'OIDC',
                     'REASON_CD': 'SERVICE', 'FLAG_TYPE': 'REVIEW'}.get(name, 'DEFAULT')
        else:
            value = ''
        row[name] = value
    if table.name == 'INVOICE_HDR':
        row['CUSTOMER_ID'] = (row['SUBSCRIPTION_ID'] - 1) % counts['CUSTOMER_ACCOUNT'] + 1
    return enrich(table, row, key, rng, counts, business_date, seed)


def rows_for(table, rows, seed, business_date):
    counts = {t.name: t.count(rows) for t in TABLES}
    derived = int.from_bytes(hashlib.sha256(f'{seed}:{table.name}'.encode()).digest()[:8], 'big')
    rng = random.Random(derived)
    for key in range(1, counts[table.name] + 1):
        yield make_row(table, key, rng, counts, business_date, seed)
    extra_rng = random.Random(derived ^ RESERVED_START)
    for index in range(extra_count(table.name)):
        key = RESERVED_START + index
        if table.name == 'STORAGE_USAGE_DAILY':
            key = RESERVED_START + index // 2
            row = make_row(table, key, random.Random(key + seed), counts, business_date, seed)
        else:
            row = make_row(table, key, extra_rng, counts, business_date, seed)
        if table.name == 'APP_USER':
            row['DISPLAY_NAME'] += ' - Senior Workspace Operations and Records Governance Coordinator'
        elif table.name == 'CUSTOMER_ACCOUNT':
            row['OWNER_USER_ID'] = key
            row['CURRENCY_CD'] = 'USD'
        elif table.name == 'SUBSCRIPTION':
            row.update(CUSTOMER_ID=key, PLAN_CODE=('pro', 'Pro ', 'TEAM  ', 'team')[index % 4])
        elif table.name == 'INVOICE_HDR':
            date = dt.date.fromisoformat(DATE_POINTS[index % len(DATE_POINTS)])
            row.update(CUSTOMER_ID=key, SUBSCRIPTION_ID=key, CURRENCY_CD=('usd', 'Usd', 'USD')[index % 3],
                       INVOICE_DT=date.isoformat(), BILL_DT=date.isoformat(), PERIOD_START_DT=date.replace(day=1).isoformat())
            row['INVOICE_NUMBER'] = f'INV-{date.year}-{key:07d}'
        elif table.name == 'DOCUMENT':
            row.update(OWNER_USER_ID=key, CUSTOMER_ID=key)
        elif table.name == 'DOC_VERSION':
            row.update(DOCUMENT_ID=RESERVED_START + index // 2, VERSION_NO=index % 2 + 1,
                       VERSION_TS=business_date.isoformat() + ' 23:59:00', FILE_SIZE=4096 + index,
                       CONTENT_HASH=f'{key:064x}')
        elif table.name == 'STORAGE_USAGE_DAILY':
            row.update(CUSTOMER_ID=key, OWNER_USER_ID=key, USAGE_DT=business_date.isoformat(),
                       BYTES_USED=1048576 * (index // 2 + 1), OBJECT_COUNT=index // 2 + 1)
        yield row


def generate(rows=200000, seed=1110, out=Path('warehouse/landing'), business_date='20261109'):
    if rows < 1 or rows >= RESERVED_START:
        raise ValueError('rows must be positive and below the reserved key range')
    if len(business_date) != 8 or not business_date.isascii() or not business_date.isdigit():
        raise ValueError('business-date must be YYYYMMDD')
    date = dt.datetime.strptime(business_date, '%Y%m%d').date()
    result = {}
    for table in TABLES:
        directory = Path(out) / table.area / table.name
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (business_date + '.psv')
        with path.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.writer(handle, delimiter='|', lineterminator='\n')
            writer.writerows(tuple(row[c] for c in table.names) for row in rows_for(table, rows, seed, date))
        result[table.name] = table.count(rows) + extra_count(table.name)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rows', type=int, default=200000)
    parser.add_argument('--seed', type=int, default=1110)
    parser.add_argument('--out', type=Path, default=Path('warehouse/landing'))
    parser.add_argument('--business-date', default='20261109')
    args = parser.parse_args()
    try:
        counts = generate(args.rows, args.seed, args.out, args.business_date)
    except ValueError as exc:
        parser.error(str(exc))
    print(f'Generated {sum(counts.values())} rows across {len(counts)} tables in {args.out}')


if __name__ == '__main__':
    main()
