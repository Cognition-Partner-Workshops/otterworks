"""Export several SonarQube projects: --project KEY=OWNER/REPO@SHA --out report.sarif."""

import argparse
import base64
import hashlib
import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from sonar_export import fetch, normalise

SEVERITIES = {"BLOCKER": ("error", "9.5"), "CRITICAL": ("error", "8.0"),
              "MAJOR": ("warning", "5.0"), "MINOR": ("note", "3.0"),
              "INFO": ("note", "1.0")}


def api(host, token, endpoint, **params):
    if urllib.parse.urlparse(host).scheme not in ("http", "https"):
        raise ValueError("SonarQube URL must use HTTP(S)")
    auth = base64.b64encode(f"{token}:".encode()).decode()
    req = urllib.request.Request(f"{host}/api/{endpoint}?{urllib.parse.urlencode(params)}",
                                 headers={"Authorization": f"Basic {auth}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"SonarQube {endpoint}: {error.code} {error.read().decode()}") from error


def collect(host, token, project):
    rows = []
    for issue_type in ("VULNERABILITY", "BUG", "CODE_SMELL"):
        for severity in SEVERITIES:
            rows.extend(fetch(host, token, project, types=issue_type, severities=severity))
    page = 1
    while True:
        data = api(host, token, "hotspots/search", project=project, ps=500, p=page)
        for hotspot in data.get("hotspots", []):
            detail = api(host, token, "hotspots/show", hotspot=hotspot["key"])
            rule = detail["rule"]
            rows.append(normalise({**hotspot, "rule": rule["key"],
                                   "type": "SECURITY_HOTSPOT",
                                   "severity": {"HIGH": "CRITICAL", "MEDIUM": "MAJOR",
                                                "LOW": "MINOR"}.get(rule.get("vulnerabilityProbability"), "MAJOR")}, project))
        if page * 500 >= data["paging"]["total"]:
            break
        page += 1
    rules = {key: api(host, token, "rules/show", key=key)["rule"]
             for key in sorted({row["rule"] for row in rows})}
    return rows, rules


def tags_for(row, rule):
    tags = set(row.get("tags") or []) | set(rule.get("tags") or []) | set(rule.get("sysTags") or [])
    standards = rule.get("securityStandards") or {}
    if isinstance(standards, dict):
        for family, values in standards.items():
            tags.update(f"{family}-{v}" for v in values)
    else:
        tags.update(standards)
    return sorted(tags)


def build_run(repository, revision, rows, rules):
    descriptors, results = {}, []
    for row in rows:
        rule_id = row["rule"]
        rule = rules.get(rule_id, {})
        tags = tags_for(row, rule)
        if row.get("type") not in ("VULNERABILITY", "BUG", "SECURITY_HOTSPOT") and not (
            row.get("type") == "CODE_SMELL" and any(
                re.search(r"security|cwe|owasp|sans|cert|sql-injection|xss", tag, re.IGNORECASE) for tag in tags)):
            continue
        level, score = SEVERITIES.get(row.get("severity"), ("warning", "5.0"))
        descriptor = descriptors.setdefault(rule_id, {
            "id": rule_id, "shortDescription": {"text": rule.get("name") or rule_id},
            "fullDescription": {"text": html.unescape(re.sub("<[^>]+>", " ", rule.get("htmlDesc") or rule.get("name") or rule_id))},
            "properties": {"tags": tags, "security-severity": score}})
        descriptor["properties"]["security-severity"] = str(max(float(score), float(descriptor["properties"]["security-severity"])))
        path = row.get("component") or ""
        physical = {"artifactLocation": {"uri": urllib.parse.quote(path, safe="/"), "uriBaseId": "REPOSITORY"}}
        if row.get("line") and row["line"] > 0:
            physical["region"] = {"startLine": row["line"]}
        identity = [repository, rule_id, path, row.get("line"), row.get("message")]
        results.append({"ruleId": rule_id, "level": level,
                        "message": {"text": row.get("message") or rule.get("name") or rule_id},
                        "locations": [{"physicalLocation": physical}],
                        "partialFingerprints": {"sourceFinding/v1": hashlib.sha256(json.dumps(identity).encode()).hexdigest()},
                        "properties": {"repository": repository, "tags": tags, "security-severity": score,
                                       "sonarType": row.get("type"), "sonarIssue": row.get("key")}})
    return {"tool": {"driver": {"name": "SonarQube", "rules": list(descriptors.values())}},
            "versionControlProvenance": [{"repositoryUri": f"https://github.com/{repository}", "revisionId": revision}],
            "originalUriBaseIds": {"REPOSITORY": {"uri": f"https://github.com/{repository}/blob/{revision}/"}},
            "properties": {"repository": repository}, "results": results}


def document(runs):
    return {"$schema": "https://json.schemastore.org/sarif-2.1.0.json", "version": "2.1.0", "runs": runs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", action="append", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    runs = []
    for spec in args.project:
        project, source = spec.split("=", 1)
        repository, revision = source.rsplit("@", 1)
        rows, rules = collect(os.environ.get("SONAR_HOST_URL", "http://localhost:9000"), os.environ["SONAR_TOKEN"], project)
        runs.append(build_run(repository, revision, rows, rules))
        print(f"{repository}: {len(runs[-1]['results'])}")
    with open(args.out, "w") as output:
        json.dump(document(runs), output, indent=2)


if __name__ == "__main__":
    main()
