"""Export SonarQube issues as a JSON file a Devin ingest-mode scan can read.

Usage (see docker-compose.sonarqube.yml for bringing SonarQube up and scanning):
  python3 security/ingest/sonar_export.py --out export.json [--noise security/ingest/fixtures/inert-noise.json]

Reads SONAR_HOST_URL (default http://localhost:9000) and SONAR_TOKEN from the
environment. With --noise, the fixture's rows are merged in with the same shape
as real rows; the fixture file itself is the record of which rows were seeded.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

PAGE = 500
FIELDS = ("key", "rule", "severity", "type", "component", "line", "message", "tags")


def normalise(issue: dict, project: str) -> dict:
    row = {k: issue.get(k) for k in FIELDS}
    comp = row.get("component") or ""
    prefix = f"{project}:"
    row["component"] = comp[len(prefix):] if comp.startswith(prefix) else comp
    row["tags"] = list(row.get("tags") or [])
    return row


def fetch(host: str, token: str, project: str, **filters) -> list[dict]:
    if urllib.parse.urlparse(host).scheme not in ("http", "https"):
        raise ValueError(f"SONAR_HOST_URL must be http or https: {host}")
    auth = base64.b64encode(f"{token}:".encode()).decode()
    rows, page = [], 1
    while True:
        q = urllib.parse.urlencode({"componentKeys": project, "ps": PAGE, "p": page, "resolved": "false", **filters})
        req = urllib.request.Request(f"{host}/api/issues/search?{q}", headers={"Authorization": f"Basic {auth}"})
        # Scheme is checked above, so a file:// URL cannot reach urlopen.
        # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
        if data.get("total", 0) > 10000:
            raise ValueError(f"SonarQube issue search exceeds 10000 results for {project}; narrow the filters")
        rows += [normalise(i, project) for i in data.get("issues", [])]
        if page * PAGE >= min(data.get("total", 0), 10000):
            return rows
        page += 1


def merge_noise(rows: list[dict], noise: list[dict]) -> list[dict]:
    seen = {r["key"] for r in rows}
    merged = list(rows)
    for n in noise:
        if n["key"] in seen:
            raise ValueError(f"noise key collides with a real issue: {n['key']}")
        merged.append({k: n.get(k) for k in FIELDS})
    return merged


def build(rows: list[dict], project: str) -> dict:
    return {
        "tool": "SonarQube Community",
        "project": project,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": len(rows),
        "issues": rows,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--project", default="otterworks")
    ap.add_argument("--noise")
    a = ap.parse_args(argv)
    token = os.environ.get("SONAR_TOKEN")
    if not token:
        print("SONAR_TOKEN is not set", file=sys.stderr)
        return 2
    rows = fetch(os.environ.get("SONAR_HOST_URL", "http://localhost:9000"), token, a.project)
    if a.noise:
        with open(a.noise) as f:
            rows = merge_noise(rows, json.load(f)["rows"])
    with open(a.out, "w") as f:
        json.dump(build(rows, a.project), f, indent=1)
    print(f"wrote {len(rows)} issues to {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
