"""Build the scanner export for the vuln-shared-lib estate from findings.manifest.json.

Writes findings.sarif (SARIF 2.1.0, Checkmarx field shape, one run per repository),
findings.csv and prioritized.csv next to this file. Line numbers are resolved from
each finding's anchor in the current source, so the export always points at the code
as it is. `--check` regenerates in memory and fails if the committed files differ.
"""

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ESTATE = HERE.parents[1]
REPO_ROOT = ESTATE.parents[2]
MANIFEST = HERE / "findings.manifest.json"
OUTPUTS = ("findings.sarif", "findings.csv", "prioritized.csv")

SARIF_LEVEL = {"Critical": "error", "High": "error", "Medium": "warning", "Low": "note"}
SECURITY_SEVERITY = {"Critical": "9.5", "High": "8.0", "Medium": "5.5", "Low": "2.0"}
SLA_DAYS = {"Critical": 15, "High": 30, "Medium": 90, "Low": 180}


def load_manifest(path=MANIFEST):
    manifest = json.loads(path.read_text())
    ids = [finding["id"] for finding in manifest["findings"]]
    if ids != list(range(1, len(ids) + 1)):
        raise ValueError(f"finding ids must be 1..N in order, got {ids}")
    return manifest


def locate(finding, root=ESTATE):
    source = root / finding["path"]
    lines = source.read_text().splitlines()
    pattern = re.compile(finding["anchor"])
    hits = [number for number, line in enumerate(lines, start=1) if pattern.search(line)]
    if len(hits) != 1:
        raise ValueError(
            f"finding {finding['id']}: anchor {finding['anchor']!r} matched {len(hits)} lines "
            f"in {finding['path']} (expected exactly one)")
    line = hits[0]
    return line, lines[line - 1].strip()


def similarity_id(finding):
    digest = hashlib.sha256(
        f"{finding['query']}|{finding['path']}|{finding['anchor']}".encode()).digest()
    return int.from_bytes(digest[:4], "big", signed=True)


def resolve(manifest, root=ESTATE):
    scan_date = date.fromisoformat(manifest["scan_date"])
    rows = []
    for finding in manifest["findings"]:
        line, snippet = locate(finding, root)
        project = manifest["projects"][finding["project"]]
        rows.append({
            **finding,
            "line": line,
            "snippet": snippet,
            "uri": f"{manifest['estate_path']}/{finding['path']}",
            "repository": project["repository"],
            "similarity_id": similarity_id(finding),
            "finding_key": f"VSL-{finding['id']:02d}",
            "sla_due": (scan_date + timedelta(days=SLA_DAYS[finding["severity"]])).isoformat(),
        })
    return rows


def rule_id(query):
    return str(int(hashlib.sha256(query.encode()).hexdigest()[:8], 16) % 9_000_000 + 1_000_000)


def sarif(manifest, rows):
    runs = []
    for key, project in manifest["projects"].items():
        results = [row for row in rows if row["project"] == key]
        rules = {}
        for row in results:
            rules.setdefault(row["query"], {
                "id": rule_id(row["query"]),
                "name": row["query"],
                "shortDescription": {"text": row["query"].replace("_", " ")},
                "properties": {
                    "cwe": f"CWE-{row['cwe']}",
                    "severity": row["severity"],
                    "security-severity": SECURITY_SEVERITY[row["severity"]],
                    "tags": ["security", f"external/cwe/cwe-{row['cwe']}"],
                },
            })
        runs.append({
            "tool": {"driver": {
                "name": manifest["tool"]["name"],
                "semanticVersion": manifest["tool"]["version"],
                "informationUri": "https://checkmarx.com/",
                "rules": sorted(rules.values(), key=lambda rule: rule["id"]),
            }},
            "versionControlProvenance": [{
                "repositoryUri": manifest["source_repository"],
                "branch": manifest["branch"],
            }],
            "properties": {"repository": project["repository"], "projectPath": f"{manifest['estate_path']}/{key}"},
            "results": [{
                "ruleId": rule_id(row["query"]),
                "level": SARIF_LEVEL[row["severity"]],
                "message": {"text": row["message"]},
                "locations": [{"physicalLocation": {
                    "artifactLocation": {"uri": row["uri"]},
                    "region": {"startLine": row["line"], "snippet": {"text": row["snippet"]}},
                }}],
                "partialFingerprints": {"similarityId": str(row["similarity_id"])},
                "properties": {
                    "findingId": row["finding_key"],
                    "queryName": row["query"],
                    "severity": row["severity"],
                    "security-severity": SECURITY_SEVERITY[row["severity"]],
                    "cwe": f"CWE-{row['cwe']}",
                    "similarityId": row["similarity_id"],
                    "state": "To Verify",
                    "repository": project["repository"],
                    "ownerTeam": row["team"],
                    "tags": ["security", f"external/cwe/cwe-{row['cwe']}"],
                },
            } for row in results],
        })
    return {"$schema": "https://json.schemastore.org/sarif-2.1.0.json", "version": "2.1.0", "runs": runs}


def to_csv(header, records):
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(records)
    return buffer.getvalue()


def findings_csv(manifest, rows):
    return to_csv(
        ["SimilarityID", "FindingID", "Query", "Severity", "CWE", "Project", "SrcFileName", "Line",
         "Result State", "Detection Date", "Owner Team"],
        [[row["similarity_id"], row["finding_key"], row["query"], row["severity"], row["cwe"],
          row["repository"], row["uri"], row["line"], "To Verify", manifest["scan_date"], row["team"]]
         for row in rows])


def prioritized_csv(rows):
    ordered = sorted(rows, key=lambda row: (-row["risk_score"], row["id"]))
    return to_csv(
        ["asset", "finding_id", "finding", "severity", "risk_score", "sla_due", "owner_team", "location"],
        [[row["repository"], row["finding_key"], row["title"], row["severity"], row["risk_score"],
          row["sla_due"], row["team"], f"{row['uri']}:{row['line']}"] for row in ordered])


def render(manifest=None, root=ESTATE):
    manifest = manifest or load_manifest()
    rows = resolve(manifest, root)
    return {
        "findings.sarif": json.dumps(sarif(manifest, rows), indent=2) + "\n",
        "findings.csv": findings_csv(manifest, rows),
        "prioritized.csv": prioritized_csv(rows),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if committed exports are stale")
    args = parser.parse_args(argv)
    outputs = render()
    if args.check:
        stale = [name for name, text in outputs.items()
                 if not (HERE / name).exists() or (HERE / name).read_text() != text]
        if stale:
            print("stale scanner export, run generate_findings.py: " + ", ".join(stale), file=sys.stderr)
            return 1
        print("scanner export matches the source")
        return 0
    for name, text in outputs.items():
        (HERE / name).write_text(text)
        print(f"wrote {(HERE / name).relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
