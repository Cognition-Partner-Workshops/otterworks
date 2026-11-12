"""Upload SARIF and start ingestion: FILE --org ID --profile ID [--dry-run]. Requires requests."""

import argparse
import json
import os
from pathlib import Path
from urllib.parse import quote

import requests


def request_body(report, profile, attachment_url):
    repositories = sorted({run["properties"]["repository"] for run in report["runs"]})
    if report.get("version") != "2.1.0" or not repositories:
        raise ValueError("Expected SARIF 2.1.0 with repository metadata")
    return {"profile_id": profile, "repos": [{"repo_name": repo, "host": "github.com"} for repo in repositories],
            "attachment_urls": [attachment_url]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sarif", type=Path)
    parser.add_argument("--org", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    base = "https://partner-workshops.devinenterprise.com/api/v3"
    org = quote(args.org, safe="")
    upload = f"{base}/organizations/{org}/attachments"
    ingestion = f"{base}/enterprise/organizations/{org}/code-scans/ingestion"
    body = request_body(json.loads(args.sarif.read_text()), args.profile, "<uploaded attachment URL>")
    if args.dry_run:
        print(json.dumps({"upload": {"method": "POST", "url": upload, "multipart": {"file": args.sarif.name}},
                          "ingestion": {"method": "POST", "url": ingestion, "json": body}}, indent=2))
        return 0
    headers = {"Authorization": f"Bearer {os.environ['DEVIN_ENTERPRISE_API_KEY']}"}
    with args.sarif.open("rb") as source:
        response = requests.post(upload, headers=headers,
                                 files={"file": (args.sarif.name, source, "application/sarif+json")}, timeout=120)
    response.raise_for_status()
    body["attachment_urls"] = [response.json()["url"]]
    response = requests.post(ingestion, headers=headers, json=body, timeout=120)
    response.raise_for_status()
    print(json.dumps(response.json(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
