import base64
import json
import sys
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace

import pytest

from integration.harness.__main__ import main
from integration.harness.diffing import differences
from integration.harness.faults import FaultHook, docker, fault_result
from integration.harness.fingerprints import record_lock, verify_lock
from integration.harness.report import write_report
from integration.harness.runner import replay, replay_flow
from integration.harness.transports import Broker, Resources, normalized, remote_path, safe_path


def message(identity="a", key="x", seq="1", destination="out"):
    return {"destination": destination, "body": "body",
            "headers": {"id": identity, "key": key, "seq": seq}}


class FakeBroker:
    output = []

    def __init__(self, config, captures):
        self.sent = []
        self.closed = False

    def open(self):
        pass

    def send(self, item):
        self.sent.append(item)

    def snapshot(self):
        return deepcopy(self.output)

    def reconnect(self):
        pass

    def close(self):
        self.closed = True


class FakeResources:
    def __init__(self, config):
        self.dropped = []

    def drop(self, item):
        self.dropped.append(item)

    def database(self, tables):
        return {name: [{"value": "1.20"}] for name in tables}

    def files(self, spec):
        return {"output.txt": "b2s="} if spec else {}


def flow():
    return {"inputs": {"messages": [message(), message("b")],
                       "files": [{"path": "input.txt", "base64": "b2s="}]},
            "capture_seconds": 0,
            "capture": {"db": {"rows": {"query": "select value from rows order by id"}},
                        "files": {"transport": "directory", "root": "/unused"}},
            "expected": {"messages": [], "db": {"rows": [{"value": "1.20"}]},
                         "files": {"output.txt": "b2s="}}}


@pytest.mark.parametrize("expected,actual,reason", [
    ({"x": 1}, {"x": 2}, "value"), ({"x": 1}, {}, "missing"),
    ({}, {"x": 1}, "unexpected"), ([1], [], "missing"),
    ([], [1], "unexpected"), (True, 1, "type"), (1, "1", "type"),
])
def test_differences(expected, actual, reason):
    assert differences(expected, actual)[0]["reason"] == reason


def test_nested_ignore():
    expected = {"messages": [{"headers": {"id": "old"}, "body": "a"}]}
    actual = {"messages": [{"headers": {"id": "new", "timestamp": "now"}, "body": "a"}]}
    assert differences(expected, actual, ["/messages/*/headers/id", "/messages/*/headers/timestamp"]) == []
    actual["messages"][0]["body"] = "b"
    assert differences(expected, actual, ["/messages/*/headers/*"])[0]["path"] == "/messages/0/body"
    assert differences({}, {}) == []
    assert differences([], []) == []
    assert differences([1, 2], [2, 1])


@pytest.fixture
def corpus(tmp_path):
    root = tmp_path / "corpus"
    root.mkdir()
    (root / "sample").mkdir()
    (root / "sample" / "flow.json").write_text(json.dumps(flow()))
    (root / "destinations.yaml").write_text("ignore: []\n")
    record_lock(root, "initial reference capture")
    return root


@pytest.mark.parametrize("mutation", ["change", "add", "remove"])
def test_lock_refuses_mutations(corpus, mutation):
    path = corpus / "sample" / "flow.json"
    if mutation == "change":
        path.write_text("{}")
    elif mutation == "remove":
        path.unlink()
    else:
        (corpus / "extra").write_text("new")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_lock(corpus)
    with pytest.raises(ValueError, match="hash mismatch"):
        replay(corpus, broker_factory=lambda *_: pytest.fail("Transport opened before lock check"))


def test_lock_audit_and_reason(corpus):
    original = verify_lock(corpus)
    with pytest.raises(ValueError, match="reason"):
        record_lock(corpus, " ")
    (corpus / "sample" / "extra").write_text("changed")
    record_lock(corpus, "approved reference update")
    current = verify_lock(corpus)
    assert len(current["history"]) == 2
    assert current["history"][-1]["previous_files"] == original["files"]


def test_empty_and_symlink_lock(tmp_path):
    with pytest.raises(ValueError, match="Empty"):
        record_lock(tmp_path, "initial")
    (tmp_path / "link").symlink_to("/etc/hosts")
    with pytest.raises(ValueError, match="symlink"):
        record_lock(tmp_path, "initial")


def test_replay_all_channels(corpus):
    result = replay(corpus, broker_factory=FakeBroker, resource_factory=FakeResources, sleep=lambda _: None)
    row = result["flows"][0]
    assert row["status"] == "matched"
    assert row["replayed"] == 3
    assert row["actual"]["db"] == flow()["expected"]["db"]
    with pytest.raises(ValueError, match="Unknown flow"):
        replay(corpus, ["absent"])


def test_replay_counts_and_error():
    class Captured(FakeBroker):
        output = [message(), message("extra")]
    sample = flow()
    sample["expected"]["messages"] = [message()]
    result = replay_flow("sample", sample, {}, broker_factory=Captured,
                         resource_factory=FakeResources, sleep=lambda _: None)
    assert (result["matched"], result["differing"], result["status"]) == (1, 1, "differing")

    class Broken(FakeBroker):
        def send(self, item):
            raise RuntimeError("secret connection string")
    result = replay_flow("sample", sample, {}, broker_factory=Broken, resource_factory=FakeResources)
    assert result["status"] == "error"
    assert "secret" not in json.dumps(result)
    assert "RuntimeError" in result["differences"][0]["reason"]


def test_empty_replay():
    result = replay_flow("empty", {"expected": {"messages": [], "db": {}, "files": {}},
                                   "capture_seconds": 0}, {}, broker_factory=FakeBroker,
                         resource_factory=FakeResources, sleep=lambda _: None)
    assert result["status"] == "matched"
    assert result["replayed"] == 0


@pytest.mark.parametrize("test,stop", [("broker-kill", "kill"), ("consumer-restart", "stop")])
def test_fault_lifecycle(test, stop):
    calls = []
    spec = {"container": "isolated-container", "after_message": 1, "restart_after": 3}
    hook = FaultHook(test, spec, FakeBroker({}, []), 4,
                     control=lambda *args: calls.append(args), sleep=lambda _: None)
    for count in range(1, 5):
        hook.after_message(count)
    hook.restore()
    assert calls == [(stop, "isolated-container"), ("start", "isolated-container")]
    assert hook.events[0]["published"] == 1


def test_restore_after_publish_failure():
    calls = []
    hook = FaultHook("consumer-restart", {"container": "c", "after_message": 1, "restart_after": 3},
                     FakeBroker({}, []), 3, control=lambda *args: calls.append(args))
    hook.after_message(1)
    hook.restore()
    assert calls == [("stop", "c"), ("start", "c")]
    with pytest.raises(ValueError):
        FaultHook("broker-kill", {"after_message": 3}, FakeBroker({}, []), 3)


@pytest.mark.parametrize("test", ["broker-kill", "consumer-restart"])
def test_loss_duplicate_results(test):
    spec = {"identity_header": "id", "topic": "topic", "durable_subscription": "stable",
            "published": [message(destination="topic")]}
    events = [{"action": "kill" if test == "broker-kill" else "stop"}, {"action": "start"}]
    expected = [message(), message("b")]
    assert fault_result(test, spec, expected, expected, events)["status"] == "passed"
    for actual in ([], [message()], expected + [message()]):
        assert fault_result(test, spec, expected, actual, events)["status"] == "failed"
    assert fault_result(test, spec, [], [], events)["status"] == "failed"
    assert fault_result(test, spec, expected, expected, [])["status"] == "failed"
    blank = [dict(message(), headers={"id": ""})]
    assert fault_result(test, spec, blank, blank, events)["status"] == "failed"


def test_poison_result():
    spec = {"identity_header": "id", "identity": "a", "audit_destination": "audit",
            "delivery_count_header": "count", "redeliveries": 3, "dlq": "dead"}
    actual = [dict(message(destination="audit"), headers={"id": "a", "count": str(n)})
              for n in range(1, 5)] + [message(destination="dead")]
    result = fault_result("poison", spec, [], actual, [])
    assert result["status"] == "passed"
    assert result["evidence"]["delivery_counts"] == [1, 2, 3, 4]
    assert fault_result("poison", spec, [], actual[:-1], [])["status"] == "failed"
    assert fault_result("poison", spec, [], actual[1:], [])["status"] == "failed"
    assert fault_result("poison", spec, [], [], [])["status"] == "failed"


def test_ordering_results():
    spec = {"key_header": "key", "sequence_header": "seq", "parallel_consumers": 2}
    expected = [message(), message("b", seq="2"), message("c", key="y")]
    assert fault_result("ordering", spec, expected, [expected[2], *expected[:2]], [])["status"] == "passed"
    assert fault_result("ordering", spec, expected, list(reversed(expected)), [])["status"] == "failed"
    assert fault_result("ordering", spec, [], [], [])["status"] == "failed"
    assert fault_result("ordering", {}, expected, expected, [])["status"] == "failed"


def test_fault_replay_with_fake_hook():
    class Captured(FakeBroker):
        output = [message(), message("b")]
    sample = flow()
    sample["expected"]["messages"] = Captured.output
    sample["faults"] = {"broker-kill": {"identity_header": "id", "after_message": 1, "container": "c"}}

    def hook(*args):
        return FaultHook(*args, control=lambda *_: None, sleep=lambda _: None)
    result = replay_flow("sample", sample, {}, "broker-kill", Captured, FakeResources,
                         lambda _: None, hook)
    assert result["status"] == "matched"
    assert result["faults"][0]["status"] == "passed"


def test_report_and_cli(corpus, tmp_path):
    directory = tmp_path / "reports"
    result = {"flows": [{"flow": "<script>|bad", "replayed": 0, "matched": 0,
                         "differing": 1, "status": "differing", "differences": [{"reason": "body mismatch"}]}]}
    write_report(result, directory)
    assert json.loads((directory / "parity.json").read_text()) == result
    assert "<script>" not in (directory / "parity.html").read_text()
    assert "body mismatch" in (directory / "parity.md").read_text()
    assert main(["report", "--input", str(directory / "parity.json"), "--report-dir", str(directory)]) == 1
    assert main(["verify-lock", "--corpus", str(corpus)]) == 0
    assert main(["replay", "--corpus", str(corpus), "--report-dir", str(corpus / "reports")]) == 2
    (corpus / "new").write_text("drift")
    assert main(["verify-lock", "--corpus", str(corpus)]) == 2
    assert main(["record-lock", "--corpus", str(corpus), "--reason", "approved change"]) == 0
    write_report({"flows": []}, directory)
    assert "<table>" in (directory / "parity.html").read_text()
    assert main(["report", "--input", str(directory / "parity.json"), "--report-dir", str(corpus / "out")]) == 2
    assert main(["verify-lock", "--corpus", str(corpus)]) == 0


def test_cli_report_permission_names_operation_without_exception_details(tmp_path, monkeypatch, capsys):
    source = tmp_path / "input.json"
    source.write_text('{"flows": []}')
    destination = tmp_path / "reports"

    def denied(*args):
        raise PermissionError("password=do-not-log")

    monkeypatch.setattr("integration.harness.__main__.write_report", denied)
    assert main(["report", "--input", str(source), "--report-dir", str(destination)]) == 2
    error = capsys.readouterr().err
    assert f"write reports in {str(destination)!r} (PermissionError)" in error
    assert "do-not-log" not in error


def test_cli_missing_input_names_read_path(tmp_path, capsys):
    source = tmp_path / "missing.json"
    assert main(["report", "--input", str(source), "--report-dir", str(tmp_path / "out")]) == 2
    assert f"read report {str(source)!r} (FileNotFoundError)" in capsys.readouterr().err


def test_cli_missing_lock_names_corpus_path(tmp_path, capsys):
    assert main(["verify-lock", "--corpus", str(tmp_path)]) == 2
    assert f"verify-lock corpus {str(tmp_path)!r} (FileNotFoundError)" in capsys.readouterr().err


def test_sftp_open_failure_closes_client(monkeypatch):
    closed = []

    class Client:
        def load_system_host_keys(self): pass
        def connect(self, *args, **kwargs): pass
        def open_sftp(self): raise OSError("subsystem refused")
        def close(self): closed.append(True)
    monkeypatch.setitem(sys.modules, "paramiko", SimpleNamespace(SSHClient=Client))
    resources = Resources({"sftp": {"host": "h", "input_root": "/in"}})
    with pytest.raises(OSError):
        resources._sftp()
    assert closed == [True]


def test_files_normalization_and_path_safety(tmp_path):
    (tmp_path / "result").write_bytes(b"\x00\xff")
    assert Resources({}).files({"transport": "directory", "root": str(tmp_path)}) == {
        "result": base64.b64encode(b"\x00\xff").decode()}
    assert normalized({"amount": Decimal("1.20")}) == {"amount": "1.20"}
    assert safe_path(tmp_path, "result") == tmp_path / "result"
    assert remote_path("/upload", "nested/file") == "/upload/nested/file"
    for path in ("../escape", "/absolute"):
        with pytest.raises(ValueError):
            safe_path(tmp_path, path)
        with pytest.raises(ValueError):
            remote_path("/upload", path)
    (tmp_path / "link").symlink_to("/etc/hosts")
    with pytest.raises(ValueError, match="symlink"):
        Resources({}).files({"transport": "directory", "root": str(tmp_path)})


def test_docker_command(monkeypatch):
    calls = []
    monkeypatch.setattr("integration.harness.faults.subprocess.run", lambda *a, **k: calls.append((a, k)))
    docker("kill", "isolated")
    assert calls[0][0][0] == ["docker", "kill", "isolated"]
    with pytest.raises(ValueError):
        docker("kill", "--all")


def test_stomp_capture_properties_and_receipts(monkeypatch):
    connections = []

    class Connection:
        def __init__(self, hosts, heartbeats):
            self.connected = False
            self.subscriptions = []
            self.sent = []
            connections.append(self)

        def set_listener(self, name, listener):
            self.listener = listener

        def connect(self, username, password, wait, headers):
            self.connected = True
            self.connect_headers = headers

        def subscribe(self, **kwargs):
            self.subscriptions.append(kwargs)
            self.listener.on_receipt(SimpleNamespace(headers={"receipt-id": kwargs["headers"]["receipt"]}))

        def send(self, **kwargs):
            self.sent.append(kwargs)
            self.listener.on_receipt(SimpleNamespace(headers={"receipt-id": kwargs["headers"]["receipt"]}))

        def is_connected(self):
            return self.connected

        def disconnect(self):
            self.connected = False

    monkeypatch.setitem(sys.modules, "stomp", SimpleNamespace(Connection12=Connection, ConnectionListener=object))
    broker = Broker({"url": "stomp://localhost:61613", "client_id": "observer", "receipt_timeout": 0.01},
                    [{"id": "out", "destination": "topic", "headers": {"durable-subscription-name": "evidence"}}])
    broker.open()
    broker.send({"body": "payload €", "destination": "input", "properties": {"region": "west"},
                 "headers": {"correlation-id": "r1"}})
    sent = connections[1].sent[0]
    assert sent["body"] == "payload €"
    assert sent["headers"]["content-length"] == len("payload €".encode("utf-8"))
    assert sent["headers"]["persistent"] == "true"
    assert sent["headers"]["region"] == "west"
    assert sent["headers"]["correlation-id"] == "r1"
    assert connections[0].connect_headers == {"client-id": "observer"}
    assert connections[0].subscriptions[0]["headers"]["durable-subscription-name"] == "evidence"
    connections[0].listener.on_message(SimpleNamespace(
        body="reply", headers={"subscription": "out", "message-id": "generated", "region": "west"}))
    assert broker.snapshot()[0] == {"body": "reply", "destination": "topic",
                                    "headers": {"subscription": "out", "message-id": "generated", "region": "west"}}
    broker.reconnect()
    assert broker.snapshot()[0]["body"] == "reply"
    with pytest.raises(TimeoutError):
        broker._receipt(lambda **kwargs: None)
    connections[-1].listener.on_error(SimpleNamespace())
    with pytest.raises(RuntimeError, match="ERROR"):
        broker.snapshot()
    broker.close()
    assert all(not conn.connected for conn in connections)


def test_ordering_replay_allows_cross_key_interleaving():
    expected = [message(), message("b", seq="2"), message("c", key="y")]

    class Captured(FakeBroker):
        output = [expected[2], *expected[:2]]
    sample = flow()
    sample["expected"]["messages"] = expected
    sample["faults"] = {"ordering": {"key_header": "key", "sequence_header": "seq", "parallel_consumers": 2}}
    result = replay_flow("sample", sample, {}, "ordering", Captured, FakeResources, lambda _: None)
    assert result["status"] == "matched"
    assert result["matched"] == 3
