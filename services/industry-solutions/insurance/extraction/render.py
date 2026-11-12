#!/usr/bin/env python3
"""Validate extraction traceability and render the owner's catalog and sign-off list."""

import csv
import io
import json
import re
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SEED = ROOT / "services/industry-solutions/insurance/db/oltp/02_seed.sql"

SQL_STRING = r"'(?:''|[^'])*'"
SEED_TABLES = r"products|commission_rates|tier_rate_schedule"
SQL_SCHEMA = r'(?:\w+\s*\.\s*|"[^"]+"\s*\.\s*)?'
INSERT_START = re.compile(
    rf'\bINSERT\s+INTO\s+{SQL_SCHEMA}("?(?:{SEED_TABLES})"?)(?=\s|\()', re.IGNORECASE
)
INSERT_ROW = re.compile(
    rf"INSERT\s+INTO\s+{SQL_SCHEMA}(?P<table>{SEED_TABLES})\s*"
    rf"\((?P<columns>[^()]*)\)\s*VALUES\s*"
    rf"\((?P<values>(?:{SQL_STRING}|[^';])*)\)\s*;",
    re.IGNORECASE,
)


def seed_rows(sql: str) -> dict[str, list[dict]]:
    """Read literal INSERT VALUES rows, not arbitrary Oracle expressions."""
    sql = re.sub(
        rf"{SQL_STRING}|--[^\n]*|/\*.*?\*/",
        lambda m: m[0] if m[0].startswith("'") else " ",
        sql,
        flags=re.DOTALL,
    )
    masked = re.sub(SQL_STRING, lambda m: " " * len(m[0]), sql)
    if re.search(
        rf'\b(?:UPDATE|DELETE\s+FROM|MERGE\s+INTO|TRUNCATE\s+TABLE)\s+{SQL_SCHEMA}"?(?:{SEED_TABLES})"?(?=\s|;|$)',
        masked,
        re.IGNORECASE,
    ) or re.search(r"\bINSERT\s+(?:ALL|FIRST)\b", masked, re.IGNORECASE):
        raise ValueError("Seed validation supports only literal INSERT INTO ... VALUES")
    rows: dict[str, list[dict]] = {
        "products": [],
        "commission_rates": [],
        "tier_rate_schedule": [],
    }
    for start in INSERT_START.finditer(masked):
        match = INSERT_ROW.match(sql, start.start())
        if not match:
            raise ValueError(f"Unsupported seed INSERT for {start[1]}")
        columns = [c.strip().lower() for c in match["columns"].split(",")]
        if len(set(columns)) != len(columns) or not all(
            re.fullmatch(r"[a-z_][a-z_0-9]*", c) for c in columns
        ):
            raise ValueError(f"Invalid seed columns for {match['table']}")
        tokens = re.findall(rf"(?:{SQL_STRING}|[^,'])+", match["values"])
        if ",".join(tokens) != match["values"]:
            raise ValueError(f"Malformed seed values for {match['table']}")
        values: list[str | Decimal | None] = []
        for token in tokens:
            token = token.strip()
            if re.fullmatch(rf"DATE\s+{SQL_STRING}", token, re.IGNORECASE):
                values.append(
                    date.fromisoformat(token[token.index("'") + 1 : -1]).isoformat()
                )
            elif re.fullmatch(SQL_STRING, token):
                values.append(token[1:-1].replace("''", "'"))
            elif token.upper() == "NULL":
                values.append(None)
            elif re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", token):
                values.append(Decimal(token))
            else:
                raise ValueError(f"Unsupported seed literal: {token}")
        if len(columns) != len(values):
            raise ValueError(f"Seed column/value count differs for {match['table']}")
        rows[match["table"].lower()].append(dict(zip(columns, values)))
    return rows


def validate_seed_config(config: dict, sql: str) -> None:
    rows = seed_rows(sql)
    products = [
        (r["product_code"], r["product_name"], r["line_of_business"])
        for r in rows["products"]
    ]
    configured_products = [
        (p["code"], p["name"], p["line"]) for p in config["products"]
    ]
    rates = [
        (
            r["product_code"],
            r["agent_id"],
            r["rate_pct"],
            r["effective_from"],
            r["effective_to"],
        )
        for r in rows["commission_rates"]
    ]
    configured_rates: list[tuple[str, Decimal | None, Decimal, str, str | None]] = []
    tiered = {r["product_code"] for r in rows["tier_rate_schedule"]}
    for p in config["products"]:
        basis = "tiered" if p["code"] in tiered else "flat"
        if p["basis"] != basis:
            raise ValueError(f"Seed/config drift in product basis: {p['code']}")
        rate_key, date_key = (
            ("flat_reference_rate_pct", "flat_reference_from")
            if basis == "tiered"
            else ("default_rate_pct", "effective_from")
        )
        configured_rates.append(
            (
                p["code"],
                None,
                Decimal(str(p[rate_key])),
                p[date_key],
                p.get("effective_to"),
            )
        )
    configured_rates.extend(
        (
            r["product"],
            Decimal(str(r["agent_id"])),
            Decimal(str(r["rate_pct"])),
            r["effective_from"],
            r.get("effective_to"),
        )
        for r in config["agent_overrides"]
    )
    tiers = [
        (r["product_code"], r["tier_code"], r["rate_pct"], r["change_date"])
        for r in rows["tier_rate_schedule"]
    ]
    configured_tiers = [
        (r["product"], r["tier"], Decimal(str(r["rate_pct"])), r["change_date"])
        for r in config["tier_schedule"]["rows"]
    ]
    for table, actual, configured in (
        ("products", products, configured_products),
        ("commission_rates", rates, configured_rates),
        ("tier_rate_schedule", tiers, configured_tiers),
    ):
        missing = Counter(actual) - Counter(configured)
        extra = Counter(configured) - Counter(actual)
        if missing or extra:
            raise ValueError(
                f"Seed/config drift in {table}: missing from config={dict(missing)!r}; "
                f"extra in config={dict(extra)!r}"
            )


def rule_refs(value) -> set[str]:
    found = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "rules":
                found.update(child)
            elif key == "rule":
                found.add(child)
            else:
                found.update(rule_refs(child))
    elif isinstance(value, list):
        for child in value:
            found.update(rule_refs(child))
    return found


def main():
    rules = json.loads((HERE / "rules.json").read_text())
    cases = json.loads((HERE / "cases.json").read_text())
    assert len({r["id"] for r in rules}) == len(rules)
    assert [r["test"] for r in rules] == [c["id"] for c in cases]
    config = json.loads((HERE / "product-config.json").read_text(), parse_float=Decimal)
    validate_seed_config(config, SEED.read_text())
    referenced = rule_refs(config)
    assert referenced == {r["id"] for r in rules}, "config must trace all catalog rules"
    for rule in rules:
        assert rule["sentence"] and rule["approval"] == "pending"
        assert rule["status"] in {"green", "amber"}
        assert bool(rule["decision"]) == (rule["status"] == "amber")
        for source in rule["sources"]:
            lines = (ROOT / source["file"]).read_text().splitlines()
            assert 1 <= source["start"] <= source["end"] <= len(lines), source
    lines = [
        "# Commission Pay — business-rule catalog",
        "",
        "**Approval state: pending for every rule. No payment or warehouse PL/SQL has been changed.**",
        "",
        "Green means no contradiction was identified, not that the business owner approved it. Amber means a specification/code or OLTP/warehouse discrepancy, or an unverified business mapping, needs a decision.",
        "Tests characterize what Oracle actually does; amber tests must pass without silently implementing the paper specification.",
        "",
        "## Scope and evidence",
        "",
        "All business-bearing SQL in the fixture was read: OLTP tables, seed/configuration values, package bodies, ledger trigger, warehouse schema, ETL, and reporting view. Setup grants/startup logic are infrastructure, not earning rules. Identity mechanics, display names, storage lengths, and fixture-only sample people/policies are not independent compensation rules.",
        "DeepWiki was queried first for the insurance layout; its index did not include the scan/newer branch changes, so demo-insurance source and the rendered three-page scan are the evidence of record.",
        "The image-only CP-114 Rev.3 PDF was visually read page by page (not inferred from the scan generator); see spec-crosswalk.md. Source paths below are repository-relative with inclusive, 1-based lines. Tests reside in cases.json and execute through characterize.py against SQL*Plus inside Oracle Free.",
        "The test fixture is sequential and disposable: cases are ordered, and later ETL tests consume earlier payment cases. Every rule has its own executable test ID; these are not independent production-safe probes.",
        "",
        "| ID | Color | Plain business rule | Source file and lines | Scan match | Test |",
        "|---|---|---|---|---|---|",
    ]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        lineterminator="\n",
        fieldnames=[
            "id",
            "status",
            "sentence",
            "sources",
            "spec",
            "test",
            "decision",
            "approval",
        ],
    )
    writer.writeheader()
    for r in rules:
        sources = "; ".join(
            f"{s['file']}:{s['start']}-{s['end']}" for s in r["sources"]
        )
        fields = [r["id"], r["status"], r["sentence"], sources, r["spec"], r["test"]]
        lines.append("| " + " | ".join(f.replace("|", "/") for f in fields) + " |")
        writer.writerow(
            {
                **{k: r[k] for k in writer.fieldnames if k != "sources"},
                "sources": sources,
            }
        )
    (HERE / "catalog.md").write_text("\n".join(lines) + "\n")
    (HERE / "catalog.csv").write_text(output.getvalue())
    decisions: dict[str, list[dict]] = {}
    for r in rules:
        if r["decision"]:
            key, _ = r["decision"].split(":", 1)
            decisions.setdefault(key, []).append(r)
    lines = [
        "# Owner sign-off — unresolved amber decisions",
        "",
        f"{len(decisions)} decisions below cover all amber rows. Nothing is approved by extraction or by a passing characterization test. Keep the PL/SQL unchanged until an owner chooses the target behavior and separately authorizes a change.",
        "",
        "| Decision | Rules | Owner decision needed | Owner / choice / date |",
        "|---|---|---|---|",
    ]
    for key, group in decisions.items():
        lines.append(
            f"| {key} | {', '.join(r['id'] for r in group)} | {group[0]['decision'].split(':', 1)[1].strip()} | Pending / — / — |"
        )
    lines += [
        "",
        "## Full catalog approval",
        "",
        "After resolving amber items, record approval or rejection of every catalog rule (including green code-only behaviors).",
        "",
        "Business owner: __________  Date: __________  Catalog/source fingerprint: __________",
        "",
        "Decisions do not authorize a code change in this PR.",
    ]
    (HERE / "sign-off.md").write_text("\n".join(lines) + "\n")
    print(
        f"Validated/rendered {len(rules)} rules, {len(cases)} tests, {len(decisions)} decisions"
    )


if __name__ == "__main__":
    main()
