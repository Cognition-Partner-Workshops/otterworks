"""Concurrent arming keeps single-scenario state and load isolation."""

import argparse
import signal

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
    monkeypatch.setattr(incident, "_start_storm", lambda *args: calls.append(("storm", args[1:])))
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
    assert calls[-1] == ("storm", (list(cat["scenarios"]), ["cache-leak"], ["log-flood"]))
    assert all(incident._step_parts(step)[0] not in {"load", "memory-limit"}
               for _, step in calls[:-1])
    assert ("log-flood", {"flag": "chaos:document-service:request_log"}) not in calls


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


def test_stopping_all_loads_signals_together_and_handles_missing_or_empty(harness, monkeypatch):
    calls = []
    for name, pid in (("n-plus-one", 100), ("cache-leak", 101), ("log-flood", 999)):
        incident.state_path(f"load-{name}.pid").write_text(str(pid))

    def killpg(pid, sig):
        calls.append((pid, sig))
        if pid == 999:
            raise ProcessLookupError

    clock = iter((0, 0, 11))
    monkeypatch.setattr(incident.os, "killpg", killpg)
    monkeypatch.setattr(incident.time, "monotonic", lambda: next(clock, 12))
    monkeypatch.setattr(incident.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(incident, "_pid_alive", lambda pid: True)
    incident.stop_background_load()
    assert {pid for pid, sig in calls[:3] if sig == signal.SIGTERM} == {100, 101, 999}
    assert {pid for pid, sig in calls[3:] if sig == signal.SIGKILL} == {100, 101}
    assert list(incident.STATE_DIR.glob("load*.pid")) == []
    calls.clear()
    incident.stop_background_load()
    assert calls == []


@pytest.mark.parametrize(("rss", "usage"), [(320, 384), (400, 470)])
def test_storm_memory_ceiling_keeps_real_usage_headroom(rss, usage):
    mib = 1024**2
    ceiling = incident.storm_memory_ceiling(rss * mib, usage * mib)
    assert ceiling >= (usage + 16) * mib
    assert rss * mib / ceiling > 0.75


@pytest.mark.parametrize(("rss", "usage"), [(0, 100), (100, 300)])
def test_storm_memory_ceiling_rejects_unsafe_or_empty_samples(rss, usage):
    with pytest.raises(SystemExit):
        incident.storm_memory_ceiling(rss * 1024**2, usage * 1024**2)


def test_storm_wait_requires_firing_and_handles_empty_or_timeout(monkeypatch):
    cat = incident.load_catalog()
    slept = []
    monkeypatch.setattr(incident.time, "sleep", slept.append)
    monkeypatch.setattr(incident, "prom_alerts", lambda cat: [
        {"state": "firing", "labels": {"alertname": "DocumentListLatencyHigh"}},
    ])
    incident._wait_storm_pages(cat, [])
    assert slept == []
    incident._wait_storm_pages(cat, ["n-plus-one"])
    assert slept == [15]
    with pytest.raises(SystemExit):
        incident._wait_storm_pages(cat, ["cache-leak"], timeout=0)


def test_storm_stages_logging_after_other_pages_and_freezes_before_lowering(monkeypatch):
    cat = incident.load_catalog()
    calls = []
    monkeypatch.setattr(incident, "load_scale", lambda: 1)
    monkeypatch.setattr(incident.time, "sleep", lambda seconds: calls.append(("sleep", seconds)))
    monkeypatch.setattr(incident, "recreate_document_service", lambda *args: calls.append("warm"))
    monkeypatch.setattr(incident, "start_background_load", lambda name, **kw: calls.append(name))
    monkeypatch.setattr(incident, "stop_background_load", lambda: calls.append("freeze"))
    monkeypatch.setattr(incident, "run_step", lambda cat, name, step: calls.append((name, step)))
    monkeypatch.setattr(incident, "_wait_storm_pages", lambda cat, names, **kw: calls.append(names))
    monkeypatch.setattr(incident, "compose", lambda *args, **kw: argparse.Namespace(
        stdout=str(320 * 1024**2)))
    monkeypatch.setattr(incident, "container_id", lambda service: "container")
    monkeypatch.setattr(incident, "sh", lambda *args: calls.append(args))
    incident._start_storm(cat, list(cat["scenarios"]), ["cache-leak"], ["log-flood"])
    assert calls[:5] == ["warm", "cache-leak", ("sleep", 30), "n-plus-one",
                         ["n-plus-one", "double-run"]]
    assert calls[5:10] == [("log-flood", {"flag": "chaos:document-service:request_log"}),
                          "log-flood", ["log-flood"], "freeze", ("sleep", 10)]
    assert calls[10][0:3] == ("docker", "update", "--memory")
    assert calls[11] == ["cache-leak"]
