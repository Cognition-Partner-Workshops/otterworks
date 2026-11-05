"""Offline contracts: missing telemetry and stale sink pages never prove detection."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

SPEC = importlib.util.spec_from_file_location(
    "detection_replay", Path(__file__).parents[1] / "replay.py"
)
replay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(replay)


def group(state="inactive", health="ok"):
    return [
        {
            "rules": [
                {
                    "name": "Example",
                    "type": "alerting",
                    "state": state,
                    "health": health,
                    "alerts": [],
                }
            ]
        }
    ]


def test_manifest_and_command(tmp_path):
    classes = replay.load_classes()
    assert set(classes) == {
        "identity-forgery",
        "cross-customer-access",
        "credential-stuffing",
        "ib-payment-anonymous",
        "ib-payment-amount",
        "ib-auth-id-mismatch",
        "ib-admin-non-admin",
        "ib-failed-logins",
    }
    for spec in classes.values():
        command = replay.probe_command(spec, "http://localhost:8080", tmp_path)
        assert ("--no-baseline" in command) is ("attack_script" not in spec)
        if "attack_script" in spec:
            assert command[:3] == ["uv", "run", str(replay.attack_script(spec))]
        assert command.count("--only") == len(spec["findings"])
        assert str(tmp_path) in command


@pytest.mark.parametrize(
    "state,quiet,firing",
    [
        ("inactive", True, False),
        ("pending", False, False),
        ("firing", False, True),
    ],
)
def test_alert_states(state, quiet, firing):
    states = replay.alert_states(group(state), ["Example"])
    assert replay.is_quiet(states) is quiet
    assert replay.all_firing(states) is firing
    assert not replay.is_quiet({})
    assert not replay.all_firing({})


@pytest.mark.parametrize("groups", [[], group(health="err"), group() + group()])
def test_missing_unhealthy_duplicate_rules_fail_closed(groups):
    with pytest.raises(replay.SetupError):
        replay.alert_states(groups, ["Example"])


def delivery(
    received="2026-01-01T00:00:10Z", status="firing", attack_class="identity-forgery"
):
    return {
        "received_at": received,
        "payload": {
            "alerts": [
                {
                    "status": status,
                    "labels": {
                        "attack_class": attack_class,
                        "alertname": "Example",
                    },
                }
            ]
        },
    }


def test_delivery_requires_fresh_firing_matching_class():
    started = "2026-01-01T00:00:05+00:00"
    assert replay.delivered_alerts([delivery()], "identity-forgery", started) == {
        "Example"
    }
    for row in (
        delivery(received="2026-01-01T00:00:01Z"),
        delivery(status="resolved"),
        delivery(attack_class="other"),
    ):
        assert replay.delivered_alerts([row], "identity-forgery", started) == set()
    assert replay.delivered_alerts([], "identity-forgery", started) == set()


def test_probe_findings_are_data_not_a_failed_detection():
    report = {
        "results": [
            {
                "finding_id": "DAST-EXAMPLE",
                "verdict": "vulnerable",
                "detail": "planted",
                "evidence": {"secret": "must not be copied"},
            }
        ]
    }
    assert replay.probe_verdicts(report, ["DAST-EXAMPLE"]) == [
        {
            "finding_id": "DAST-EXAMPLE",
            "verdict": "vulnerable",
            "detail": "planted",
        }
    ]
    with pytest.raises(replay.SetupError):
        replay.probe_verdicts({"results": []}, ["DAST-EXAMPLE"])


def test_empty_counter_snapshot_fails_closed():
    def handle(request):
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [],
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(replay.SetupError):
            replay.snapshot(
                client, {"prometheus": "http://prom"}, {"counters": ["counter"]}
            )


@pytest.mark.parametrize(
    "alerts,quiet",
    [
        ([], True),
        ([{"labels": {"alertname": "Example"}}], False),
        ([{"labels": {"alertname": "Other"}}], True),
    ],
)
def test_alertmanager_class_quiet(alerts, quiet):
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=alerts))
    ) as client:
        assert (
            not replay.active_class_alerts(
                client, {"alertmanager": "http://am"}, {"alerts": ["Example"]}
            )
        ) is quiet


def test_alertmanager_bad_response_fails_closed():
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={}))
    ) as client:
        with pytest.raises(replay.SetupError):
            replay.active_class_alerts(
                client, {"alertmanager": "http://am"}, {"alerts": ["Example"]}
            )


@pytest.mark.parametrize(
    "scenario,expected",
    [
        ("pass", 0),
        ("not-quiet", 2),
        ("alertmanager-not-quiet", 2),
        ("not-settled", 2),
        ("no-fire", 1),
        ("no-delivery", 1),
        ("unreachable", 2),
        ("stale-delivery", 1),
        ("script-pass", 0),
        ("script-missing-report", 2),
        ("script-bad-exit", 2),
        ("script-bad-exit-three", 2),
        ("script-timeout", 2),
        ("script-bad-report", 2),
    ],
)
def test_replay_outcomes_offline(tmp_path, monkeypatch, scenario, expected):
    spec = {
        "alerts": ["Example"],
        "findings": ["DAST-EXAMPLE"],
        "counters": ["counter"],
        "quiet_budget_seconds": 1,
        "time_budget_seconds": 1,
        "probe_budget_seconds": 1,
    }
    if scenario.startswith("script-"):
        spec["attack_script"] = "security/detection/attacks/ib_signals.py"
    calls = 0

    def read_alerts(*args):
        nonlocal calls
        calls += 1
        if scenario == "unreachable":
            raise httpx.ConnectError("offline")
        if scenario == "not-quiet":
            return {"Example": {"state": "firing", "instances": []}}
        return {
            "Example": {
                "state": "inactive"
                if calls == 1 or scenario == "no-fire"
                else "firing",
                "instances": [{"activeAt": "2026-01-01T00:00:00Z"}],
            }
        }

    monkeypatch.setattr(replay, "read_alerts", read_alerts)
    monkeypatch.setattr(
        replay, "ALERTMANAGER_SETTLE_SECONDS", 60 if scenario == "not-settled" else 0
    )
    monkeypatch.setattr(
        replay,
        "active_class_alerts",
        lambda *a: (
            [{"labels": {"alertname": "Example"}}]
            if scenario == "alertmanager-not-quiet"
            else []
        ),
    )
    monkeypatch.setattr(replay, "snapshot", lambda *a: {"counters": {"counter": []}})
    monkeypatch.setattr(replay, "now", lambda: "2026-01-01T00:00:05+00:00")
    clock = iter(range(1000))
    monkeypatch.setattr(replay.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(replay.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        httpx.Client,
        "get",
        lambda *a, **k: SimpleNamespace(raise_for_status=lambda: None),
    )
    deliveries = 0

    def records(*args):
        nonlocal deliveries
        deliveries += 1
        if scenario == "stale-delivery":
            return [delivery()]
        return [] if deliveries == 1 or scenario == "no-delivery" else [delivery()]

    monkeypatch.setattr(replay, "sink_records", records)

    def run(command, **kwargs):
        assert kwargs["timeout"] == spec["probe_budget_seconds"]
        if scenario == "script-timeout":
            raise replay.subprocess.TimeoutExpired(command, kwargs["timeout"])
        if scenario in ("script-missing-report", "script-bad-exit", "script-bad-exit-three"):
            code = {"script-missing-report": 0, "script-bad-exit": 2, "script-bad-exit-three": 3}[scenario]
            return SimpleNamespace(returncode=code, stdout="", stderr="")
        out = Path(command[command.index("--report-dir") + 1])
        out.mkdir(parents=True)
        (out / "dast-report.json").write_text(
            json.dumps(
                {
                    "results": [
                        {
                            "finding_id": "DAST-EXAMPLE",
                            "verdict": "vulnerable",
                            "detail": "planted",
                        }
                    ]
                }
            )
        )
        if scenario == "script-bad-report":
            (out / "dast-report.json").write_text('{"results":[]}')
        return SimpleNamespace(returncode=0 if scenario.startswith("script-") else 1, stdout="", stderr="")

    monkeypatch.setattr(replay.subprocess, "run", run)
    urls = {
        key: "http://example"
        for key in ("gateway", "prometheus", "alertmanager", "sink")
    }
    assert replay.replay("identity-forgery", spec, urls, tmp_path) == expected
    report = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert report["exit_code"] == expected
    assert next(tmp_path.glob("*.md")).is_file()


def test_bad_url_rejected(monkeypatch):
    monkeypatch.setenv("DETECT_GATEWAY_URL", "http://user:password@example")
    with pytest.raises(replay.SetupError):
        replay.service_urls()


@pytest.mark.parametrize("path", [None, "", "/etc/passwd", "../../etc/passwd", "security/dast/harness/dast_scan.py", "security/detection/attacks/missing.py"])
def test_attack_script_path_rejected(path):
    with pytest.raises(replay.SetupError):
        replay.attack_script({"attack_script": path})


def test_shared_login_rule_delivery_label():
    spec = replay.load_classes()["ib-failed-logins"]
    assert spec["alerts"] == ["SecurityLoginFailureBurst"]
    assert replay.delivered_alerts(
        [delivery(attack_class=spec["alert_attack_class"])],
        spec["alert_attack_class"], "2026-01-01T00:00:05+00:00"
    ) == {"Example"}
