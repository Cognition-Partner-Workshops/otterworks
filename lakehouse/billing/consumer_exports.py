"""Lakehouse-side consumer files; no service or legacy-source mutations."""

import argparse
import csv
import fcntl
import hashlib
import io
import json
import os
import re
import tempfile
import uuid
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from lakehouse.billing.consumer_queries import SOURCES, dates, query
from lakehouse.runtime.layout import data_root
from lakehouse.runtime.session import create_session


HEADER = 'invoice_no,account_no,invoice_date,amount_due,tax_amt,open_balance,currency'
INVOICE_COLUMNS = ('invoice_no', 'customer_name', 'account_no', 'invoice_date', 'currency_cd',
                   'amount_due', 'tax_amt', 'open_balance')
NUMERIC = set('amount_due tax_amt open_balance total_amount paid current_amt days_1_30 days_31_60 days_61_90 '
              'days_over_90 open_ratio ar_open_balance collections_30_days dso overdue_balance billed_revenue '
              'collected_cash active_accounts period_id invoiced_total paid_total ar_gl_balance variance days_overdue '
              'account_count'.split())
CASEFOLD = {'currency_cd', 'account_status', 'currency_code'}


def atomic_bytes(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.' + path.name, delete=False) as handle:
            temporary = Path(handle.name)
            os.chmod(temporary, 0o600)
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def partner_csv(raw):
    result, seen, total = [HEADER], set(), Decimal(0)
    for line in raw.splitlines():
        if not line.strip():
            continue
        fields = [s.strip(' \t\r\n\v\f') for s in line.split(',')]
        if len(fields) != 7:
            raise ValueError('Invalid partner field count')
        invoice, account, issued, *_, currency = fields
        if not (re.fullmatch(r'INV-[A-Za-z0-9-]+', invoice) and
                re.fullmatch(r'(A[0-9]+|ACC-[0-9]+)', account) and
                re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', issued) and
                re.fullmatch(r'[A-Z]{3}', currency)) or invoice in seen:
            raise ValueError('Invalid or duplicate partner identity')
        seen.add(invoice)
        for i in range(3, 6):
            if not re.fullmatch(r'-?[0-9]*\.[0-9][0-9]', fields[i]):
                raise ValueError('Malformed partner money')
            amount = Decimal(fields[i])
            if abs(amount * 100) > 9000000000000:
                raise ValueError('Partner money exceeds limit')
            if i == 3:
                total += amount
            fields[i] = format(amount, '.2f')
        if abs(total * 100) > 9000000000000:
            raise ValueError('Partner total exceeds limit')
        result.append(','.join(fields))
    result.append(f'TRAILER,{len(seen)},{total if total else Decimal(0):.2f}')
    return ('\n'.join(result) + '\n').encode()


def transfer_receipt(payload, filename, remote='/incoming', dry_run=True):
    if not dry_run:
        raise ValueError('Live SFTP is not implemented')
    if any(c in remote + filename for c in '"\\\r\n'):
        raise ValueError('Unsafe SFTP path')
    return dict(mode='simulated', destination=remote + '/' + filename,
                sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload))


def publish_partner(raw, root, day, remote='/incoming', dry_run=True):
    business, _ = dates(day)
    filename = 'partner-invoices-' + day + '.csv'
    payload = partner_csv(raw)
    receipt = transfer_receipt(payload, filename, remote, dry_run)
    version = root / 'versions' / uuid.uuid4().hex
    atomic_bytes(version / 'raw.csv', raw.encode())
    atomic_bytes(version / filename, payload)
    atomic_bytes(version / 'transfer.json', json.dumps(receipt, sort_keys=True).encode())
    link = root / 'next'
    link.unlink(missing_ok=True)
    link.symlink_to(version.relative_to(root), target_is_directory=True)
    os.replace(link, root / 'current')
    return root / 'current'


def invoice_csv(rows):
    if len(rows) > 100000:
        raise ValueError('Invoice export exceeds 100000 rows')
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(INVOICE_COLUMNS)
    for row in rows:
        values = [row[k] for k in INVOICE_COLUMNS]
        values[0:3] = [str(v) for v in values[0:3]]
        values[2] = values[2].strip()
        values[3] = date.fromisoformat(str(values[3]).strip())
        values[4] = str(values[4]).strip()
        values[5:] = [Decimal(str(v).strip()) for v in values[5:]]
        writer.writerow(values)
    return stream.getvalue().encode()


def workbook_rows(path):
    rows = []
    with Path(path).open(newline='', encoding='utf-8') as handle:
        for values in csv.reader(handle, delimiter='|'):
            if len(values) != 4:
                raise ValueError('Account status requires four columns')
            business, status, currency, count = values
            number = int(count)
            if not -(2 ** 63) <= number < 2 ** 63:
                raise ValueError('AccountCount exceeds Int64')
            rows.append(dict(business_date=date.fromisoformat(business).isoformat(),
                             account_status=status or None, currency_code=currency or None, account_count=number))
    return rows


def json_lines(rows):
    return ''.join(json.dumps(row, default=str, sort_keys=True) + '\n' for row in rows).encode()


def comparison_rows(rows):
    def key(row):
        values = {}
        for name, value in row.items():
            if value is not None and name in NUMERIC:
                number = Decimal(str(value).strip()).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
                value = str(number if number else Decimal(0))
            elif value is not None:
                value = str(value).rstrip()
                if name in CASEFOLD:
                    value = value.casefold()
            values[name] = value
        return json.dumps(values, sort_keys=True)
    return [dict(row, parity_row=i) for i, row in enumerate(sorted(rows, key=key), 1)]


def export(spark, day, clock=None, partner_only=False):
    dates(day, clock)
    publication = data_root() / 'exports/billing_consumers' / day
    root = publication / 'versions' / uuid.uuid4().hex
    for name in ('partner_rows',) if partner_only else SOURCES:
        frame = query(spark, name, day, clock)
        rows = [dict(zip([c.lower() for c in frame.columns], row)) for row in frame.collect()]
        if name == 'partner_rows':
            raw = ''.join((r['report_row'] or '') + '\n' for r in rows)
            publish_partner(raw, data_root() / 'exports/billing_partner' / day, day)
        else:
            atomic_bytes(root / 'queries' / (name + '.jsonl'), json_lines(comparison_rows(rows)))
            if name == 'billing_invoices':
                atomic_bytes(root / 'invoices.csv', invoice_csv(rows))
        print(name + ': PUBLISHED', flush=True)
    if partner_only:
        return
    typed = workbook_rows(data_root() / 'exports/billing' / day / ('account_status_' + day + '.psv'))
    atomic_bytes(root / 'account_status.jsonl', json_lines(comparison_rows(typed)))
    pivot = {}
    for row in typed:
        key = (row['account_status'], row['currency_code'])
        pivot[key] = pivot.get(key, 0) + row['account_count']
    atomic_bytes(root / 'workbook_feed.jsonl', json_lines(comparison_rows([
        dict(account_status=k[0], currency_code=k[1], account_count=v) for k, v in pivot.items()])))
    link = publication / 'next'
    link.unlink(missing_ok=True)
    link.symlink_to(root.relative_to(publication), target_is_directory=True)
    os.replace(link, publication / 'current')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--business-date', required=True)
    parser.add_argument('--clock-date')
    parser.add_argument('--partner-only', action='store_true')
    args = parser.parse_args()
    with (data_root() / 'billing-consumers.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        spark = create_session()
        try:
            export(spark, args.business_date, args.clock_date, args.partner_only)
        finally:
            spark.stop()


if __name__ == '__main__':
    main()
