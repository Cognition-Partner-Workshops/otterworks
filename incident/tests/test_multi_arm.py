"""Concurrent arming keeps single-scenario state and load isolation."""

import argparse

import pytest
from test_error_ratio import incident


@pytest.fixture
def harness(monkeypatch, tmp_path):
    monkeypatch.setattr(incident, "STATE_DIR", tmp_path)
    cat = incident.load_catalog()
    calls = []
    for symbol in ("wait_healthy", "wait_alert_inactive"):
        monkeypatch.setattr(incident, symbol, lambda *args: None)
    monkeypatch.setattr(incident, "run_step", lambda cat, name, step: calls.append((name, step)))
    monkeypatch.setattr(incident, "git_sha", lambda: "test")
    monkeypatch.setattr(incident, "fingerprints", lambda: {})
    monkeypatch.setattr(incident, "load_scale", lambda: 1)
    async def seed(cat):
        calls.append(("shared", "seed"))
    monkeypatch.setattr(incident, "seed", seed)
    return cat, calls


def test_single_then_add_and_disarm(harness, monkeypatch):
    cat, calls = harness
    incident.cmd_arm(argparse.Namespace(scenario="n-plus-one"))
    assert incident.read_state()["scenario"] == "n-plus-one"
    incident.cmd_arm(argparse.Namespace(scenario="cache-leak,log-flood"))
    assert set(incident.read_state()["scenarios"]) == {"n-plus-one", "cache-leak", "log-flood"}
    calls.clear()
    monkeypatch.setattr(incident.httpx, "delete", lambda *args, **kwargs: None)
    incident.cmd_disarm(argparse.Namespace())
    assert calls == [(name, step) for name in ("n-plus-one", "cache-leak", "log-flood")
                     for step in cat["scenarios"][name]["disarm"]]
    assert incident.read_state() == {}


def test_all_and_invalid(harness):
    cat, calls = harness
    with pytest.raises(SystemExit):
        incident.cmd_arm(argparse.Namespace(scenario="n-plus-one,missing"))
    assert calls == []
    assert incident.read_state() == {}
    incident.cmd_arm(argparse.Namespace(scenario="all"))
    assert set(incident.read_state()["scenarios"]) == set(cat["scenarios"])
    assert calls.count(("shared", "seed")) == 1
    first_load = next(i for i, (_, step) in enumerate(calls)
                      if incident._step_parts(step)[0] == "load")
    assert all(incident._step_parts(step)[0] == "load" for _, step in calls[first_load:])


def test_load_start_stops_only_same_scenario(harness, monkeypatch):
    stopped = []
    monkeypatch.setattr(incident, "stop_background_load", stopped.append)
    monkeypatch.setattr(
        incident.subprocess, "Popen", lambda *args, **kwargs: argparse.Namespace(pid=123)
    )
    incident.start_background_load("n-plus-one")
    incident.start_background_load("cache-leak")
    assert stopped == ["n-plus-one", "cache-leak"]
    assert incident.state_path("load-n-plus-one.pid").read_text() == "123"
    assert incident.state_path("load-cache-leak.pid").read_text() == "123"
