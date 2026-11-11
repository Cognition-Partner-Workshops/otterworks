from __future__ import annotations

import html
import json
from pathlib import Path


def write_report(report: dict, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "parity.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# Integration parity", "", "| Flow | Replayed | Matched | Differing | Status |",
             "| --- | ---: | ---: | ---: | --- |"]
    rows = []
    for row in report["flows"]:
        values = [row["flow"], row["replayed"], row["matched"], row["differing"], row["status"]]
        lines.append("| " + " | ".join(str(v).replace("|", "\\|").replace("\n", " ") for v in values) + " |")
        rows.append("<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in values) + "</tr>")
    evidence = json.dumps(report, indent=2)
    lines.extend(["", "## Differences and fault evidence", "", "```json", evidence, "```", ""])
    (directory / "parity.md").write_text("\n".join(lines))
    (directory / "parity.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Integration parity</title>'
        '<h1>Integration parity</h1><table><thead><tr><th>Flow</th><th>Replayed</th>'
        '<th>Matched</th><th>Differing</th><th>Status</th></tr></thead><tbody>'
        + "".join(rows) + "</tbody></table><h2>Differences and fault evidence</h2><pre>"
        + html.escape(evidence) + "</pre></html>\n")
