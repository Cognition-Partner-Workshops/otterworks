import importlib
import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import pytest

from integration.fixture.summary import summarize
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
