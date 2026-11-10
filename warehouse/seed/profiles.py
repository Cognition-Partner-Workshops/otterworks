import hashlib
import random


FIRST_NAMES = ('Ingrid', 'Mira', 'Leonie', 'Jonas', 'Soren', 'Amara', 'Tomas', 'Elise',
               'Nadia', 'Callum', 'Freya', 'Mateo', 'Linnea', 'Rafael', 'Anika', 'Celine')
LAST_STARTS = ('Hald', 'Lind', 'Berg', 'Merr', 'Voss', 'Sol', 'Briar', 'Ash', 'Nor', 'Wren')
LAST_ENDS = ('en', 'holm', 'vik', 'ford', 'well', 'sen', 'lund', 'wood')
COMPANY_STARTS = ('Alder', 'Briar', 'Cedar', 'Dawn', 'Elk', 'Fen', 'Glen', 'Harbor',
                  'Juniper', 'Linden', 'Meadow', 'North', 'Silver', 'Stone', 'Willow', 'Wind')
COMPANY_ENDS = ('brook', 'crest', 'dale', 'field', 'ford', 'grove', 'haven', 'mere', 'ridge', 'vale', 'wick', 'wood')
INDUSTRIES = ('Freight', 'Dental', 'Analytics', 'Engineering', 'Medical', 'Advisory', 'Logistics', 'Design')
REGIONS = (
    ('US', 'California', 'USD', 'LLC', '0.0725', 'America/Los_Angeles'),
    ('GB', 'England', 'GBP', 'Ltd', '0.2000', 'Europe/London'),
    ('DE', 'Bavaria', 'EUR', 'GmbH', '0.1900', 'Europe/Berlin'),
    ('NO', 'Oslo', 'NOK', 'AS', '0.2500', 'Europe/Oslo'),
    ('CA', 'Ontario', 'CAD', 'Inc', '0.1300', 'America/Toronto'),
    ('AU', 'New South Wales', 'AUD', 'Pty Ltd', '0.1000', 'Australia/Sydney'),
    ('US', 'Oregon', 'USD', 'LLC', '0.0000', 'America/Los_Angeles'),
    ('FR', 'Ile-de-France', 'EUR', 'SAS', '0.2000', 'Europe/Paris'),
)
CHART = (
    (1000, 'Cash and bank', 'ASSET', 'DR'),
    (1200, 'Accounts receivable', 'ASSET', 'DR'),
    (2100, 'Accounts payable', 'LIABILITY', 'CR'),
    (2200, 'Sales tax payable', 'LIABILITY', 'CR'),
    (2300, 'Deferred revenue', 'LIABILITY', 'CR'),
    (3000, 'Retained earnings', 'EQUITY', 'CR'),
    (4000, 'Subscription revenue', 'REVENUE', 'CR'),
    (4100, 'Usage revenue', 'REVENUE', 'CR'),
    (5000, 'Hosting and storage costs', 'EXPENSE', 'DR'),
    (6100, 'Payment processing fees', 'EXPENSE', 'DR'),
)
PLAN_NAMES = ('Workspace Professional', 'Workspace Team', 'Records Essentials', 'Workflow Business',
              'Secure Archive', 'Collaboration Enterprise', 'Compliance Plus', 'Document Operations')
PLAN_PRICES = ('29.00', '79.00', '19.50', '149.00', '249.00', '599.00', '349.00', '99.00')
TEAMS = ('Revenue Operations', 'Customer Enablement', 'Legal and Compliance', 'Financial Control',
         'People Operations', 'Product Delivery', 'Client Services', 'Information Security')
DOCUMENT_TOPICS = {
    'pdf': ('Supplier onboarding', 'Signed service agreement', 'Data processing addendum'),
    'docx': ('Expense policy', 'Board minutes', 'Service agreement draft'),
    'xlsx': ('Quarterly accounts', 'Expense reconciliation', 'Purchase approval register'),
    'pptx': ('Board briefing', 'Project handover', 'Quarterly business review'),
    'csv': ('Usage export', 'Supplier register', 'Payment reconciliation'),
    'txt': ('Meeting notes', 'Access review checklist', 'Records transfer notes'),
}
FILE_TYPES = ('pdf', 'docx', 'xlsx', 'pptx', 'csv', 'txt')
CREDIT_REASONS = (
    ('SLA_CREDIT', 'Service availability credit approved by account operations'),
    ('DUPLICATE', 'Duplicate charge reversed after billing review'),
    ('PRORATION', 'Unused subscription days following a plan change'),
    ('GOODWILL', 'Commercial goodwill credit agreed with the customer'),
    ('CANCELLATION', 'Subscription cancellation within the notice period'),
)
AUDIT_ACTIONS = ('DOC_VIEW', 'DOC_DOWNLOAD', 'DOC_UPLOAD', 'DOC_SHARE',
                 'VERSION_PUB', 'ACCESS_DENY', 'POLICY_APPLY', 'EXPORT_REQ')


def person(rng):
    return rng.choice(FIRST_NAMES) + ' ' + rng.choice(LAST_STARTS) + rng.choice(LAST_ENDS)


def company(rng, region):
    return rng.choice(COMPANY_STARTS) + rng.choice(COMPANY_ENDS) + ' ' + rng.choice(INDUSTRIES) + ' ' + region[3]


def money(cents):
    return f'{cents / 100:.2f}'


def usage_cents(key, seed):
    rng = random.Random(seed ^ (key * 7919))
    return 0 if key % 37 == 0 else min(25000000, round(rng.lognormvariate(8.7, 1.35)))


def enrich(table, row, key, rng, counts, business_date, seed):
    name = table.name
    customer = row.get('CUSTOMER_ID', key)
    region = REGIONS[(customer - 1) % len(REGIONS)]
    if 'COUNTRY_CD' in row:
        row['COUNTRY_CD'] = region[0]
    if 'CURRENCY_CD' in row:
        row['CURRENCY_CD'] = region[2]
    if 'TIMEZONE' in row:
        row['TIMEZONE'] = region[5]
    choices = {
        'ROLE_CD': ('MEMBER', 'ADMIN', 'REVIEWER', 'BILLING'),
        'ACCESS_LEVEL': ('READ', 'EDIT', 'OWNER'),
        'METHOD_CD': ('CARD', 'BANK_WIRE', 'ACH', 'DIRECT_DEBIT'),
        'SEVERITY_CD': ('LOW', 'MEDIUM', 'HIGH'),
        'STORAGE_CLASS': ('STANDARD', 'ARCHIVE', 'INFREQUENT'),
        'CLIENT_TYPE': ('WEB', 'DESKTOP', 'MOBILE', 'API'),
        'EVENT_TYPE': AUDIT_ACTIONS,
        'USAGE_TYPE': ('API_CALL', 'SIGNATURE', 'OCR_PAGE', 'WORKFLOW'),
        'PROVIDER_CD': ('OIDC', 'SAML'),
        'REASON_CD': ('PRORATION', 'ROUNDING', 'SERVICE'),
        'FLAG_TYPE': ('PII_REVIEW', 'ACCESS', 'RETENTION'),
        'TITLE': ('Finance Manager', 'Client Operations Lead', 'Records Administrator', 'Legal Counsel', 'Project Analyst'),
        'TEAM_NAME': TEAMS,
        'FOLDER_NAME': ('Customer agreements', 'Finance and billing', 'Board governance', 'Project delivery', 'People and policies'),
        'TAG_NAME': ('confidential', 'signed', 'finance', 'review-required', 'approved', 'customer-facing'),
        'COMMENT_TEXT': ('Approved for publication after legal review.', 'Please confirm the revised payment terms.',
                         'Supporting schedules attached for the quarterly close.', 'Version reviewed; no further changes requested.'),
        'POLICY_NAME': ('Financial records - seven years', 'Employee records - six years', 'Customer agreements - ten years'),
        'PREF_NAME': ('notification_digest', 'editor_theme', 'review_reminders'),
        'PREF_VALUE': ('daily', 'system', 'enabled'),
        'REASON_TEXT': ('Preserve supporting evidence for contract review', 'Pending regulatory records request'),
    }
    for column, values in choices.items():
        if column in row:
            row[column] = rng.choice(values)
    if name == 'APP_USER':
        row['DISPLAY_NAME'] = person(rng)
        domain = rng.choice(COMPANY_STARTS).lower() + rng.choice(COMPANY_ENDS)
        row['EMAIL'] = row['DISPLAY_NAME'].lower().replace(' ', '.') + f'.{key}@{domain}.example'
    elif name == 'CUSTOMER_ACCOUNT':
        row.update(ACCOUNT_NAME=company(rng, region), ACCOUNT_NUMBER=f'ACC-{key:07d}', REGION_CD=region[1])
    elif name == 'PLAN_CATALOG':
        index = (key - 1) % len(PLAN_NAMES)
        row.update(PLAN_NAME=PLAN_NAMES[index] + (' - Monthly' if key <= 8 else f' - {region[0]} Edition {1 + (key-1)//8}'),
                   MONTHLY_FEE=PLAN_PRICES[index], CURRENCY_CD='USD' if key <= 2 else region[2])
    elif name == 'TAX_RATE':
        region = REGIONS[(key - 1) % len(REGIONS)]
        row.update(COUNTRY_CD=region[0], REGION_CD=region[1], RATE=region[4])
    elif name == 'INVOICE_HDR':
        rate = float(region[4])
        subtotal = usage_cents(key, seed)
        tax = round(subtotal * rate)
        row.update(INVOICE_NUMBER=f'INV-{business_date.year}-{key:07d}', TAX_RATE_ID=(customer-1) % len(REGIONS)+1,
                   TOTAL_AMOUNT=money(subtotal+tax), SUBTOTAL_AMOUNT=money(subtotal), TAX_AMOUNT=money(tax),
                   INVOICE_PERIOD='0000-00', PERIOD_KEY=0, PRIOR_PERIOD_END_DT='1900-01-01', INVOICE_MONTH=0,
                   PERIOD_CLOSED_CD='N', CURRENCY_CONTROL_TOTAL='0.00')
    elif name == 'INVOICE_LINE':
        amount = usage_cents(row['INVOICE_ID'], seed)
        row.update(LINE_NO=1, DESCRIPTION=rng.choice(('Document processing', 'Signature requests', 'Workflow execution', 'Archive retrieval')),
                   QUANTITY=1, UNIT_PRICE=money(amount), LINE_AMOUNT=money(amount))
    elif name in ('PAYMENT', 'CREDIT_NOTE', 'BILLING_ADJ'):
        invoice = ((key - 1) * 17) % counts['INVOICE_HDR'] + 1
        subscription = (invoice - 1) % counts['SUBSCRIPTION'] + 1
        customer = (subscription - 1) % counts['CUSTOMER_ACCOUNT'] + 1
        gross = round(usage_cents(invoice, seed) * (1 + float(REGIONS[(customer-1) % len(REGIONS)][4])))
        row.update(INVOICE_ID=invoice, CUSTOMER_ID=customer)
        if name == 'PAYMENT':
            row.update(AMOUNT=money(round(gross * rng.choice((1, 1, 1, 0.5, 0.75)))), PAYMENT_REFERENCE=f'PAY-{business_date.year}-{key:09d}')
        elif name == 'CREDIT_NOTE':
            code, reason = rng.choice(CREDIT_REASONS)
            row.update(AMOUNT=money(round(gross * rng.uniform(0.05, 0.35))), REASON_CD=code,
                       CREDIT_NUMBER=f'CRN-{business_date.year}-{key:07d}', REASON_TEXT=reason)
        else:
            row['AMOUNT'] = money(rng.choice((-1, -1, 0, 1)) * rng.randrange(1, 5001))
    elif name == 'DOCUMENT':
        file_type = FILE_TYPES[(key - 1) % len(FILE_TYPES)]
        row.update(DOCUMENT_NAME=f'{rng.choice(DOCUMENT_TOPICS[file_type])} - {business_date.year} Q{(business_date.month-1)//3+1}.{file_type}', FILE_TYPE=file_type)
    elif name == 'FILE_OBJECT':
        row['OBJECT_KEY'] = f'workspaces/{customer}/documents/{row["DOCUMENT_ID"]}/original.{FILE_TYPES[(key-1) % len(FILE_TYPES)]}'
    elif name == 'SSO_IDENTITY':
        row['SUBJECT_ID'] = hashlib.sha256(f'{seed}:identity:{key}'.encode()).hexdigest()[:40]
    elif name in ('AUDIT_EVENT', 'AUDIT_EVENT_ARCHIVE'):
        row['DETAILS'] = f'{row["EVENT_TYPE"]}: document {row["DOCUMENT_ID"]}; access evaluated under workspace policy; client={rng.choice(("web", "desktop", "api"))}'
    elif name == 'GL_ACCOUNT':
        number, title, account_type, balance = CHART[key - 1]
        row.update(GL_ACCOUNT_ID=number, ACCOUNT_NUMBER=str(number), ACCOUNT_NAME=title, ACCOUNT_TYPE=account_type, NORMAL_BALANCE=balance)
    if 'FILE_SIZE' in row:
        row['FILE_SIZE'] = round(rng.lognormvariate(12.2, 1.7))
    if 'BYTES_USED' in row:
        row['BYTES_USED'] = round(rng.lognormvariate(17.5, 1.8))
    if 'RETENTION_DAYS' in row:
        row['RETENTION_DAYS'] = rng.choice((365, 1095, 2190, 2555, 3650))
    return row
