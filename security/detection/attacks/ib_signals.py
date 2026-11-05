# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx"]
# ///
"""Edge-tripwire scenarios; responses are evidence, never proof of IB ownership."""

from __future__ import annotations

import argparse
import json
import secrets
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import httpx

SCENARIOS = (
    "IB-PAYMENT-ANONYMOUS",
    "IB-PAYMENT-AMOUNT",
    "IB-AUTH-ID-MISMATCH",
    "IB-ADMIN-NON-ADMIN",
    "IB-FAILED-LOGINS",
)


class SetupError(RuntimeError):
    pass


def register(client) -> dict:
    email = f"ib-signal-{uuid.uuid4().hex}@example.test"
    password = f"Signal-{secrets.token_urlsafe(24)}-1!"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "displayName": "Detection replay"},
    )
    if response.status_code not in (200, 201):
        raise SetupError(f"Registration failed: HTTP {response.status_code}")
    data = response.json()
    if not isinstance(data, dict) or not data.get("accessToken") or not isinstance(data.get("user"), dict) or not data["user"].get("id"):
        raise SetupError("Registration returned no usable identity")
    return {"email": email, "token": data["accessToken"], "id": data["user"]["id"]}


def run_scenario(client, scenario: str) -> dict:
    responses = []

    def send(method, path, **kwargs):
        response = client.request(method, path, **kwargs)
        responses.append({"method": method, "path": path, "status": response.status_code})

    if scenario == "IB-PAYMENT-ANONYMOUS":
        for path in ("/transaction/fund-transfer", "/api/v1/transaction/fund-transfer", "/utility-payment", "/api/v1/utility-payment"):
            send("POST", path, json={"amount": "10.50"})
    else:
        identity = register(client)
        headers = {"Authorization": f"Bearer {identity['token']}"}
        if scenario == "IB-PAYMENT-AMOUNT":
            for amount in (0, -100000, 0.005):
                send("POST", "/api/v1/transaction/fund-transfer", headers=headers, json={"amount": amount})
        elif scenario == "IB-AUTH-ID-MISMATCH":
            other = register(client)
            send("GET", "/api/v1/documents", headers={**headers, "X-Auth-Id": other["id"]})
        elif scenario == "IB-ADMIN-NON-ADMIN":
            for path in ("/api/v1/admin/users", "/bank-users"):
                send("GET", path, headers=headers)
        elif scenario == "IB-FAILED-LOGINS":
            wrong_password = f"Wrong-{secrets.token_urlsafe(24)}"
            for _ in range(12):
                send("POST", "/api/v1/auth/login", json={"email": identity["email"], "password": wrong_password})
        else:
            raise SetupError("Unknown scenario")
    return {
        "finding_id": scenario,
        "verdict": "inconclusive",
        "detail": "Tripwire requests sent; no IB account ownership or payment execution is observable here. " + "; ".join(f"{r['method']} {r['path']} -> {r['status']}" for r in responses),
        "evidence": {"responses": responses},
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--report-dir", required=True, type=Path)
    parser.add_argument("--only", action="append", choices=SCENARIOS, required=True)
    args = parser.parse_args(argv)
    target = urlsplit(args.target)
    if target.scheme not in ("http", "https") or not target.netloc or target.username is not None or target.password is not None:
        parser.error("target must be an HTTP URL without embedded credentials")
    try:
        # A single fixed client key, never rotated between failed-login attempts.
        with httpx.Client(base_url=args.target.rstrip("/"), timeout=15, headers={"X-Forwarded-For": "192.0.2.80"}) as client:
            results = [run_scenario(client, scenario) for scenario in args.only]
        args.report_dir.mkdir(parents=True, exist_ok=True)
        (args.report_dir / "dast-report.json").write_text(json.dumps({"results": results}, indent=2) + "\n")
        for row in results:
            print(f"{row['finding_id']}: {row['detail']}")
        return 0
    except (SetupError, httpx.HTTPError, ValueError) as exc:
        print(f"Scenario setup failed: {type(exc).__name__}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
