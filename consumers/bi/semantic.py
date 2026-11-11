"""Deterministic SQL snapshots for selected LookML explore fields."""
from pathlib import Path
import re

import lkml

ROOT = Path(__file__).parent


def project():
    model = lkml.load((ROOT / "finance.model.lkml").read_text())
    views = {}
    for path in sorted((ROOT / "views").glob("*.lkml")):
        for view in lkml.load(path.read_text())["views"]:
            views[view["name"]] = view
    return model, views


def queries():
    model, views = project()

    def expand(sql, view_name):
        def field(match):
            reference = match.group(1)
            if reference == "TABLE":
                return view_name
            owner, name = reference.split(".")
            dimension = next(d for d in views[owner]["dimensions"] if d["name"] == name)
            return expand(dimension["sql"], owner)
        return re.sub(r"\$\{([^}]+)\}", field, sql)

    result = {"overdue_accounts": views["overdue_accounts"]["derived_table"]["sql"].strip()}
    for name, dimension, measure in [
        ("invoices", "month_label", "billed"),
        ("payments", "month_label", "collected"),
        ("invoice_revenue", "month_label", "billed"),
        ("gl_journal", "period_id", "movement"),
    ]:
        view = views[name]
        dim = next(d for d in view["dimensions"] if d["name"] == dimension)
        metric = next(m for m in view["measures"] if m["name"] == measure)
        explore = next(e for e in model["explores"] if e["name"] == name)
        sql = (
            f"SELECT {expand(dim['sql'], name)} AS LABEL,\n"
            f"  SUM({expand(metric['sql'], name)}) AS AMOUNT\n"
            f"FROM {view['sql_table_name'] if 'sql_table_name' in view else '(' + view['derived_table']['sql'].strip() + ')'} AS {name}"
        )
        for join in explore.get("joins", []):
            alias = join["name"]
            sql += (
                f"\nLEFT JOIN {views[alias]['sql_table_name']} AS {alias}"
                f" ON {expand(join['sql_on'], name)}"
            )
        result[name] = sql + "\nGROUP BY 1\nORDER BY 1"
    return result
