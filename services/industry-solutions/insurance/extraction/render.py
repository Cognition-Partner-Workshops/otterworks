#!/usr/bin/env python3
"""Validate extraction traceability and render the owner's catalog and sign-off list."""

import csv
import io
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


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
    config = json.loads((HERE / "product-config.json").read_text())
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
