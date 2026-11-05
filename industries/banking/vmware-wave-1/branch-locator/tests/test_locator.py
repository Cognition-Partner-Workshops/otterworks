import io
import logging
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
with patch("logging.basicConfig"):
    import locator


@pytest.fixture
def client():
    with patch.object(locator, "locate", return_value=(10.0, -30.0)), \
            patch.object(locator, "branches", return_value=[]):
        yield locator.app.test_client()


@pytest.fixture
def logs():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    level = locator.log.level
    locator.log.addHandler(handler)
    locator.log.setLevel(logging.INFO)
    try:
        yield stream
    finally:
        locator.log.removeHandler(handler)
        locator.log.setLevel(level)
        handler.close()


@pytest.mark.parametrize("query", [
    "Central",
    "foo\n2026-01-01 00:00:00,000 INFO forged",
    "foo\rforged",
    "foo\r\nforged",
    "foo\t\x00\x1b\x85\u2028\u2029forged",
])
def test_nearest_logs_one_line_and_preserves_response(client, logs, query):
    response = client.get("/api/nearest", query_string={"q": query})

    assert response.status_code == 200
    assert response.get_json() == {
        "query": query, "lat": 10.0, "lon": -30.0, "branches": [],
    }
    locator.locate.assert_called_once_with(query)
    assert logs.getvalue() == "nearest q=%r -> []\n" % query
    assert len(logs.getvalue().splitlines()) == 1


@pytest.mark.parametrize("query", ["", " \r\n "])
def test_empty_query_does_not_log_or_call_dependencies(client, logs, query):
    response = client.get("/api/nearest", query_string={"q": query})

    assert response.status_code == 400
    assert response.get_json() == {"error": "q is required"}
    locator.locate.assert_not_called()
    locator.branches.assert_not_called()
    assert logs.getvalue() == ""


def test_geocoder_error_does_not_log_success(client, logs):
    locator.locate.side_effect = RuntimeError("geocoder unavailable")

    response = client.get("/api/nearest", query_string={"q": "Central"})

    assert response.status_code == 500
    locator.branches.assert_not_called()
    assert logs.getvalue() == ""
