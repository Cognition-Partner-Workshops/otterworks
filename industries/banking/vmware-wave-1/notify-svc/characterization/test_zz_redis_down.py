"""Behaviour when Redis is unavailable. Destructive: shuts the app's Redis down.

Runs only with NOTIFY_REDIS_DOWN=1, after test_notify_http.py, against an app whose
Redis may be lost (see test_notify_http.py for the other variables).
"""
import json
import os
import socket

import pytest
import redis

from test_notify_http import REDIS_URL, request

pytestmark = pytest.mark.skipif(os.environ.get("NOTIFY_REDIS_DOWN") != "1", reason="set NOTIFY_REDIS_DOWN=1")


@pytest.fixture(scope="module", autouse=True)
def redis_down():
    r = redis.Redis.from_url(REDIS_URL)
    try:
        r.shutdown(nosave=True)
    except redis.exceptions.ConnectionError:
        pass


def test_post_waits_for_redis_instead_of_answering():
    with pytest.raises((socket.timeout, TimeoutError)):
        request("POST", "/notify", json.dumps({"account": "HG611000001", "kind": "statement_ready"}), timeout=5)


def test_outbox_waits_for_redis_instead_of_answering():
    with pytest.raises((socket.timeout, TimeoutError)):
        request("GET", "/outbox/HG611000001", timeout=5)


def test_validation_errors_still_answer_without_redis():
    resp, text = request("POST", "/notify", '{"account":"HG611000001","kind":"nope"}')
    assert (resp.status, text) == (400, '{"error":"unknown notification kind: nope"}')
