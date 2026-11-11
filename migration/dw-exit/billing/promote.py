"""Verify billing objects in the shared control schema after fresh live parity."""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SQL = Path(__file__).resolve().parent
sys.path.insert(0, str(SQL.parent))
from parity.connection import COMMENT, connect
from parity.ladder import Ladder, assert_parity

CONTROL = 'SFX_D1110_AFTER.MIGRATION_CONTROL.OBJECTS'
ROUTINES = {
    'M_SUBSCRIPTION_PLANS': 'DESC PROCEDURE SFX_D1110_AFTER.BILLING.M_SUBSCRIPTION_PLANS(VARCHAR)',
    'M_CURRENCY_TOTALS': 'DESC PROCEDURE SFX_D1110_AFTER.BILLING.M_CURRENCY_TOTALS(VARCHAR)',
    'P_MONTHLY_INVOICE': 'DESC PROCEDURE SFX_D1110_AFTER.BILLING.P_MONTHLY_INVOICE(VARCHAR)',
}
READ_CONTROL = """SELECT OBJECT_NAME,OBJECT_TYPE,MIGRATION_STATUS,PARITY_STATUS
    FROM SFX_D1110_AFTER.MIGRATION_CONTROL.OBJECTS
    WHERE SUBJECT_AREA='billing' ORDER BY OBJECT_TYPE,OBJECT_NAME"""


def inventory_objects():
    tables = re.findall(r'CREATE OR REPLACE TABLE SFX_D1110_AFTER.BILLING.(\w+)', (SQL / '00_tables.sql').read_text())
    views = re.findall(r'CREATE OR REPLACE VIEW SFX_D1110_AFTER.BILLING.(\w+)', (SQL / '30_views.sql').read_text())
    objects = [('table', 'SFX_BILLING.' + name, 'warehouse/teradata/ddl/billing/00_tables.sql',
                'SFX_D1110_AFTER.BILLING.' + name) for name in tables]
    for name in views:
        file = '20_views.sql' if name in ('V_INVOICE_BASE', 'V_INVOICE_REVENUE') else '10_views.sql'
        objects.append(('view', 'SFX_BILLING.' + name, 'warehouse/teradata/ddl/billing/' + file,
                        'SFX_D1110_AFTER.BILLING.' + name))
    for name, kind, source in (
        ('M_SUBSCRIPTION_PLANS', 'macro', 'macros/subscription_plans.sql'),
        ('M_CURRENCY_TOTALS', 'macro', 'macros/currency_totals.sql'),
        ('P_MONTHLY_INVOICE', 'procedure', 'procedures/monthly_invoice.sql'),
    ):
        objects.append((kind, 'SFX_BILLING.' + name, 'warehouse/teradata/' + source,
                        'SFX_D1110_AFTER.BILLING.' + name))
    for path in sorted((ROOT / 'warehouse/teradata/scripts/billing').glob('*.bteq')):
        objects.append(('bteq', path.stem, str(path.relative_to(ROOT)),
                        'migration/dw-exit/billing/' + ('10_load.sql' if path.stem[:2] <= '05' else
                        '40_close.sql' if path.stem.startswith('13') else '20_routines.sql')))
    for name, source in (
        ('M_SUBSCRIPTION_PLANS_OUTPUT', 'macros/subscription_plans.sql'),
        ('M_CURRENCY_TOTALS_OUTPUT', 'macros/currency_totals.sql'),
        ('INVOICE_PERIODS', 'scripts/billing/13_period_close.bteq'),
        ('PERIOD_CLOSE', 'scripts/billing/13_period_close.bteq'),
    ):
        objects.append(('table', 'SFX_BILLING.' + name, 'warehouse/teradata/' + source,
                        'SFX_D1110_AFTER.BILLING.' + name))
    return objects


def verify_routines(cursor):
    evidence = []
    for name, describe in ROUTINES.items():
        cursor.execute(describe)
        evidence.append({'routine': name, 'query_id': cursor.sfqid})
    return evidence


def read_control(cursor):
    cursor.execute(READ_CONTROL)
    return cursor.fetchall()


def promote(output):
    manifest = json.loads((SQL.parent / 'parity/billing.json').read_text())
    objects = inventory_objects()
    base_tables = {name.split('.')[-1][4:] for kind, name, _, _ in objects
                   if kind == 'table' and name.split('.')[-1].startswith('STG_')}
    with connect('migration_control_verify') as sf:
        with sf.cursor() as cursor:
            routines = verify_routines(cursor)
        ladder = Ladder(sf)
        results = [ladder.compare(**entry) for entry in manifest]
        assert_parity(results)
        inputs = []
        for entry in manifest:
            name = entry['name']
            if name in base_tables:
                inputs.append(ladder.compare('STG_' + name,
                    'SFX_D1110_AFTER.TD_BASELINE.STG_' + name,
                    'SFX_D1110_AFTER.BILLING.STG_' + name, entry['keys']))
        assert_parity(inputs)
        evidence = json.dumps({'billing_relations': len(results), 'input_relations': len(inputs),
                               'routines': routines,
                               'parity_query_ids': [q['query_id'] for r in results + inputs for q in r['queries']]})
        with sf.cursor() as cursor:
            cursor.execute('CREATE SCHEMA IF NOT EXISTS SFX_D1110_AFTER.MIGRATION_CONTROL COMMENT = ?', (COMMENT,))
            cursor.execute("""CREATE TABLE IF NOT EXISTS SFX_D1110_AFTER.MIGRATION_CONTROL.OBJECTS (
                SUBJECT_AREA VARCHAR, OBJECT_NAME VARCHAR, OBJECT_TYPE VARCHAR,
                SOURCE VARCHAR, TARGET VARCHAR, MIGRATION_STATUS VARCHAR, PARITY_STATUS VARCHAR,
                VERIFIED_AT TIMESTAMP_LTZ, EVIDENCE VARIANT
            ) COMMENT = ? """, (COMMENT,))
            cursor.execute('BEGIN')
            try:
                cursor.executemany(f"""MERGE INTO {CONTROL} t
                    USING (SELECT ? AS OBJECT_TYPE, ? AS OBJECT_NAME, ? AS SOURCE,
                                  ? AS TARGET, PARSE_JSON(?) AS EVIDENCE) s
                    ON t.SUBJECT_AREA='billing' AND t.OBJECT_TYPE=s.OBJECT_TYPE AND t.OBJECT_NAME=s.OBJECT_NAME
                    WHEN MATCHED THEN UPDATE SET SOURCE=s.SOURCE,TARGET=s.TARGET,
                        MIGRATION_STATUS='migrated', PARITY_STATUS='verified',
                        VERIFIED_AT=CURRENT_TIMESTAMP(), EVIDENCE=s.EVIDENCE
                    WHEN NOT MATCHED THEN INSERT
                        (SUBJECT_AREA,OBJECT_NAME,OBJECT_TYPE,SOURCE,TARGET,MIGRATION_STATUS,
                         PARITY_STATUS,VERIFIED_AT,EVIDENCE)
                        VALUES ('billing',s.OBJECT_NAME,s.OBJECT_TYPE,s.SOURCE,s.TARGET,
                         'migrated','verified',CURRENT_TIMESTAMP(),s.EVIDENCE)""",
                    [(kind, name, source, target, evidence) for kind, name, source, target in objects])
                cursor.execute('COMMIT')
            except Exception:
                cursor.execute('ROLLBACK')
                raise
            control = read_control(cursor)
            output.write_text(json.dumps({'control': control, 'query_id': cursor.sfqid,
                                          'parity': results, 'input_parity': inputs,
                                          'routines': routines}, indent=2, default=str) + '\n')
            print(f'{len(control)} billing inventory rows: migrated / verified', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    promote(parser.parse_args().output)
