#!/usr/bin/env python3
"""Score a rule catalog against the answer key on this branch.

  python3 legacy-rating/answer-key/score_catalog.py [git-ref]

Reads legacy-rating/catalog/rules.md from the ref (default origin/demo-insrules)
and prints matched, missed and extra counts. It never prints a key rule, so the
output can go straight into a pull request or a hand-back.

A key rule counts as matched when a catalog rule cites the same source paragraph
or method and carries the same table, or when its statement shares enough of the
key statement's distinctive words. Scoring is by coverage, not by rule number:
the catalog may split one key rule across several of its own.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parents[2]
KEY = HERE / "legacy-rating/answer-key/rules.yaml"
STOP = set("the a an and or of to in on at is are be with for from by that this it as any no not every each both".split())


def key_rules() -> list[dict]:
    rules = []
    for line in KEY.read_text().splitlines():
        line = line.strip()
        if not line.startswith("- {"):
            continue
        row = {}
        for field in ("id", "cobol", "smalltalk", "table", "kind"):
            m = re.search(rf"{field}: ([^,}}]+)", line)
            row[field] = (m.group(1).strip().strip('"') if m else "null")
        m = re.search(r'statement: "([^"]*)"', line)
        row["statement"] = m.group(1) if m else ""
        rules.append(row)
    return rules


def citations(ref: str) -> dict[str, str]:
    """Rows of an optional citations.md, keyed by rule ID, so split catalogs are scored whole."""
    out = subprocess.run(["git", "show", f"{ref}:legacy-rating/catalog/citations.md"],
                         capture_output=True, text=True).stdout
    rows = {}
    for line in out.splitlines():
        m = re.match(r"\|\s*(?:<a [^>]*></a>)?\[?(R\d+)\]?(?:\([^)]*\))?\s*\|(.*)", line)
        if m:
            rows[m.group(1)] = rows.get(m.group(1), "") + " " + m.group(2)
    return rows


def catalog(ref: str) -> str:
    return subprocess.run(
        ["git", "show", f"{ref}:legacy-rating/catalog/rules.md"],
        cwd=HERE, capture_output=True, text=True, check=True).stdout


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9$%.]+", text.lower()) if w not in STOP and len(w) > 2}


def rows(markdown: str) -> list[tuple[str, str]]:
    """Each catalog row as (rule id, its own text plus the section text above it)."""
    out, section = [], ""
    for line in markdown.splitlines():
        if line.startswith("#") or line.startswith("**"):
            section = (section + " " + line) if line.startswith("**") else line
        m = re.match(r"\|\s*\[?(R\d+)\]?(?:\([^)]*\))?\s*\|(.*)", line)
        if m:
            out.append((m.group(1), m.group(2) + " " + section))
    return out


def main() -> int:
    ref = sys.argv[1] if len(sys.argv) > 1 else "origin/demo-insrules"
    cites_by_rule = citations(ref)
    entries = [(r, t + cites_by_rule.get(r, "")) for r, t in rows(catalog(ref))]
    if not entries:
        print("no catalog rows found", file=sys.stderr)
        return 2

    claimed: set[str] = set()
    matched = 0
    for key in key_rules():
        want = words(key["statement"])
        cites = [c for c in (key["cobol"], key["smalltalk"], key["table"]) if c != "null"]
        hits = []
        for rule_id, text in entries:
            low = text.lower()
            cited = any(c.split(">>")[-1].lower() in low for c in cites)
            overlap = len(want & words(text)) / max(len(want), 1)
            if (cited and overlap >= 0.25) or overlap >= 0.5:
                hits.append(rule_id)
        if hits:
            matched += 1
            claimed.update(hits)
    extra = [r for r, _ in entries if r not in claimed]

    print(f"catalog rules: {len(entries)}")
    print(f"key rules:     {len(key_rules())}")
    print(f"matched:       {matched}")
    print(f"missed:        {len(key_rules()) - matched}")
    print(f"extra:         {len(extra)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
