from __future__ import annotations

import json

import pytest

from otterworks_etl.analytics import drain_queue


class FakeSqs:
    def __init__(self, bodies, fail_receives=0, fail_delete=False):
        self.queue = [(f"m{i}", body) for i, body in enumerate(bodies)]
        self.in_flight: set[str] = set()
        self.deleted: list[str] = []
        self.calls: list[str] = []
        self.fail_receives = fail_receives
        self.fail_delete = fail_delete

    def receive_message(self, QueueUrl, MaxNumberOfMessages, **kwargs):
        self.calls.append("receive")
        if self.fail_receives:
            self.fail_receives -= 1
            raise ConnectionError("throttled")
        visible = [m for m in self.queue if m[0] not in self.in_flight][:MaxNumberOfMessages]
        self.in_flight.update(mid for mid, _ in visible)
        return {
            "Messages": [
                {"MessageId": mid, "ReceiptHandle": f"rh-{mid}", "Body": b} for mid, b in visible
            ]
        }

    def delete_message_batch(self, QueueUrl, Entries):
        self.calls.append("delete")
        if self.fail_delete:
            return {"Failed": [{"Id": Entries[0]["Id"]}], "Successful": []}
        ids = {e["Id"] for e in Entries}
        self.deleted.extend(sorted(ids))
        self.queue = [m for m in self.queue if m[0] not in ids]
        return {"Successful": [{"Id": i} for i in ids]}


def _drain(sqs, staged, **overrides):
    def stage(index, events):
        sqs.calls.append("stage")
        staged[index] = list(events)
        return f"batch-{index}"

    kwargs = dict(max_messages=10000, batch_size=10, wait_time_seconds=0, max_consecutive_errors=3)
    kwargs.update(overrides)
    return drain_queue(sqs, "url", stage, **kwargs)


def test_stages_before_deleting_and_leaves_malformed_in_flight(caplog):
    bodies = [json.dumps({"n": i}) for i in range(12)] + ["not json", "{"]
    sqs, staged = FakeSqs(bodies), {}
    with caplog.at_level("WARNING"):
        result = _drain(sqs, staged)

    assert result.staged_keys == ["batch-0", "batch-1"]
    assert [e["n"] for i in sorted(staged) for e in staged[i]] == list(range(12))
    assert result.messages_processed == 14
    assert result.malformed == 2 and result.events == 12
    # every delete follows the stage of its batch
    assert sqs.calls[:3] == ["receive", "stage", "delete"]
    assert [body for _, body in sqs.queue] == ["not json", "{"]
    assert "sqs_malformed_messages_left_in_flight" in caplog.text
    assert '"count":2' in caplog.text


def test_a_failed_stage_deletes_nothing():
    sqs = FakeSqs([json.dumps({"n": 1})])

    def stage(index, events):
        raise OSError("S3 down")

    with pytest.raises(OSError):
        drain_queue(sqs, "url", stage, max_messages=10, batch_size=10, wait_time_seconds=0,
                    max_consecutive_errors=3)  # fmt: skip
    assert sqs.deleted == [] and len(sqs.queue) == 1


def test_failed_delete_raises_after_staging():
    sqs, staged = FakeSqs([json.dumps({"n": 1})], fail_delete=True), {}
    with pytest.raises(RuntimeError, match="delete failed"):
        _drain(sqs, staged)
    assert staged == {0: [{"n": 1}]}


def test_max_messages_counts_malformed_and_resumes():
    sqs, staged = FakeSqs(["bad"] * 5 + [json.dumps({"n": 1})] * 5), {}
    result = _drain(sqs, staged, max_messages=7, batch_size=5, messages_processed=2, next_batch=3)
    assert result.messages_processed == 7
    assert result.staged_keys == []
    assert result.malformed == 5


def test_receive_errors_give_up_after_the_limit():
    sqs, staged = FakeSqs([json.dumps({"n": 1})], fail_receives=5), {}
    result = _drain(sqs, staged)
    assert result.gave_up and result.events == 0
    assert sqs.calls == ["receive"] * 3

    sqs, staged = FakeSqs([json.dumps({"n": 1})], fail_receives=2), {}
    result = _drain(sqs, staged)
    assert not result.gave_up and result.events == 1
