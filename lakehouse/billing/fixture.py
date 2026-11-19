"""Prepare stage-specific billing parity fixtures in the local legacy emulator."""

import argparse
import io
import os
import re
import zlib

from psycopg import sql

from lakehouse.billing.calendar import variables
from lakehouse.orchestration.graph import business_date
from lakehouse.runtime.layout import ROOT, data_root
from warehouse.teradata.bteq import Runner


def prepare(day):
    exports = data_root() / 'parity/legacy/billing' / day
    values = variables(day, exports)
    exports.mkdir(parents=True, exist_ok=True)
    legacy_ns = os.environ.get('LEGACY_NS', 'sfx-d1110-before')
    if not os.environ.get('TD_PG_DSN'):
        os.environ.setdefault('TD_PG_PORT', str(54500 + zlib.crc32(legacy_ns.encode()) % 1000))
    output = io.StringIO()
    with Runner(variables=values, output=output) as runner:
        runner.conn.execute('CREATE SCHEMA IF NOT EXISTS sfx_billing_parity')
        runner.conn.execute('TRUNCATE sfx_billing.gl_journal_line')

        def script(name):
            output.seek(0)
            output.truncate()
            code = runner.run((ROOT.parent / 'warehouse/teradata/scripts/billing' / (name + '.bteq')).read_text())
            print(f'{name}: exit {code}', flush=True)
            if code:
                raise RuntimeError(output.getvalue())

        def snapshot(name, source):
            runner.conn.execute(sql.Composed([sql.SQL('DROP TABLE IF EXISTS '),
                                             sql.Identifier('sfx_billing_parity', name)]))
            runner.conn.execute(sql.Composed([sql.SQL('CREATE TABLE '),
                                             sql.Identifier('sfx_billing_parity', name),
                                             sql.SQL(' AS SELECT * FROM '),
                                             sql.Identifier('sfx_billing', source)]))

        for name in ('load_account_history', '01_load_accounts', '02_load_subscriptions',
                     '03_load_invoices', '04_load_payments', '05_load_usage'):
            script(name)
        for name in ('invoice_hdr', 'invoice_line', 'gl_journal_line'):
            snapshot('load_' + name, name)
        for name in ('10_subscription_report', '11_currency_daily', '12_invoice_monthly',
                     '13_period_close', '14_account_history_extract'):
            script(name)
            if name == '12_invoice_monthly':
                for table in ('invoice_hdr', 'invoice_line', 'gl_journal_line'):
                    snapshot('monthly_' + table, table)
                result = re.findall(r'^n = (\d+)$', output.getvalue(), re.M)
                if len(result) != 1:
                    raise RuntimeError('Expected one captured monthly procedure OUT n')
                runner.conn.execute('DROP TABLE IF EXISTS sfx_billing_parity.monthly_invoice_result')
                runner.conn.execute('CREATE TABLE sfx_billing_parity.monthly_invoice_result (n bigint)')
                runner.conn.execute('INSERT INTO sfx_billing_parity.monthly_invoice_result VALUES (%s)', (int(result[0]),))
    print(f'Billing reporting fixture: PASS ({day}); exports: {exports}', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--business-date', required=True)
    args = parser.parse_args()
    business_date(args.business_date)
    prepare(args.business_date)


if __name__ == '__main__':
    main()
