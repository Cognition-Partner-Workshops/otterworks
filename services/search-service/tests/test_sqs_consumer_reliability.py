"""Reliability regression tests for the SQS consumer, reindex and MeiliSearch client."""

from __future__ import annotations

import json
import socket
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
import requests
from meilisearch.errors import MeilisearchTimeoutError

from app.config import MeiliSearchConfig
from app.services import sqs_consumer as sqs_mod
from app.services.indexer import Indexer, ReindexSourceError
from app.services.meilisearch_client import MeiliSearchService
from app.services.sqs_consumer import SQSConsumer


def _counter(outcome: str) -> float:
    return sqs_mod.SQS_MESSAGES.labels(outcome=outcome)._value.get()


def _sqs(has_dlq: bool) -> MagicMock:
    sqs = MagicMock()
    sqs.get_queue_attributes.return_value = {
        "Attributes": {"RedrivePolicy": '{"maxReceiveCount":"5"}'} if has_dlq else {}
    }
    return sqs


def _msg(body: str, receive_count: str = "1") -> dict:
    return {
        "MessageId": "m-1",
        "ReceiptHandle": "rh-1",
        "Body": body,
        "Attributes": {"ApproximateReceiveCount": receive_count},
    }


def _consumer(indexer: Indexer | None = None, visibility_timeout: int = 60) -> SQSConsumer:
    consumer = SQSConsumer(
        indexer=indexer or Indexer(MagicMock()),
        queue_url="https://sqs.example/q",
        visibility_timeout=visibility_timeout,
    )
    consumer._running = True
    return consumer


DOC_EVENT = json.dumps({
    "event_type": "document_created",
    "payload": {"id": "doc-1", "title": "Plan", "owner_id": "u-1"},
})


class TestPoisonMessages:
    @pytest.mark.parametrize("body", ["not json", json.dumps([1, 2]), json.dumps("str"),
                                      json.dumps({"event_type": "document_created",
                                                  "payload": {"title": "no id"}}),
                                      json.dumps({"event_type": "document_created",
                                                  "payload": ["x"]})])
    def test_poison_retained_for_dlq_when_redrive_configured(self, body):
        sqs = _sqs(has_dlq=True)
        before = _counter("poison_retained")
        _consumer()._process_message(sqs, _msg(body))
        sqs.delete_message.assert_not_called()
        assert _counter("poison_retained") == before + 1

    @pytest.mark.parametrize("body", ["not json", json.dumps([1, 2])])
    def test_poison_discarded_with_metric_when_no_dlq(self, body):
        sqs = _sqs(has_dlq=False)
        before = _counter("poison_discarded")
        _consumer()._process_message(sqs, _msg(body))
        sqs.delete_message.assert_called_once_with(
            QueueUrl="https://sqs.example/q", ReceiptHandle="rh-1"
        )
        assert _counter("poison_discarded") == before + 1

    def test_redrive_lookup_failure_is_not_cached(self):
        sqs = _sqs(has_dlq=True)
        sqs.get_queue_attributes.side_effect = [Exception("throttled"),
                                                {"Attributes": {"RedrivePolicy": "{}x"}}]
        consumer = _consumer()
        assert consumer._queue_has_dlq(sqs) is False
        assert consumer._queue_has_dlq(sqs) is True
        assert consumer._queue_has_dlq(sqs) is True
        assert sqs.get_queue_attributes.call_count == 2


class TestTransientAndSuccess:
    def test_transient_failure_left_for_redelivery(self):
        search = MagicMock()
        search.index_document.side_effect = requests.ConnectionError("meili down")
        sqs = _sqs(has_dlq=False)
        before = _counter("failed")
        _consumer(Indexer(search))._process_message(sqs, _msg(DOC_EVENT))
        sqs.delete_message.assert_not_called()
        assert _counter("failed") == before + 1

    def test_success_deletes_message(self):
        sqs = _sqs(has_dlq=False)
        _consumer()._process_message(sqs, _msg(DOC_EVENT))
        sqs.delete_message.assert_called_once()

    def test_sns_wrapped_success(self):
        sqs = _sqs(has_dlq=False)
        envelope = json.dumps({"Type": "Notification", "MessageId": "sns-1",
                               "TopicArn": "arn:aws:sns:us-east-1:1:t", "Message": DOC_EVENT})
        search = MagicMock()
        _consumer(Indexer(search))._process_message(sqs, _msg(envelope))
        search.index_document.assert_called_once()
        sqs.delete_message.assert_called_once()

    def test_ack_failure_after_success_does_not_raise(self):
        sqs = _sqs(has_dlq=False)
        sqs.delete_message.side_effect = Exception("network")
        before = _counter("ack_failed")
        _consumer()._process_message(sqs, _msg(DOC_EVENT))
        assert _counter("ack_failed") == before + 1

    def test_reprocessing_same_event_is_idempotent_upsert(self):
        search = MagicMock()
        consumer = _consumer(Indexer(search))
        for _ in range(2):
            consumer._process_message(_sqs(False), _msg(DOC_EVENT, receive_count="2"))
        first, second = search.index_document.call_args_list
        assert first == second


class TestBatchLease:
    def test_unstarted_messages_deferred_after_half_visibility(self):
        consumer = _consumer(visibility_timeout=10)
        processed = []
        consumer._process_message = lambda sqs, m: processed.append(m["MessageId"])
        clock = iter([0.0, 1.0, 6.0, 6.0, 6.0])
        before = _counter("deferred")
        with patch.object(sqs_mod.time, "monotonic", lambda: next(clock)):
            consumer._process_batch(MagicMock(), [{"MessageId": f"m{i}"} for i in range(4)], 0.0)
        assert processed == ["m0", "m1"]
        assert _counter("deferred") == before + 2


class TestPollLoopResilience:
    def test_backoff_is_jittered_and_capped(self):
        with patch.object(sqs_mod.random, "uniform", side_effect=lambda a, b: b) as uni:
            ceilings = [SQSConsumer._backoff_delay(n) for n in range(8)]
        assert ceilings == [1, 2, 4, 8, 16, 30, 30, 30]
        assert all(call.args[0] == 0 for call in uni.call_args_list)

    def test_receive_errors_back_off_then_reset(self):
        consumer = _consumer()
        sqs = MagicMock()
        calls = {"n": 0}

        def receive(**kwargs):
            calls["n"] += 1
            assert kwargs["AttributeNames"] == ["ApproximateReceiveCount"]
            if calls["n"] <= 2:
                raise Exception("throttled")
            consumer._running = False
            return {"Messages": []}

        sqs.receive_message.side_effect = receive
        waits = []
        consumer._stop_event.wait = lambda d: waits.append(d)
        with patch.object(consumer, "_create_sqs_client", return_value=sqs), \
             patch.object(sqs_mod.random, "uniform", side_effect=lambda a, b: b):
            consumer._poll_loop()
        assert waits == [1, 2]

    def test_sqs_client_has_explicit_timeouts_and_standard_retries(self):
        consumer = _consumer()
        with patch("boto3.client") as client:
            consumer._create_sqs_client()
        cfg = client.call_args.kwargs["config"]
        assert cfg.connect_timeout == 5
        assert cfg.read_timeout > consumer.wait_time_seconds
        assert cfg.retries == {"mode": "standard", "max_attempts": 3}

    def test_stop_waits_longer_than_long_poll(self):
        consumer = _consumer()
        consumer._thread = MagicMock()
        consumer._thread.is_alive.return_value = True
        consumer.stop()
        consumer._thread.join.assert_called_once_with(timeout=consumer.wait_time_seconds + 5)
        assert consumer._stop_event.is_set()


class TestReindexPreservesIndex:
    @pytest.mark.parametrize("failure", [requests.ConnectionError("down"), "http500", "midpage"])
    def test_source_failure_aborts_before_touching_index(self, failure):
        search = MagicMock()
        ok_page = MagicMock(status_code=200)
        ok_page.json.return_value = {"documents": [{"id": "d1", "title": "t"}]}
        bad = MagicMock(status_code=500)
        if failure == "http500":
            side_effect = [bad]
        elif failure == "midpage":
            side_effect = [ok_page, bad]
        else:
            side_effect = failure
        with patch("app.services.indexer.requests.get", side_effect=side_effect):
            with pytest.raises(ReindexSourceError):
                Indexer(search).reindex()
        search.reindex.assert_not_called()

    def test_reindex_api_returns_502_and_keeps_index(self, client, mock_meilisearch_client):
        with patch("app.services.indexer.requests.get",
                   side_effect=requests.ConnectionError("down")):
            resp = client.post("/api/v1/search/reindex")
        assert resp.status_code == 502
        assert "left intact" in resp.get_json()["error"]
        mock_meilisearch_client.delete_index.assert_not_called()


class TestMeiliSearchTimeout:
    def test_hung_meilisearch_call_times_out(self):
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(5)
        held: list = []
        threading.Thread(target=lambda: held.append(srv.accept()), daemon=True).start()
        svc = MeiliSearchService(MeiliSearchConfig(
            url=f"http://127.0.0.1:{srv.getsockname()[1]}", timeout_seconds=1))
        start = time.monotonic()
        with pytest.raises(MeilisearchTimeoutError):
            svc.client.get_version()
        assert time.monotonic() - start < 5
        srv.close()

    def test_default_timeout_is_bounded(self, monkeypatch):
        monkeypatch.delenv("MEILISEARCH_TIMEOUT_SECONDS", raising=False)
        svc = MeiliSearchService(MeiliSearchConfig(url="http://127.0.0.1:1"))
        assert svc.client.config.timeout == 10
