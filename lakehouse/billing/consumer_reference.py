"""Execute untouched consumer SQL through the repository's legacy emulator."""

import argparse
import ast
import csv
import io
import hashlib
import json
import os
import subprocess
from dataclasses import asdict, dataclass, fields
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile

from lakehouse.billing.consumer_exports import atomic_bytes, comparison_rows, json_lines
from lakehouse.billing.consumer_queries import SOURCES, bound_query, dates
from lakehouse.runtime.layout import ROOT, data_root
from warehouse.teradata.bteq import Runner


def legacy_rows(runner, name, day, clock=None, **parameters):
    runner.execute(bound_query(name, day, clock, **parameters))
    if runner.errorcode:
        raise RuntimeError(f'{name}: {runner.errorcode}: {runner.output.getvalue()}')
    return [dict(zip([h.lower() for h in runner.headers], values)) for values in runner.rows]


def source_invoice_export(rows, path):
    source = ast.parse((ROOT.parent / SOURCES['billing_invoices']).read_text())
    maximum = next(ast.literal_eval(n.value) for n in source.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'MAX_INVOICES' for t in n.targets))
    if len(rows) > maximum:
        raise RuntimeError('Invoice export exceeds legacy limit')
    dto = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == 'InvoiceExportRow')
    exporter = ast.parse((ROOT.parent / 'services/billing-service/app/export_invoices.py').read_text())
    function = next(n for n in exporter.body if isinstance(n, ast.FunctionDef) and n.name == 'export_invoices')
    future = ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)
    namespace = dict(globals())
    # Only the named DTO and exporter ASTs from fixed, read-only repository sources execute.
    # nosemgrep: python.lang.security.audit.exec-detected.exec-detected
    exec(compile(ast.fix_missing_locations(ast.Module(body=[future, dto, function], type_ignores=[])),
                 '<unchanged-billing-export>', 'exec'), namespace)
    parsed = [namespace['InvoiceExportRow'].from_values(tuple(row.values())) for row in rows]

    class Warehouse:
        def invoices_for_run(self, run_date):
            return parsed

    namespace['export_invoices'](Warehouse(), None, path)


def prepare(day, clock=None):
    business, today = dates(day, clock)
    root = data_root() / 'parity/legacy/billing_consumers' / day
    root.mkdir(parents=True, exist_ok=True)
    with Runner(output=io.StringIO()) as runner:
        provenance = dict(business_date=business.isoformat(), clock=today.isoformat(), sources={})
        for name in SOURCES:
            rows = legacy_rows(runner, name, day, clock)
            if name == 'partner_rows':
                raw = ''.join((row['report_row'] or '') + '\n' for row in rows)
                atomic_bytes(root / 'raw.csv', raw.encode())
                filename = 'partner-invoices-' + day + '.csv'
                output = root / filename
                subprocess.run(['bash', str(ROOT.parent / 'consumers/partner-extract/bin/postprocess.sh'),
                                str(root / 'raw.csv'), str(output)], check=True)
                environment = {**os.environ, 'SFTP_DRY_RUN': '1', 'SFTP_REMOTE_DIR': '/incoming',
                               'SFTP_KEY_PATH': '/fake/keys/partner_sftp'}
                transfer = subprocess.run(['bash', str(ROOT.parent / 'consumers/partner-extract/bin/sftp_push.sh'),
                                           str(output)], env=environment, check=True, capture_output=True, text=True)
                if 'put "' + str(output) + '" "/incoming/' + filename + '"' not in transfer.stdout:
                    raise RuntimeError('Native simulated transfer did not select the published CSV')
                atomic_bytes(root / 'transfer.json', json.dumps(dict(mode='simulated', destination='/incoming/' + filename,
                             sha256=hashlib.sha256(output.read_bytes()).hexdigest(), bytes=output.stat().st_size), sort_keys=True).encode())
            else:
                atomic_bytes(root / (name + '.jsonl'), json_lines(comparison_rows(rows)))
                if name == 'billing_invoices':
                    source_invoice_export(rows, root / 'invoices.csv')
            provenance['sources'][SOURCES[name]] = hashlib.sha256((ROOT.parent / SOURCES[name]).read_bytes()).hexdigest()
            print('legacy.' + name + ': ' + str(len(rows)), flush=True)
    source = data_root() / 'parity/legacy/billing' / day / ('account_status_' + day + '.psv')
    typed, groups = [], {}
    with source.open(newline='') as handle:
        for row in csv.reader(handle, delimiter='|'):
            day_value, status, currency, count = row
            typed.append(dict(business_date=date.fromisoformat(day_value).isoformat(), account_status=status or None,
                              currency_code=currency or None, account_count=int(count)))
            key = (status or None, currency or None)
            groups[key] = groups.get(key, 0) + int(count)
    atomic_bytes(root / 'account_status.jsonl', json_lines(comparison_rows(typed)))
    atomic_bytes(root / 'workbook_feed.jsonl', json_lines(comparison_rows([
        dict(account_status=k[0], currency_code=k[1], account_count=v) for k, v in groups.items()])))
    atomic_bytes(root / 'provenance.json', json.dumps(provenance, indent=2).encode())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--business-date', required=True)
    parser.add_argument('--clock-date')
    args = parser.parse_args()
    prepare(args.business_date, args.clock_date)


if __name__ == '__main__':
    main()
