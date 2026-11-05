"""Group likely shared causes: report.sarif --json clusters.json --markdown clusters.md."""

import argparse
import hashlib
import json
import re
from pathlib import Path


def cluster(report):
    if report.get("version") != "2.1.0":
        raise ValueError("Expected SARIF 2.1.0")
    groups = {}
    for run in report["runs"]:
        rules = {rule["id"]: rule for rule in run["tool"]["driver"].get("rules", [])}
        for result in run.get("results", []):
            rule = result["ruleId"]
            props = result.get("properties", {})
            tags = props.get("tags", []) + rules.get(rule, {}).get("properties", {}).get("tags", [])
            cwes = sorted({f"CWE-{match}" for tag in tags for match in re.findall(r"cwe[-: ]?(\d+)", tag, re.IGNORECASE)})
            key = (rule, tuple(cwes))
            group = groups.setdefault(key, {"cluster": hashlib.sha256(json.dumps(key).encode()).hexdigest()[:12],
                                            "rules": [rule], "cwes": cwes, "count": 0, "repos": set()})
            group["count"] += 1
            group["repos"].add(props.get("repository") or run.get("properties", {}).get("repository", "unknown"))
    return [{**group, "repos": sorted(group["repos"])} for _, group in sorted(groups.items())]


def markdown(groups):
    def escape(value):
        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    lines = ["| Cluster | Rule(s) | CWE | Count | Repos touched |", "|---|---|---|---:|---|"]
    for group in groups:
        lines.append("| " + " | ".join(escape(value) for value in (
            group["cluster"], ", ".join(group["rules"]), ", ".join(group["cwes"]),
            group["count"], ", ".join(group["repos"]))) + " |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sarif", type=Path)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    args = parser.parse_args()
    groups = cluster(json.loads(args.sarif.read_text()))
    encoded = json.dumps(groups, indent=2)
    table = markdown(groups)
    args.json.write_text(encoded + "\n")
    args.markdown.write_text(table)
    print(encoded)
    print(table)


if __name__ == "__main__":
    main()
