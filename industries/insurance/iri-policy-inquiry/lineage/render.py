"""Render the reviewed, machine-readable lineage inventory."""
import argparse
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent


def render(data):
    out = ["# IRI Policy Inquiry lineage", "", "Generated from lineage.yaml; do not edit this document.", "",
           "## Rules", ""]
    for name, rule in data["rules"].items():
        out.append(f"- **{name}**: `{rule}`")
    out += ["", "RTN_CD / HTTP: " + ", ".join(f"{k} → {v}" for k, v in data["status_codes"].items()),
            "Errors use the pinned Error schema (code, message; timestamp optional; correlationId header only).", ""]
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    for op in ("summary", "values", "funds"):
        out += [f"## {op}", "", "| DB column → legacy field → IRI element | Rule | Status | Note |",
                "| --- | --- | --- | --- |"]
        for r in data["rows"]:
            if r["operation"] == op:
                chain = f'{r["db"]} → {r["legacy"]} ({r["legacy_format"]}) → {r["iri"]}'
                out.append("| " + " | ".join(map(cell, [chain, r["rule"], r["status"], r["note"]])) + " |")
        out.append("")
    out += ["## Sign-off", "", "A difference is a failure until explained from data. Business-only decisions belong here; the field stays in the payload.", ""]
    for r in data["rows"]:
        if r["status"] == "sign-off":
            out.append(f'- **{r["operation"]}: {r["legacy"]} → {r["iri"]}**: {r["note"]}')
    return "\n".join(out) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render(yaml.safe_load((ROOT / "lineage.yaml").read_text()))
    target = ROOT / "LINEAGE.md"
    if args.check:
        if not target.exists() or target.read_text() != expected:
            raise SystemExit("LINEAGE.md is stale; run python3 lineage/render.py")
        print("LINEAGE.md is current")
    else:
        target.write_text(expected)


if __name__ == "__main__":
    main()
