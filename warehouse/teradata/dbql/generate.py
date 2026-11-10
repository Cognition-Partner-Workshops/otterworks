import argparse
from collections import Counter
import csv
import datetime as dt
from pathlib import Path
import random
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bteq.parser import commands


AS_OF = dt.date(2026, 11, 10)
START = AS_OF - dt.timedelta(days=90)
DENSE_START = AS_OF - dt.timedelta(days=30)
QUIET_OBJECTS = {
    'SFX_AUDIT.AUDIT_EVENT_ARCHIVE', 'SFX_DOCUMENTS.SEARCH_INDEX_LOG', 'SFX_USERS.USER_PREF',
    'SFX_DOCUMENTS.V_SEARCH_HISTORY', 'SFX_USERS.V_USER_SETTINGS', 'SFX_AUDIT.M_ARCHIVE_OVERVIEW',
}
QUERY_COLUMNS = ('ProcID', 'CollectTimeStamp', 'QueryID', 'UserName', 'DefaultDatabase', 'AppID', 'ClientID',
                 'StartTime', 'FirstRespTime', 'StatementType', 'StatementGroup', 'QueryText',
                 'NumResultRows', 'AMPCPUTime', 'TotalIOCount', 'ErrorCode')
OBJECT_COLUMNS = ('QueryID', 'ObjectDatabaseName', 'ObjectTableName', 'ObjectType', 'UsageType')
TABLE_COLUMNS = ('DatabaseName', 'TableName', 'TableKind', 'CreateTimeStamp', 'LastAccessTimeStamp', 'AccessCount')
CLIENTS = {
    'svc_report_recon': ('BTEQ', 'finance-recon-01'),
    'svc_analytics_dash': ('Analytics Dashboard', 'bi-gateway-02'),
    'svc_billing_export': ('BTEQ Export', 'billing-export-01'),
    'svc_legacy_billing': ('JDBC', 'billing-batch-03'),
    'svc_admin_fin': ('SQL Assistant', 'finance-admin-02'),
    'svc_bi_semantic': ('BI Semantic Service', 'semantic-model-01'),
    'nb_dsci_pkhan': ('JupyterLab/python', 'notebook-finops-02'),
    'svc_partner_sftp': ('SFTP Export', 'sftp.partner-feed.example'),
    'FIN_ANALYST_JMORALES': ('ODBC', 'Microsoft Excel; workstation=FIN-WS-014'),
    **{f'svc_etl_{area}': ('BTEQ', f'etl-{area}-01') for area in ('billing', 'docs', 'users', 'audit')},
    'svc_fastload': ('FastLoad', 'landing-loader-01'),
}
REPORTS = {
    'svc_report_recon': (
        'SELECT BUSINESS_DT, SUM(DIFFERENCE_COUNT) AS DIFFERENCE_COUNT FROM SFX_AUDIT.AUDIT_RECON GROUP BY BUSINESS_DT;',
        'SELECT COUNT(*) AS INVOICE_COUNT, SUM(TOTAL_AMOUNT) AS TOTAL_AMOUNT FROM SFX_BILLING.INVOICE_HDR;',
    ),
    'svc_analytics_dash': (
        'SELECT CURRENCY_CD, INVOICE_PERIOD, TOTAL_AMOUNT FROM SFX_BILLING.V_INVOICE_REVENUE;',
        'SELECT TEAM_NAME, COUNT(*) AS MEMBER_COUNT FROM SFX_USERS.V_TEAM_MEMBERS GROUP BY TEAM_NAME;',
        'SELECT OWNER_USER_ID, DOCUMENT_COUNT, TOTAL_BYTES FROM SFX_DOCUMENTS.V_WORKSPACE_STORAGE;',
    ),
    'svc_billing_export': (
        "SELECT INVOICE_NUMBER, CUSTOMER_ID, CURRENCY_CD, TOTAL_AMOUNT FROM SFX_BILLING.INVOICE_HDR WHERE BILL_DT<=DATE '${DAY}';",
        "SELECT PAYMENT_REFERENCE, INVOICE_ID, AMOUNT FROM SFX_BILLING.PAYMENT WHERE PAYMENT_DT=DATE '${DAY}';",
    ),
    'svc_legacy_billing': (
        'SELECT CUSTOMER_ID, ACCOUNT_NAME, INVOICE_ID, TOTAL_AMOUNT FROM SFX_BILLING.V_ACCOUNT_INVOICES;',
    ),
    'svc_admin_fin': (
        'SELECT GL_ACCOUNT_ID, CURRENCY_CD, SUM(DEBIT_AMOUNT-CREDIT_AMOUNT) AS BALANCE FROM SFX_BILLING.GL_JOURNAL_LINE GROUP BY GL_ACCOUNT_ID, CURRENCY_CD;',
        'SELECT REASON_CD, SUM(AMOUNT) AS CREDIT_AMOUNT FROM SFX_BILLING.CREDIT_NOTE GROUP BY REASON_CD;',
    ),
    'svc_bi_semantic': (
        'SELECT INVOICE_PERIOD, CURRENCY_CD, INVOICE_COUNT, TOTAL_AMOUNT FROM SFX_BILLING.V_INVOICE_REVENUE;',
        'SELECT TEAM_NAME, DISPLAY_NAME FROM SFX_USERS.V_TEAM_MEMBERS;',
    ),
    'nb_dsci_pkhan': (
        'SELECT METHOD_CD, COUNT(*) AS PAYMENT_COUNT, AVG(AMOUNT) AS AVG_AMOUNT FROM SFX_BILLING.PAYMENT GROUP BY METHOD_CD;',
        'SELECT EVENT_TYPE, COUNT(*) AS EVENT_COUNT FROM SFX_AUDIT.V_EVENT_ACTORS GROUP BY EVENT_TYPE;',
    ),
    'svc_partner_sftp': (
        "SELECT h.INVOICE_NUMBER, b.ACCOUNT_NAME, h.CURRENCY_CD, h.TOTAL_AMOUNT FROM SFX_BILLING.V_INVOICE_BASE b JOIN SFX_BILLING.INVOICE_HDR h ON b.INVOICE_ID=h.INVOICE_ID WHERE h.BILL_DT=DATE '${DAY}';",
        "SELECT PAYMENT_REFERENCE, INVOICE_ID, AMOUNT, METHOD_CD FROM SFX_BILLING.PAYMENT WHERE PAYMENT_DT=DATE '${DAY}';",
    ),
    'FIN_ANALYST_JMORALES': (
        'SELECT INVOICE_PERIOD, CURRENCY_CD, SUM(TOTAL_AMOUNT) AS INVOICED_AMOUNT FROM SFX_BILLING.INVOICE_HDR GROUP BY INVOICE_PERIOD, CURRENCY_CD;',
        'SELECT a.ACCOUNT_NUMBER, a.ACCOUNT_NAME, j.CURRENCY_CD, SUM(j.DEBIT_AMOUNT) AS DEBITS, SUM(j.CREDIT_AMOUNT) AS CREDITS FROM SFX_BILLING.GL_JOURNAL_LINE j JOIN SFX_BILLING.GL_ACCOUNT a ON j.GL_ACCOUNT_ID=a.GL_ACCOUNT_ID GROUP BY a.ACCOUNT_NUMBER, a.ACCOUNT_NAME, j.CURRENCY_CD;',
    ),
}


def inventory(root=ROOT):
    result = {}
    paths = sorted((root / 'ddl').glob('*/*.sql'))
    paths += sorted((root / 'macros').glob('*.sql')) + sorted((root / 'procedures').glob('*.sql'))
    paths.append(root / 'dbql' / 'schema.sql')
    for path in paths:
        for statement in commands(path.read_text()):
            match = re.match(r'(?:CREATE|REPLACE)\s+(?:(?:SET|MULTISET)\s+)?(TABLE|VIEW|MACRO|PROCEDURE)\s+([\w.]+)', statement, re.I)
            if match:
                result[match[2].upper()] = (dict(TABLE='T', VIEW='V', MACRO='M', PROCEDURE='P')[match[1].upper()], statement)
    return dict(sorted(result.items()))


def references(statement, objects):
    direct = {m.upper() for m in re.findall(r'\b(?:FROM|JOIN|INTO|UPDATE|CALL|EXEC)\s+((?:SFX_\w+|DBC)\.\w+)', statement, re.I)}
    found, pending = set(), list(direct & objects.keys())
    while pending:
        name = pending.pop()
        if name in found:
            continue
        found.add(name)
        kind, definition = objects[name]
        if kind != 'T':
            dependencies = {m.upper() for m in re.findall(r'\b(?:FROM|JOIN|INTO|UPDATE|CALL|EXEC)\s+((?:SFX_\w+|DBC)\.\w+)', definition, re.I)}
            pending.extend((dependencies & objects.keys()) - found)
    return found


def expand(statement, day):
    first = day.replace(day=1)
    previous_end = first - dt.timedelta(days=1)
    next_month = (first + dt.timedelta(days=32)).replace(day=1)
    encode = lambda d: str((d.year-1900)*10000+d.month*100+d.day)
    values = {'DAY': day.isoformat(), 'BUSINESS_DATE': day.strftime('%Y%m%d'),
              'MONTH_START': first.strftime('%Y%m%d'), 'MONTH_END': next_month.strftime('%Y%m%d'),
              'PERIOD_START_INT': encode(previous_end.replace(day=1)), 'PERIOD_END_INT': encode(previous_end)}
    return re.sub(r'\$\{(\w+)\}', lambda m: values[m[1]], re.sub(r'\s+', ' ', statement).strip())


def generate(out=Path(__file__).parent, seed=1110):
    rng, objects, events = random.Random(seed), inventory(), []

    def add(user, day, hour, minute, query, error=0):
        start = dt.datetime.combine(day, dt.time(hour, minute, rng.randrange(60)))
        events.append((start, user, expand(query, day), error))

    loads = []
    for path in sorted((ROOT / 'scripts').glob('*/0*.bteq')):
        user = 'svc_etl_' + ('docs' if path.parent.name == 'documents' else path.parent.name)
        for statement in commands(path.read_text()):
            if re.match(r'(INSERT|MERGE)\b', statement, re.I):
                loads.append((user, statement))
    fastloads = [next(q for q in commands(p.read_text()) if q.upper().startswith('INSERT INTO'))
                 for p in sorted((ROOT / 'load' / 'fastload').glob('*.fl'))]
    routines = [(name, kind) for name, (kind, _) in objects.items() if kind in ('M', 'P') and name not in QUIET_OBJECTS]
    for index in range(90):
        day = START + dt.timedelta(days=index)
        for offset, (user, query) in enumerate(loads):
            add(user, day, 1 + offset//60, offset % 60, query)
        for offset in range(5):
            add('svc_fastload', day, 0, offset*9, fastloads[(index*5+offset) % len(fastloads)])
        for offset, (name, kind) in enumerate(routines):
            user = 'svc_etl_' + {'SFX_BILLING': 'billing', 'SFX_DOCUMENTS': 'docs', 'SFX_USERS': 'users', 'SFX_AUDIT': 'audit'}[name.split('.')[0]]
            args = "CAST('${MONTH_START}' AS DATE FORMAT 'YYYYMMDD'), CAST('${MONTH_END}' AS DATE FORMAT 'YYYYMMDD')" if name.endswith('M_STORAGE_TOTALS') else "'${BUSINESS_DATE}'" + (', ?' if kind == 'P' else '')
            add(user, day, 3, offset*3, ('CALL ' if kind == 'P' else 'EXEC ') + name + '(' + args + ');')
        for area in ('billing', 'docs', 'users', 'audit'):
            table = {'billing': 'SFX_BILLING.INVOICE_HDR', 'docs': 'SFX_DOCUMENTS.DOCUMENT', 'users': 'SFX_USERS.APP_USER', 'audit': 'SFX_AUDIT.AUDIT_EVENT'}[area]
            add('svc_etl_'+area, day, 4, 5, 'SELECT COUNT(*) AS ROW_COUNT FROM '+table+';')
        dense = day >= DENSE_START
        for user, queries in REPORTS.items():
            if user in ('svc_billing_export', 'svc_partner_sftp', 'svc_legacy_billing'):
                hours = (5,)
            elif user == 'svc_analytics_dash':
                hours = range(6, 23) if dense else (12,)
            elif not dense and day.weekday() != 0:
                continue
            elif day.weekday() >= 5:
                continue
            elif user == 'svc_bi_semantic':
                hours = range(8, 19, 2) if dense else (8,)
            elif user == 'nb_dsci_pkhan':
                hours = (10, 14) if day.weekday() in (1, 3) else ()
            elif user == 'FIN_ANALYST_JMORALES':
                hours = (9, 11, 14, 16)
            else:
                hours = (8, 15)
            for hour in hours:
                for offset, query in enumerate(queries):
                    add(user, day, hour, 10 + offset*7 + rng.randrange(5), query)
        if index % 10 == 0:
            add('svc_legacy_billing', day, 5, 58, 'SELECT * FROM SFX_BILLING.INVOICE_EXPORT_QUEUE;', 3807)
        if index % 13 == 0:
            add('svc_admin_fin', day, 15, 55, 'SELECT CAST(SUM(TOTAL_AMOUNT) AS DECIMAL(5,2)) FROM SFX_BILLING.INVOICE_HDR;', 2616)

    covered = set().union(*(references(query, objects) for _, _, query, _ in events))
    for offset, name in enumerate(sorted(objects.keys() - covered - QUIET_OBJECTS)):
        add('svc_report_recon', START, 6, offset % 60, 'SELECT COUNT(*) AS ROW_COUNT FROM '+name+';')

    query_rows, object_rows, access, last = [], [], Counter(), {}
    for index, (start, user, query, error) in enumerate(sorted(events)):
        query_id = 111000000000 + index
        touched = references(query, objects)
        if touched & QUIET_OBJECTS:
            raise ValueError('Unexpected object reference: '+str(touched & QUIET_OBJECTS))
        statement_type = query.split()[0].upper()
        io_count = rng.randrange(20, 250000)
        cpu = rng.uniform(0.002, 3.5) * (3 if statement_type in ('INSERT', 'MERGE', 'CALL') else 1)
        first = start + dt.timedelta(milliseconds=rng.randrange(30, 1800)+int(cpu*100))
        database = next(iter(sorted(touched))).split('.')[0] if touched else 'SFX_BILLING'
        app, client = CLIENTS[user]
        query_rows.append((rng.randrange(100, 108), first+dt.timedelta(seconds=1), query_id, user, database,
                           app, client, start, first, statement_type,
                           'SELECT' if statement_type == 'SELECT' else ('UTILITY' if user == 'svc_fastload' else 'ETL'),
                           query, 0 if error else (1 if 'COUNT(*)' in query else rng.randrange(10, 20001)),
                           f'{cpu:.6f}', io_count, error))
        target = re.match(r'(?:INSERT INTO|MERGE INTO|UPDATE|DELETE FROM)\s+([\w.]+)', query, re.I)
        for name in sorted(touched):
            kind = objects[name][0]
            usage = 'EXECUTE' if kind in ('M', 'P') else ('WRITE' if target and target[1].upper() == name else 'READ')
            object_rows.append((query_id, *name.split('.'), kind, usage))
            access[name] += 1
            last[name] = start
    table_rows = [(*name.split('.'), kind, '2021-04-12 09:00:00', last.get(name, '2026-07-01 17:30:00'), access[name])
                  for name, (kind, _) in objects.items()]
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    result = {}
    for filename, columns, rows in [('qrylog.csv', QUERY_COLUMNS, query_rows),
                                    ('objectusage.csv', OBJECT_COLUMNS, object_rows), ('tablesv.csv', TABLE_COLUMNS, table_rows)]:
        with (out / filename).open('w', newline='', encoding='utf-8') as handle:
            writer = csv.writer(handle, lineterminator='\n')
            writer.writerow(columns)
            writer.writerows(rows)
        result[filename] = len(rows)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=Path(__file__).parent)
    parser.add_argument('--seed', type=int, default=1110)
    args = parser.parse_args()
    for name, count in generate(args.out, args.seed).items():
        print(f'{name}: {count} rows, {(args.out/name).stat().st_size} bytes')


if __name__ == '__main__':
    main()
