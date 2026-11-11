import importlib
import json
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from integration.fixture.summary import summarize
from integration.fixture.reconcile import BROKER_IMAGE, artemis, reconcile
from integration.fixture.smoke import create
from integration.harness.faults import FaultHook
from integration.harness.fingerprints import verify_lock
from integration.harness.runner import load_corpus

ROOT = Path(__file__).resolve().parents[3]
LEGACY = ROOT / "integration/legacy-bw6"
CORPUS = ROOT / "integration/corpus"
REFERENCE = importlib.import_module("integration.legacy-bw6.reference.record")


def fixture(name):
    return json.loads((CORPUS / name / "flow.json").read_text())


def test_frozen_estate_shape_and_provenance():
    config, flows, lock = load_corpus(CORPUS)
    assert config["broker"]["url_env"] == "REPLAY_BROKER_URL"
    assert lock == verify_lock(CORPUS)
    assert len(flows) == 24
    processes = list((LEGACY / "Processes").glob("*/*.bwp"))
    assert Counter(p.parent.name for p in processes) == {
        "payments": 6, "account-events": 5, "fees-billing": 4,
        "statements-documents": 5, "customer-alerts": 4}
    assert json.loads((CORPUS / "source-hashes.json").read_text()) == REFERENCE.source_hashes()
    for _, flow in flows:
        assert set(flow["expected"]) == {"messages", "db", "files"}
        assert flow["expected"]["messages"]
        assert flow["inputs"]["messages"] or flow["inputs"]["files"]
    for source in processes:
        root = ET.parse(source).getroot()
        for node in root.iter():
            if "location" in node.attrib:
                assert (source.parent / node.attrib["location"]).is_file()
    for stylesheet in (LEGACY / "Transforms").rglob("*.xsl"):
        for node in ET.parse(stylesheet).getroot():
            if node.tag.endswith("}import"):
                assert (stylesheet.parent / node.attrib["href"]).is_file()


def test_static_cache_second_rate_does_not_replace_first():
    flow = fixture("fees-billing.daily-fee")
    requests = [ET.fromstring(m["body"]) for m in flow["inputs"]["messages"]]
    assert requests[0].get("rate") != requests[1].get("rate")
    assert [m["body"].split("|")[4] for m in flow["expected"]["messages"]] == ["15.00"] * 3


def test_channel_rounding_disagreement_is_preserved():
    flow = fixture("fees-billing.month-end-summary")
    requests = [ET.fromstring(m["body"]) for m in flow["inputs"]["messages"]]
    assert requests[0].get("amount") == requests[1].get("amount") == "2.345"
    assert [r.get("channel") for r in requests[:2]] == ["XSLT", "JAVA"]
    assert [m["body"].split("|")[4] for m in flow["expected"]["messages"][:2]] == ["2.35", "2.34"]


def test_import_precedence_timezone_and_selector():
    assert "ACCEPTED_RETAIL" in fixture("payments.status-update")["expected"]["messages"][0]["body"]
    dates = fixture("statements-documents.statement-drop")
    assert dates["inputs"]["files"] and not dates["inputs"]["messages"]
    assert all(m["body"].endswith("2026-03-29T00:30:00Z") for m in dates["expected"]["messages"])
    selected = fixture("customer-alerts.low-balance")
    assert len(selected["inputs"]["messages"]) == 3
    assert len(selected["expected"]["messages"]) == 2
    assert selected["inputs"]["messages"][2]["properties"]["customerType"] != "RETAIL"


def test_transaction_durable_ordering_and_poison_evidence():
    xa = fixture("payments.instruction-intake")
    assert set(xa["expected"]["db"]) == {"payment_inbox", "payment_ledger"}
    assert "XA" in (LEGACY / "Processes/payments/instruction-intake.bwp").read_text()
    durable = fixture("account-events.event-fanout")["faults"]["consumer-restart"]
    assert durable["durable_subscription"] == "records-event-fanout"
    ordered = fixture("account-events.limit-changed")
    assert ordered["faults"]["ordering"]["parallel_consumers"] == 2
    assert len({m["properties"]["JMSXGroupID"] for m in ordered["inputs"]["messages"]}) == 2
    poison = fixture("customer-alerts.card-dispute")
    attempts = [m["headers"]["deliveryCount"] for m in poison["expected"]["messages"]
                if m["destination"] == "HB.DELIVERY.AUDIT"]
    assert attempts == ["1", "2", "3", "4"]
    assert sum(m["destination"] == "HB.UNDLV" for m in poison["expected"]["messages"]) == 1


def test_profile_difference_and_orphan():
    assert "/v1/screen" in (LEGACY / "Profiles/dev.substvar").read_text()
    assert "/v2/screen" in (LEGACY / "Profiles/prod.substvar").read_text()
    assert not any("<processName>fees-billing.month-end-summary</processName>" in p.read_text()
                   for p in (LEGACY / "Processes").rglob("*.bwp"))


def test_record_refuses_empty_reason(tmp_path):
    with pytest.raises(ValueError, match="reason"):
        REFERENCE.record(tmp_path, " ")


def test_smoke_corpus_is_locked_and_ignores_only_transaction_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("REPLAY_BROKER_CONTAINER", "isolated-broker")
    create(tmp_path)
    config, flows, _ = load_corpus(tmp_path)
    assert "/messages/*/headers/transaction" in config["ignore"]
    assert "/messages/*/headers/requestId" not in config["ignore"]
    assert len(flows) == 1
    assert len(flows[0][1]["expected"]["messages"]) == 5


def test_smoke_refuses_missing_broker_container(tmp_path, monkeypatch):
    monkeypatch.delenv("REPLAY_BROKER_CONTAINER", raising=False)
    with pytest.raises(KeyError):
        create(tmp_path)


def test_fault_container_from_environment(monkeypatch):
    monkeypatch.setenv("FIXTURE_CONTAINER", "isolated-broker")
    hook = FaultHook("broker-kill", {"container_env": "FIXTURE_CONTAINER", "after_message": 1}, None, 2)
    assert hook.spec["container"] == "isolated-broker"
    monkeypatch.delenv("FIXTURE_CONTAINER")
    with pytest.raises(KeyError):
        FaultHook("broker-kill", {"container_env": "FIXTURE_CONTAINER", "after_message": 1}, None, 2)


@pytest.mark.parametrize("rows", [[], [{"status": "error", "matched": 0}],
                                  [{"status": "matched", "matched": 1}]])
def test_summary_refuses_nonbaseline(tmp_path, rows):
    report = tmp_path / "parity.json"
    report.write_text(json.dumps({"flows": [{"flow": "test", "replayed": 1, "differing": 1, **r} for r in rows]}))
    with pytest.raises(SystemExit, match="24 differing"):
        summarize(report, expect_empty=True)


def test_summary_accepts_exact_red_baseline(tmp_path, capsys):
    report = tmp_path / "parity.json"
    report.write_text(json.dumps({"flows": [{"flow": str(n), "status": "differing", "matched": 0,
                                             "replayed": 2, "differing": 2} for n in range(24)]}))
    summarize(report, expect_empty=True)
    assert "24 flows; 0 matched; 24 differing; 0 errors" in capsys.readouterr().out


def test_topic_addresses_create_multicast_subscription_queues():
    ns = {"a": "urn:activemq:core"}
    core = ET.parse(ROOT / "integration/fixture/broker.xml").getroot().find("a:core", ns)
    topics = {a.get("name") for a in core.findall("a:addresses/a:address", ns)
              if a.find("a:multicast", ns) is not None and a.find("a:anycast", ns) is None}
    routing = {s.get("match"): s.findtext("a:default-queue-routing-type", namespaces=ns)
               for s in core.findall("a:address-settings/a:address-setting", ns)}
    assert topics
    assert {t: routing.get(t) for t in topics} == {t: "MULTICAST" for t in topics}


def test_reconcile_converts_only_anycast_queues_and_routing_on_topics(capsys):
    def queue(name, address, routing, count="0"):
        return {"name": name, "address": address, "routingType": routing, "messageCount": count}
    stat = [queue("replay-observer.replay-account-evidence", "HB.ACCOUNT.EVENTS", "ANYCAST", "3"),
            queue("records-event-fanout", "HB.ACCOUNT.EVENTS.IN", "MULTICAST"),
            queue("HB.UNDLV", "HB.UNDLV", "ANYCAST")]
    calls = []

    def run(container, *args):
        calls.append(args)
        if args[:2] == ("queue", "stat"):
            return "Connection brokerURL = tcp://localhost:61616\n" + json.dumps({"data": stat})
        if args[:2] == ("address", "show"):
            types = "MULTICAST,ANYCAST" if args[3] == "HB.ACCOUNT.EVENTS" else "MULTICAST"
            return f"Address [name={args[3]}, routingTypes={{{types}}}, autoCreated=false]"
        return ""

    assert reconcile("isolated-broker", run, ROOT / "integration/fixture/broker.xml") == (
        ["replay-observer.replay-account-evidence"], ["HB.ACCOUNT.EVENTS"])
    changes = [c for c in calls if c[1] == "update"]
    assert changes == [("queue", "update", "--name", "replay-observer.replay-account-evidence",
                        "--address", "HB.ACCOUNT.EVENTS", "--multicast", "--silent"),
                       ("address", "update", "--name", "HB.ACCOUNT.EVENTS", "--multicast", "--no-anycast")]
    assert "HB.UNDLV" not in {c[3] for c in calls if c[0] == "address"}
    assert "3 messages kept" in capsys.readouterr().out


def test_reconcile_cli_runs_outside_the_broker_memory_limit(monkeypatch):
    seen = []
    monkeypatch.setenv("REPLAY_BROKER_USER", "replay")
    monkeypatch.setenv("REPLAY_BROKER_PASSWORD", "secret")
    monkeypatch.setattr(subprocess, "run", lambda command, **_: seen.append(command) or SimpleNamespace(stdout="ok"))
    assert artemis("isolated-broker", "queue", "stat") == "ok"
    assert seen[0][:8] == ["docker", "run", "--rm", "--network", "container:isolated-broker",
                           "--entrypoint", "/opt/activemq-artemis/bin/artemis", BROKER_IMAGE]
    broker = yaml.safe_load((ROOT / "docker-compose.tibco.yml").read_text())["services"]["broker"]
    assert broker["image"] == BROKER_IMAGE


def test_broker_resyncs_fixture_config_on_existing_volume():
    broker = yaml.safe_load((ROOT / "docker-compose.tibco.yml").read_text())["services"]["broker"]
    assert "cp etc-override/broker.xml etc/broker.xml" in broker["entrypoint"][2]
    assert broker["command"] == ["run"]
