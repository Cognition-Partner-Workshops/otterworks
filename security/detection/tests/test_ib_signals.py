"""Offline request-shape and report contracts for the five edge tripwires."""

import importlib.util
import json
from pathlib import Path

import httpx
import pytest

SPEC = importlib.util.spec_from_file_location(
    "ib_signals", Path(__file__).parents[1] / "attacks" / "ib_signals.py"
)
signals = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(signals)


def client_and_requests(fail_registration=False):
    requests = []
    registrations = 0

    def handle(request):
        nonlocal registrations
        requests.append(request)
        if request.url.path == "/api/v1/auth/register":
            registrations += 1
            if fail_registration:
                return httpx.Response(503)
            return httpx.Response(201, json={"accessToken": f"token-{registrations}", "user": {"id": f"user-{registrations}"}})
        return httpx.Response(401 if request.url.path.endswith("/login") else 404)

    return httpx.Client(
        base_url="http://gateway", transport=httpx.MockTransport(handle),
        headers={"X-Forwarded-For": "192.0.2.80"},
    ), requests


@pytest.mark.parametrize("scenario", signals.SCENARIOS)
def test_scenario_request_shapes(scenario):
    client, requests = client_and_requests()
    with client:
        result = signals.run_scenario(client, scenario)
    assert result["finding_id"] == scenario
    assert result["verdict"] == "inconclusive"
    assert len({r.headers["X-Forwarded-For"] for r in requests}) == 1
    probes = [r for r in requests if not r.url.path.endswith("/register")]
    if scenario == "IB-PAYMENT-ANONYMOUS":
        assert len(requests) == 4
        assert all("Authorization" not in r.headers for r in probes)
    elif scenario == "IB-PAYMENT-AMOUNT":
        assert [json.loads(r.content)["amount"] for r in probes] == [0, -100000, 0.005]
        assert all(r.headers["Authorization"] == "Bearer token-1" for r in probes)
    elif scenario == "IB-AUTH-ID-MISMATCH":
        assert len(probes) == 1
        assert probes[0].headers["Authorization"] == "Bearer token-1"
        assert probes[0].headers["X-Auth-Id"] == "user-2"
    elif scenario == "IB-ADMIN-NON-ADMIN":
        assert [r.url.path for r in probes] == ["/api/v1/admin/users", "/bank-users"]
        assert all(r.headers["Authorization"] == "Bearer token-1" for r in probes)
    else:
        assert len(probes) == 12
        assert len({json.loads(r.content)["email"] for r in probes}) == 1
        assert all(r.url.path == "/api/v1/auth/login" for r in probes)
        assert all("Authorization" not in r.headers for r in probes)
        registered = json.loads(requests[0].content)
        assert all(json.loads(r.content)["password"] != registered["password"] for r in probes)
    assert len(result["evidence"]["responses"]) == len(probes)
    assert "token-" not in result["detail"]


def test_script_writes_compatible_report(tmp_path, monkeypatch):
    client, _ = client_and_requests()
    monkeypatch.setattr(signals.httpx, "Client", lambda **_: client)
    assert signals.main(["--target", "http://gateway", "--report-dir", str(tmp_path), "--only", signals.SCENARIOS[0]]) == 0
    report = json.loads((tmp_path / "dast-report.json").read_text())
    assert report["results"][0]["finding_id"] == signals.SCENARIOS[0]
    assert report["results"][0]["verdict"] == "inconclusive"


def test_script_setup_failure_has_no_success_report(tmp_path, monkeypatch):
    client, _ = client_and_requests(fail_registration=True)
    monkeypatch.setattr(signals.httpx, "Client", lambda **_: client)
    assert signals.main(["--target", "http://gateway", "--report-dir", str(tmp_path), "--only", "IB-FAILED-LOGINS"]) == 2
    assert not (tmp_path / "dast-report.json").exists()


def test_unknown_scenario_rejected():
    client, _ = client_and_requests()
    with client, pytest.raises(signals.SetupError):
        signals.run_scenario(client, "unknown")
