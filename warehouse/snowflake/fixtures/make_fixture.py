"""Generate small, deterministic, referentially consistent landing files."""
import argparse
import csv
from datetime import date, datetime, timedelta
from decimal import Decimal
import hashlib
from pathlib import Path
import random

import yaml

ROOT = Path(__file__).resolve().parents[1]

FIRST = 'Mira Tessa Ivo Arlen Nella Soren Liora Ewan Anya Dorian Freya Leif Elara Ronan Cora Alden Iris Nico Esme Orin'.split()
LAST = 'Merrow Vale Fenwick Calder Wren Alder Thorne Ellery Rosden Halden Briar Voss Larkin Selwyn Arden Greaves Marlow Quill Riven Ashby'.split()
COMPANIES = 'Alderquay Brindlehaven Cindermere Dovewick Elmspire Ferncrest Glenmarsh Hearthvale Ironwillow Juniperquay Kestrelford Larkbridge Mosscairn Northfen Oakhollow Pebblewick Quillhaven Reedspire Silverfen Thistlequay'.split()
COUNTRIES = ('US', 'DE', 'GB', 'CA')
CURRENCIES = ('USD', 'EUR', 'GBP', 'CAD')
RATES = tuple(map(Decimal, ('0.0825', '0.19', '0.20', '0.13')))
PLANS = ('Harbor Starter', 'Harbor Team', 'Harbor Business', 'Harbor Scale', 'Harbor Enterprise')
PRICES = tuple(map(Decimal, ('19.00', '49.00', '99.00', '199.00', '399.00')))
ACCOUNTS = (('1000', 'Operating Cash', 'ASSET', 'DR'),
            ('1100', 'Accounts Receivable', 'ASSET', 'DR'),
            ('4000', 'Subscription Revenue', 'REVENUE', 'CR'),
            ('2100', 'Sales Tax Payable', 'LIABILITY', 'CR'),
            ('2200', 'Customer Credits', 'LIABILITY', 'CR'))


def money(value):
    return Decimal(value).quantize(Decimal('0.01'))


def records(rows, seed):
    rng = random.Random(seed)
    data = {}

    def add(table, i, values):
        values = {table + '_ID': i, **values}
        data.setdefault(table, []).append(values)

    for i in range(1, rows + 1):
        k = (i - 1) % 4
        person = (i - 1) % len(FIRST)
        company = COMPANIES[person] + ' Works Ltd'
        first, last = FIRST[person], LAST[person]
        email = f'{first.lower()}.{last.lower()}@{COMPANIES[person].lower()}.example'
        created = datetime(2026, 1, 5, 9, 15) + timedelta(days=i * 3, minutes=rng.randrange(240))
        issued = date(2026, 8, 1) + timedelta(days=(i - 1) * 3 % 80)
        event = datetime.combine(issued + timedelta(days=5), datetime.min.time()) + timedelta(hours=10, minutes=rng.randrange(240))
        common = dict(CREATED_AT=created, IS_ACTIVE='Y')
        customer = dict(CUSTOMER_ID=i, CURRENCY_CODE=CURRENCIES[k])
        user = dict(USER_ID=i, **common)
        document = dict(DOCUMENT_ID=i, **common)
        plan = (i - 1) // 4 % 5
        quantity = (1, 3, 5, 8)[(i - 1) % 4]
        price = PRICES[plan]
        net = money(price * quantity)
        tax = money(net * RATES[k])
        total = net + tax
        paid = money(total / 2)
        add('CUSTOMER_ACCOUNT', i, dict(**customer, **common, OWNER_USER_ID=i,
            ACCOUNT_NUMBER=f'ACC-{i:06d}', LEGAL_NAME=company, BILLING_COUNTRY=COUNTRIES[k], PAYMENT_TERMS_DAYS=30))
        add('PLAN_CATALOG', i, dict(**common, CUSTOMER_ID=i, PLAN_CODE=f'HBR-{plan + 1}-{CURRENCIES[k]}',
            PLAN_NAME=PLANS[plan], MONTHLY_PRICE=price, CURRENCY_CODE=CURRENCIES[k], STORAGE_LIMIT_GB=(50, 250, 1000, 5000, 20000)[plan], SEAT_LIMIT=(3, 10, 25, 100, 500)[plan]))
        add('SUBSCRIPTION', i, dict(**customer, **common, PLAN_CATALOG_ID=i, START_DATE=created.date(),
            NEXT_BILL_DATE=issued + timedelta(days=30), SEAT_COUNT=quantity, STATUS='ACTIVE'))
        add('INVOICE_HDR', i, dict(**customer, INVOICE_NUMBER=f'INV-2026-{i:06d}', INVOICE_DATE=issued,
            DUE_DATE=issued + timedelta(days=30), SUBTOTAL_AMOUNT=net, TAX_AMOUNT=tax, TOTAL_AMOUNT=total, STATUS='PARTIALLY_PAID'))
        add('INVOICE_LINE', i, dict(**customer, INVOICE_HDR_ID=i, DESCRIPTION=PLANS[plan] + ' monthly subscription',
            QUANTITY=quantity, UNIT_PRICE=price, LINE_AMOUNT=net, TAX_AMOUNT=tax, SERVICE_DATE=issued))
        add('PAYMENT', i, dict(**customer, INVOICE_HDR_ID=i, PAYMENT_NUMBER=f'PAY-2026-{i:06d}',
            PAYMENT_DATE=issued + timedelta(days=7), AMOUNT=paid, METHOD=('BANK_TRANSFER', 'CARD')[i % 2], STATUS='SETTLED', CREATED_AT=event))
        add('CREDIT_NOTE', i, dict(**customer, INVOICE_HDR_ID=i, CREDIT_NUMBER=f'CN-2026-{i:06d}',
            ISSUE_DATE=issued + timedelta(days=10), AMOUNT=money(net * Decimal('0.05')),
            REASON='Service availability credit', STATUS='ISSUED', CREATED_AT=event + timedelta(days=5)))
        add('TAX_RATE', i, dict(**customer, **common, COUNTRY_CODE=COUNTRIES[k], TAX_NAME=('State sales tax', 'Standard VAT', 'Standard VAT', 'Ontario HST')[k], RATE=RATES[k], EFFECTIVE_DATE=date(2026, 1, 1)))
        add('USAGE_DAILY', i, dict(**customer, **common, USAGE_DATE=issued, QUANTITY=quantity,
            UNIT_PRICE=Decimal('0.10'), AMOUNT=money(Decimal('0.10') * quantity)))
        add('BILLING_ADJ', i, dict(**customer, **common, INVOICE_HDR_ID=i, ADJUSTMENT_DATE=issued + timedelta(days=10),
            AMOUNT=money(net * Decimal('0.05')), REASON='Service availability credit'))
        folder = ('Finance', 'Operations', 'Product', 'People')[k]
        title = f'{company} — {folder} operating review'
        add('FOLDER', i, dict(**common, OWNER_USER_ID=i, FOLDER_NAME=folder + ' Reviews', PATH=f'/workspaces/{COMPANIES[person].lower()}/{folder.lower()}', VISIBILITY='TEAM'))
        add('DOCUMENT', i, dict(**common, OWNER_USER_ID=i, FOLDER_ID=i, TITLE=title, DOCUMENT_TYPE='OPERATING_REVIEW', STATUS='PUBLISHED'))
        add('DOC_VERSION', i, dict(**document, VERSION_NUMBER=1, CHANGE_SUMMARY='Approved quarterly operating review', FILE_OBJECT_ID=i))
        add('DOC_SHARE', i, dict(**document, USER_ID=i, PERMISSION='EDIT', EXPIRES_DATE=date(2027, 1, 31)))
        add('DOC_TAG', i, dict(**document, TAG_NAME=folder.lower(), TAG_CATEGORY='Department'))
        add('FILE_OBJECT', i, dict(**document, OBJECT_KEY=f'reviews/{COMPANIES[person].lower()}/operating-review.pdf', MIME_TYPE='application/pdf', SIZE_BYTES=rng.randrange(120000, 900000), CHECKSUM=hashlib.sha256(title.encode()).hexdigest()))
        add('DOC_COMMENT', i, dict(**document, USER_ID=i, BODY='The revised forecast reconciles to the approved operating budget.', RESOLVED='Y'))
        add('COLLAB_SESSION', i, dict(**document, USER_ID=i, STARTED_AT=event, ENDED_AT=event + timedelta(minutes=25), EDIT_COUNT=rng.randrange(2, 25), CLIENT_TYPE='WEB'))
        add('STORAGE_USAGE_DAILY', i, dict(**user, USAGE_DATE=issued, SIZE_BYTES=rng.randrange(1000000, 9000000), FILE_COUNT=rng.randrange(20, 90), QUOTA_BYTES=50000000000))
        add('SEARCH_INDEX_LOG', i, dict(**document, INDEXED_AT=event, INDEX_NAME='workspace-documents', STATUS='INDEXED', DURATION_MS=rng.randrange(40, 800)))
        add('APP_USER', i, dict(**user, EMAIL=email, FIRST_NAME=first, LAST_NAME=last, TIME_ZONE=('America/New_York', 'Europe/Berlin', 'Europe/London', 'America/Toronto')[k], STATUS='ACTIVE'))
        add('USER_PROFILE', i, dict(**user, DISPLAY_NAME=f'{first} {last}', JOB_TITLE=('Finance Manager', 'Operations Lead', 'Product Analyst', 'People Partner')[k], DEPARTMENT=folder, LOCALE=('en-US', 'de-DE', 'en-GB', 'en-CA')[k]))
        add('TEAM', i, dict(**common, OWNER_USER_ID=i, TEAM_NAME=company + ' ' + folder, DESCRIPTION=folder + ' planning and reporting'))
        add('TEAM_MEMBER', i, dict(**user, TEAM_ID=i, MEMBERSHIP_ROLE='OWNER', JOINED_DATE=created.date()))
        add('ROLE_GRANT', i, dict(**user, ROLE_NAME='Workspace Editor', SCOPE_NAME=company, GRANTED_AT=created))
        add('SSO_IDENTITY', i, dict(**user, PROVIDER='Workspace SAML', EXTERNAL_SUBJECT=hashlib.sha256(email.encode()).hexdigest(), EMAIL=email))
        add('LOGIN_EVENT', i, dict(**user, LOGIN_AT=event, AUTH_METHOD='SAML_MFA', OUTCOME='SUCCESS', COUNTRY_CODE=COUNTRIES[k]))
        add('USER_ACTIVITY_DAILY', i, dict(**user, ACTIVITY_DATE=issued, EVENT_COUNT=35 + i, DOCUMENTS_VIEWED=5 + i, ACTIVE_MINUTES=60 + i))
        add('USER_PREF', i, dict(**user, PREF_KEY='notification_digest', PREF_VALUE='weekly', UPDATED_AT=event))
        add('USER_STATUS_HIST', i, dict(**user, STATUS_CODE='ACTIVE', REASON='Workspace invitation accepted', EFFECTIVE_DATE=created.date()))
        add('AUDIT_EVENT', i, dict(**common, ACTOR_USER_ID=i, DOCUMENT_ID=i, ACTION_NAME='DOCUMENT_PUBLISHED', OUTCOME='SUCCESS', RESOURCE_TYPE='DOCUMENT'))
        add('AUDIT_EVENT_ARCHIVE', i, dict(**common, AUDIT_EVENT_ID=i, ARCHIVED_AT=event + timedelta(days=30), ARCHIVE_PATH=f'audit/2026/{COMPANIES[person].lower()}/publication.json', RETENTION_UNTIL=date(2033, 12, 31)))
        add('ACCESS_REVIEW', i, dict(**user, REVIEWER_USER_ID=i % rows + 1, REVIEW_DATE=issued, DECISION='RETAIN', REVIEW_NOTES='Access matches current department responsibilities'))
        add('RETENTION_POLICY', i, dict(**common, POLICY_NAME=company + ' records policy', RESOURCE_TYPE='AUDIT_EVENT', RETENTION_DAYS=2555, DISPOSITION='ARCHIVE'))
        add('DATA_EXPORT_REQ', i, dict(**user, REQUESTED_AT=event, EXPORT_FORMAT='JSON', STATUS='COMPLETED', PURPOSE='Quarterly access certification'))
        add('COMPLIANCE_FLAG', i, dict(**common, AUDIT_EVENT_ID=i, FLAG_CODE='REVIEW_REQUIRED', SEVERITY='LOW', REVIEW_STATUS='RESOLVED'))
        add('SECURITY_ALERT', i, dict(**common, ACTOR_USER_ID=i, SEVERITY='LOW', ALERT_TYPE='NEW_DEVICE_SIGN_IN', RESOLUTION='Device verified by workspace owner'))
        add('LEGAL_HOLD', i, dict(**document, MATTER_NUMBER=f'MAT-2026-{i:06d}', REASON='Contract records preservation', RELEASE_DATE=date(2027, 6, 30)))
        add('AUDIT_DAILY_SUMMARY', i, dict(**common, SUMMARY_DATE=issued, EVENT_COUNT=100 + i, SUCCESS_COUNT=99 + i, FAILURE_COUNT=1))
        add('AUDIT_RECON', i, dict(**common, AUDIT_EVENT_ID=i, RECON_DATE=issued, SOURCE_SYSTEM='Workspace event stream', STATUS='MATCHED', DIFFERENCE_COUNT=0))

    for k, currency in enumerate(CURRENCIES if rows else ()):
        for offset, (code, name, kind, balance) in enumerate(ACCOUNTS, 1):
            add('GL_ACCOUNT', k * 5 + offset, dict(ACCOUNT_CODE=f'{code}-{currency}', ACCOUNT_NAME=name,
                ACCOUNT_TYPE=kind, CURRENCY_CODE=currency, NORMAL_BALANCE=balance,
                CREATED_AT=datetime(2026, 1, 1), IS_ACTIVE='Y'))
        invoices = [r for r in data['INVOICE_HDR'] if r['CURRENCY_CODE'] == currency]
        if not invoices:
            continue
        posting = max(r['INVOICE_DATE'] for r in invoices) + timedelta(days=10)
        net = sum(r['SUBTOTAL_AMOUNT'] for r in invoices)
        tax = sum(r['TAX_AMOUNT'] for r in invoices)
        paid = sum(r['AMOUNT'] for r in data['PAYMENT'] if r['CURRENCY_CODE'] == currency)
        entries = ((2, net + tax, 0, 'Invoice receivables'), (3, 0, net, 'Subscription revenue'),
                   (4, 0, tax, 'Sales tax payable'), (1, paid, 0, 'Settled customer receipts'),
                   (2, 0, paid, 'Receivables settlement'))
        for offset, (account, debit, credit, description) in enumerate(entries, 1):
            add('GL_JOURNAL_LINE', len(data.get('GL_JOURNAL_LINE', [])) + 1,
                dict(JOURNAL_ID=k * 2 + (1 if offset <= 3 else 2), GL_ACCOUNT_ID=k * 5 + account,
                     SOURCE_BATCH_NUMBER=f'BATCH-2026-{currency}', DESCRIPTION=description,
                     POSTING_DATE=posting, DEBIT_AMOUNT=money(debit), CREDIT_AMOUNT=money(credit), CURRENCY_CODE=currency))
    return data


def generate(rows=20, seed=1110, output=None):
    if rows < 0:
        raise ValueError("rows must be nonnegative")
    data = records(rows, seed)
    spec = yaml.safe_load((ROOT / "fixture_columns.yml").read_text())
    output = Path(output) if output is not None else ROOT / "fixtures/landing"
    for area, tables in spec.items():
        for table, columns in tables.items():
            path = output / area / table / "20261101.psv"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", newline="") as stream:
                writer = csv.writer(stream, delimiter="|", lineterminator="\n")
                writer.writerow(columns)
                for row in data.get(table, []):
                    writer.writerow(row[column] for column in columns)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=20)
    parser.add_argument("--seed", type=int, default=1110)
    args = parser.parse_args()
    generate(args.rows, args.seed)
