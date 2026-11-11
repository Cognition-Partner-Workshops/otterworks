"""Render additive seed reconciliation without rewriting applied migrations."""
from pathlib import Path
import re
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from seed_contract import seed_spec

TARGET = ROOT / 'migrations/V007__shared_seed.sql'
ALIASES = {'CUSTOMER_ACCOUNT_ID': 'CUSTOMER_ID', 'LEGAL_NAME': 'ACCOUNT_NAME',
           'BILLING_COUNTRY': 'COUNTRY_CD', 'CURRENCY_CODE': 'CURRENCY_CD',
           'CREATED_AT': 'CREATED_DT', 'INVOICE_HDR_ID': 'INVOICE_ID',
           'INVOICE_DATE': 'INVOICE_DT', 'PAYMENT_NUMBER': 'PAYMENT_REFERENCE',
           'PAYMENT_DATE': 'PAYMENT_DT', 'METHOD': 'METHOD_CD',
           'GL_JOURNAL_LINE_ID': 'JOURNAL_LINE_ID', 'POSTING_DATE': 'POSTING_DT'}


def render():
    fixture = yaml.safe_load((ROOT / 'fixture_columns.yml').read_text())
    merged = yaml.safe_load((ROOT / 'fixture_columns.yml').read_text())
    seed = seed_spec()
    statements = []
    for area, tables in seed.items():
        for table, columns in tables.items():
            relation = f'RAW_{area.upper()}.{table}'
            for name, kind in columns.items():
                if (area, table, name) == ('users', 'APP_USER', 'DISPLAY_NAME'):
                    kind = 'VARCHAR(256)'
                old = merged[area][table].get(name)
                if old is None:
                    statements.append(f"ALTER TABLE {relation} ADD COLUMN IF NOT EXISTS {name} {kind} COMMENT 'sfx-d1110 shared seed';")
                    merged[area][table][name] = kind
                elif old != kind:
                    before, after = re.fullmatch(r'VARCHAR\((\d+)\)', old), re.fullmatch(r'VARCHAR\((\d+)\)', kind)
                    widen = before and after and int(after[1]) > int(before[1])
                    if widen or (old == 'NUMBER(8,4)' and kind == 'NUMBER(12,4)'):
                        statements.append(f'ALTER TABLE {relation} ALTER COLUMN {name} SET DATA TYPE {kind};')
                        merged[area][table][name] = kind
    views = {'CUSTOMER': 'CUSTOMER_ACCOUNT', 'ACCOUNT': 'CUSTOMER_ACCOUNT',
             'INVOICE': 'INVOICE_HDR', 'INVOICE_LINE': 'INVOICE_LINE',
             'PAYMENT': 'PAYMENT', 'GL_JOURNAL_LINE': 'GL_JOURNAL_LINE', 'GL_ACCOUNT': 'GL_ACCOUNT'}
    for view, table in views.items():
        selections = []
        for name in fixture['billing'][table]:
            alias = ALIASES.get(name)
            selections.append(f'    COALESCE(r.{name}, r.{alias}) AS {name}' if alias in seed['billing'][table]
                              else f'    r.{name}')
        selections += [f'    r.{name}' for name in seed['billing'][table] if name not in fixture['billing'][table]]
        join = ''
        if view == 'CUSTOMER':
            selections += ['    u.FIRST_NAME AS OWNER_FIRST_NAME', '    u.LAST_NAME AS OWNER_LAST_NAME',
                           '    u.EMAIL AS OWNER_EMAIL', '    u.DISPLAY_NAME AS OWNER_DISPLAY_NAME']
            join = '\nLEFT JOIN RAW_USERS.APP_USER u ON r.OWNER_USER_ID = u.USER_ID'
        statements.append(f"CREATE OR REPLACE VIEW COMPAT.{view} COMMENT='sfx-d1110 seed compatibility projection'\nAS SELECT\n"
                          + ',\n'.join(selections) + f'\nFROM RAW_BILLING.{table} r' + join + ';')
    statements.append("""CREATE OR REPLACE VIEW COMPAT.DAILY_USAGE COMMENT='sfx-d1110 seeded daily usage rollup'
AS SELECT r.CUSTOMER_ID, COALESCE(r.USAGE_DATE, r.USAGE_DT) AS USAGE_DATE,
    COALESCE(r.CURRENCY_CODE, c.CURRENCY_CD) AS CURRENCY_CODE,
    SUM(COALESCE(r.QUANTITY, r.UNITS)) AS QUANTITY, SUM(r.AMOUNT) AS AMOUNT,
    COALESCE(r.USAGE_DATE, r.USAGE_DT) AS USAGE_DT, SUM(COALESCE(r.UNITS, r.QUANTITY)) AS UNITS
FROM RAW_BILLING.USAGE_DAILY r
LEFT JOIN RAW_BILLING.CUSTOMER_ACCOUNT c ON r.CUSTOMER_ID = c.CUSTOMER_ID
GROUP BY r.CUSTOMER_ID, COALESCE(r.USAGE_DATE, r.USAGE_DT), COALESCE(r.CURRENCY_CODE, c.CURRENCY_CD);""")
    for view, source in (('CUSTOMER_ACCOUNT', 'ACCOUNT'), ('INVOICE_HDR', 'INVOICE')):
        statements.append(f"CREATE OR REPLACE VIEW COMPAT.{view} COMMENT='sfx-d1110 shared seed object name' AS SELECT * FROM COMPAT.{source};")
    for view in [*views, 'DAILY_USAGE', 'CUSTOMER_ACCOUNT', 'INVOICE_HDR']:
        statements.append(f"ALTER VIEW COMPAT.{view} SET TAG GOVERNANCE.SFX_RUN = 'sfx-d1110';")
    statements.append('GRANT SELECT ON ALL VIEWS IN SCHEMA COMPAT TO ROLE SFX_D1110_ROLE;')
    return merged, '\n\n'.join(statements) + '\n'


if __name__ == '__main__':
    merged, sql = render()
    (ROOT / 'landing_columns.yml').write_text('# Additive RAW superset of fixture_columns.yml and warehouse/seed/columns.py.\n' + yaml.safe_dump(merged, sort_keys=False))
    TARGET.write_text(sql)
