import importlib.util
import json
from pathlib import Path

import httpx
import pytest

SPEC = importlib.util.spec_from_file_location(
    "fineract_signals", Path(__file__).parents[1] / "attacks" / "fineract_signals.py"
)
signals = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(signals)


@pytest.mark.parametrize("scenario", signals.SCENARIOS)
def test_fineract_requests(scenario):
    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(404)
    with httpx.Client(base_url="http://gateway", transport=httpx.MockTransport(handle)) as client:
        result = signals.run_scenario(client, scenario)
    assert result["finding_id"] == scenario
    assert result["verdict"] == "inconclusive"
    assert all("Authorization" not in r.headers for r in requests)
    assert all(r["status"] == 404 for r in result["evidence"]["responses"])
    for prefix in signals.PREFIXES:
        if scenario == "FIN-MAKERCHECKER-REPEAT":
            matching = [r for r in requests if str(r.url).startswith("http://gateway"+prefix+"/makercheckers/")]
            assert len(matching) == 2 and matching[0].url == matching[1].url
            assert all(r.method == "POST" and r.url.params["command"] == "approve" for r in matching)
        elif scenario == "FIN-MAKERCHECKER-DISABLED":
            put = [r for r in requests if r.url.path == prefix+"/configurations/name/maker-checker" and r.method == "PUT"]
            assert len(put) == 1 and json.loads(put[0].content) == {"enabled": False}
            posts = [r for r in requests if r.method == "POST" and r.url.path in (prefix+"/configurations/1", prefix+"/configurations/name/maker-checker")]
            assert len(posts) == 2 and all(r.url.params["command"] == "disable" for r in posts)
        else:
            assert any(r.method == "POST" and r.url.path == prefix+"/datatables/deregister/detection-replay" for r in requests)
            assert any(r.method == "POST" and r.url.path == prefix+"/creditBureauIntegration/addCreditReport" for r in requests)


@pytest.mark.parametrize("fail", [False, True])
def test_fineract_report_or_transport_error(tmp_path, monkeypatch, fail):
    def handle(request):
        if fail:
            raise httpx.ConnectError("offline", request=request)
        return httpx.Response(404)
    client = httpx.Client(base_url="http://gateway", transport=httpx.MockTransport(handle))
    monkeypatch.setattr(signals.httpx, "Client", lambda **_: client)
    assert signals.main(["--target", "http://gateway", "--report-dir", str(tmp_path), "--only", signals.SCENARIOS[0]]) == (2 if fail else 0)
    report = tmp_path / "dast-report.json"
    assert report.exists() is not fail
    if not fail:
        assert json.loads(report.read_text())["results"][0]["finding_id"] == signals.SCENARIOS[0]


def test_fineract_empty_selection_and_unknown_scenario(tmp_path):
    with pytest.raises(SystemExit):
        signals.main(["--target", "http://gateway", "--report-dir", str(tmp_path)])
    with pytest.raises(ValueError):
        signals.run_scenario(None, "unknown")
