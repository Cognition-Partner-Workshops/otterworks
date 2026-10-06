"""Run: python3 -m pytest infrastructure/terraform/legacy-portal-serverless/consumer (needs boto3, no AWS)."""

import importlib.util
import json
import pathlib
import re
import socket
import threading
import time

import pytest

HERE = pathlib.Path(__file__).parent
FUNCTION_TIMEOUT = int(
    re.search(
        r'resource "aws_lambda_function" "consumer" \{.*?\btimeout\s*=\s*(\d+)',
        (HERE.parent / "events.tf").read_text(),
        re.S,
    ).group(1)
)

EVENT = {
    "id": "evt-1",
    "source": "otterworks.legacy-portal",
    "detail-type": "announcement.published",
    "time": "2026-10-06T00:00:00Z",
    "detail": {"id": 7, "title": "Hello", "body": "World", "published": True, "createdAt": None},
}


class FakeTable:
    def __init__(self, error=None):
        self.items, self.error = {}, error

    def put_item(self, Item):
        if self.error:
            raise self.error
        self.items[Item["eventId"]] = Item


@pytest.fixture
def blackhole():
    """A DynamoDB endpoint that accepts connections and never answers."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(16)
    held = []
    threading.Thread(target=lambda: [held.append(srv.accept()) for _ in iter(int, 1)], daemon=True).start()
    yield f"http://127.0.0.1:{srv.getsockname()[1]}"
    srv.close()


@pytest.fixture
def load(monkeypatch):
    def _load(endpoint=None):
        monkeypatch.setenv("TABLE_NAME", "otterworks-test-notifications")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
        for k in ("AWS_SESSION_TOKEN", "AWS_PROFILE", "AWS_RETRY_MODE", "AWS_MAX_ATTEMPTS"):
            monkeypatch.delenv(k, raising=False)
        if endpoint:
            monkeypatch.setenv("AWS_ENDPOINT_URL_DYNAMODB", endpoint)
        spec = importlib.util.spec_from_file_location("consumer_handler", HERE / "handler.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    return _load


def test_sdk_worst_case_fits_inside_function_timeout(load):
    cfg = load().TABLE.meta.client.meta.config
    attempts = cfg.retries["total_max_attempts"]
    assert cfg.retries["mode"] == "standard"
    # Standard mode waits at most 2 ** (n - 1) s before retry n.
    worst = attempts * (cfg.connect_timeout + cfg.read_timeout) + sum(2 ** (n - 1) for n in range(1, attempts))
    assert worst < FUNCTION_TIMEOUT


def test_hung_dynamodb_fails_before_function_timeout(load, blackhole, capsys):
    module = load(blackhole)
    t0 = time.monotonic()
    with pytest.raises(Exception, match="timeout"):
        module.handler(EVENT, None)
    assert time.monotonic() - t0 < FUNCTION_TIMEOUT
    assert json.loads(capsys.readouterr().out)["failed"] == "evt-1"


def test_failed_write_logs_whole_event_and_reraises(load, capsys):
    module = load()
    module.TABLE = FakeTable(error=RuntimeError("throttled"))
    with pytest.raises(RuntimeError):
        module.handler(EVENT, None)
    record = json.loads(capsys.readouterr().out)
    assert record == {"failed": "evt-1", "error": "RuntimeError: throttled", "event": EVENT}


def test_event_without_id_is_logged_and_fails(load, capsys):
    module = load()
    module.TABLE = FakeTable()
    event = {k: v for k, v in EVENT.items() if k != "id"}
    with pytest.raises(KeyError):
        module.handler(event, None)
    assert json.loads(capsys.readouterr().out)["event"] == event
    assert module.TABLE.items == {}


def test_redelivery_of_same_event_keeps_one_identical_item(load):
    module = load()
    module.TABLE = FakeTable()
    assert module.handler(EVENT, None) == {"stored": "evt-1"}
    first = dict(module.TABLE.items["evt-1"])
    assert module.handler(EVENT, None) == {"stored": "evt-1"}
    assert module.TABLE.items == {"evt-1": first}
    assert "createdAt" not in first
    assert first["detail"] == json.dumps(EVENT["detail"], separators=(",", ":"))
