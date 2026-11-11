"""Render typed billing views and their column-level contracts."""
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / 'snowflake'))
from seed_contract import seed_spec


def render():
    spec = yaml.safe_load((ROOT.parent / "snowflake/landing_columns.yml").read_text())
    output = {}
    models = []
    seed = seed_spec()['billing']
    for table, columns in spec["billing"].items():
        name = "stg_billing__" + table.lower()
        selections = [f"    cast({col} as {kind}) as {col.lower()}"
                      for col, kind in columns.items()]
        aliases = {next(iter(seed[table])): table + '_ID', 'INVOICE_ID': 'INVOICE_HDR_ID'}
        for index, (col, kind) in enumerate(columns.items()):
            alias = aliases.get(col)
            if alias and alias != col and alias in columns:
                selections[index] = f'    cast(coalesce({col}, {alias}) as {kind}) as {col.lower()}'
            if table == 'CREDIT_NOTE' and col == 'ISSUE_DATE':
                selections[index] = '    cast(coalesce(ISSUE_DATE, CREDIT_DT) as DATE) as issue_date'
            if table == 'INVOICE_HDR' and col == 'DUE_DATE':
                selections[index] = """    cast(coalesce(DUE_DATE, dateadd(day,
        coalesce((select max(c.PAYMENT_TERMS_DAYS)
                  from {{ source('billing', 'CUSTOMER_ACCOUNT') }} c
                  where c.CUSTOMER_ID = i.CUSTOMER_ID), 30),
        coalesce(INVOICE_DATE, INVOICE_DT))) as DATE) as due_date"""
        output[f"{name}.sql"] = (
            "select\n" + ",\n".join(selections)
            + f"\nfrom {{{{ source('billing', '{table}') }}}}" + (' i' if table == 'INVOICE_HDR' else '') + '\n'
        )
        tests = []
        for column in columns:
            checks = []
            if column == next(iter(seed[table])):
                checks += ["not_null", "unique"]
            if column == "CUSTOMER_ID" and column in seed[table]:
                if 'not_null' not in checks:
                    checks += ["not_null"]
                if table == "CUSTOMER_ACCOUNT":
                    if 'unique' not in checks:
                        checks += ["unique"]
                else:
                    checks += [{"relationships": {
                        "to": "ref('stg_billing__customer_account')", "field": "customer_id"}}]
            if column == "IS_ACTIVE":
                checks += [{"accepted_values": {"values": ["Y", "N"]}}]
            targets = {
                'GL_ACCOUNT_ID': 'gl_account', 'INVOICE_ID': 'invoice_hdr',
                'SUBSCRIPTION_ID': 'subscription', 'CREDIT_NOTE_ID': 'credit_note',
            }
            if column in targets and column in seed[table] and column != next(iter(seed[table])):
                checks += [{'relationships': {
                    'to': "ref('stg_billing__" + targets[column] + "')",
                    'field': column.lower()}}]
            if column == 'JOURNAL_ID':
                checks += ['not_null']
            if checks:
                tests.append({"name": column.lower(), "tests": checks})
        models.append({
            "name": name, "description": "sfx-d1110 typed billing landing view",
            "columns": tests,
        })
        if table == 'GL_JOURNAL_LINE':
            models[-1]['tests'] = ['balanced_journal']
    output["schema.yml"] = yaml.safe_dump({"version": 2, "models": models}, sort_keys=False)
    return output


if __name__ == "__main__":
    for filename, content in render().items():
        (ROOT / "models/staging/billing" / filename).write_text(content)
