# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx"]
# ///
"""Fineract-shaped edge requests, not proof of Fineract authorization or execution."""

import argparse
import json
import secrets
from pathlib import Path
from urllib.parse import urlsplit

import httpx

SCENARIOS = ("FIN-MAKERCHECKER-REPEAT", "FIN-MAKERCHECKER-DISABLED", "FIN-PRIVILEGED-ENDPOINT")
PREFIXES = ("", "/api/v1", "/fineract-provider/api/v1")


def run_scenario(client, scenario):
    if scenario not in SCENARIOS:
        raise ValueError("Unknown scenario")
    responses = []

    def send(method, path, **kwargs):
        response = client.request(method, path, **kwargs)
        responses.append({"method": method, "path": path, "status": response.status_code})

    for prefix in PREFIXES:
        if scenario == "FIN-MAKERCHECKER-REPEAT":
            identifier = secrets.randbelow(2**31 - 1) + 1
            for _ in range(2):
                send("POST", f"{prefix}/makercheckers/{identifier}?command=approve")
        elif scenario == "FIN-MAKERCHECKER-DISABLED":
            send("PUT", f"{prefix}/configurations/name/maker-checker", json={"enabled": False})
            send("POST", f"{prefix}/configurations/1?command=disable")
            send("POST", f"{prefix}/configurations/name/maker-checker?command=disable")
        else:
            send("POST", f"{prefix}/datatables/deregister/detection-replay")
            send("POST", f"{prefix}/creditBureauIntegration/addCreditReport")
    return {
        "finding_id": scenario,
        "verdict": "inconclusive",
        "detail": "Edge requests only; actor office and permissions are not evaluated; no Fineract is deployed. "
        + "; ".join(f"{r['method']} {r['path']} -> {r['status']}" for r in responses),
        "evidence": {"responses": responses},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--report-dir", required=True, type=Path)
    parser.add_argument("--only", action="append", choices=SCENARIOS, required=True)
    args = parser.parse_args(argv)
    target = urlsplit(args.target)
    if target.scheme not in ("http", "https") or not target.netloc or target.username is not None:
        parser.error("target must be an HTTP URL without credentials")
    try:
        with httpx.Client(base_url=args.target.rstrip("/"), timeout=15, headers={"X-Forwarded-For": "192.0.2.81"}) as client:
            results = [run_scenario(client, scenario) for scenario in args.only]
        args.report_dir.mkdir(parents=True, exist_ok=True)
        (args.report_dir / "dast-report.json").write_text(json.dumps({"results": results}, indent=2) + "\n")
        return 0
    except (httpx.HTTPError, ValueError, OSError) as exc:
        print(f"Scenario setup failed: {type(exc).__name__}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
