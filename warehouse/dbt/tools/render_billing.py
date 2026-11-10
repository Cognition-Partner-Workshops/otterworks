"""Render typed billing views and their column-level contracts."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def render():
    spec = yaml.safe_load((ROOT.parent / "snowflake/landing_columns.yml").read_text())
    output = {}
    models = []
    for table, columns in spec["billing"].items():
        name = "stg_billing__" + table.lower()
        selections = [f"    cast({col} as {kind}) as {col.lower()}"
                      for col, kind in columns.items()]
        output[f"{name}.sql"] = (
            "select\n" + ",\n".join(selections)
            + f"\nfrom {{{{ source('billing', '{table}') }}}}\n"
        )
        tests = []
        for column in columns:
            checks = []
            if column == table + "_ID":
                checks += ["not_null", "unique"]
            if column == "CUSTOMER_ID":
                checks += ["not_null"]
                if table == "CUSTOMER_ACCOUNT":
                    checks += ["unique"]
                else:
                    checks += [{"relationships": {
                        "to": "ref('stg_billing__customer_account')", "field": "customer_id"}}]
            if column == "IS_ACTIVE":
                checks += [{"accepted_values": {"values": ["Y", "N"]}}]
            targets = {
                'GL_ACCOUNT_ID': 'gl_account', 'INVOICE_HDR_ID': 'invoice_hdr',
                'PLAN_CATALOG_ID': 'plan_catalog',
            }
            if column in targets and column != table + '_ID':
                checks += ['not_null', {'relationships': {
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
