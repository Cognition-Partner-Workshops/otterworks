"""Credential transport regression checks; HTTPS responses are synthetic."""
import io
from email.message import Message
from pathlib import Path
import sys
from unittest.mock import MagicMock, Mock
from urllib import request
from urllib.response import addinfourl

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fire_alert

BODY = {"alerts": [{"status": "firing"}]}


@pytest.mark.parametrize("url", [
    "http://receiver.example/hook", "file:///tmp/hook", "ftp://receiver.example/hook",
    "https:///hook", "https://user:password@receiver.example/hook",
    "https://receiver.example/hook#fragment", "https://receiver.example:invalid/hook",
])
def test_rejects_unsafe_webhook_before_sending_credentials(url, capsys):
    response = MagicMock()
    response.__enter__.return_value.status = 200
    opener = Mock(return_value=response)
    assert fire_alert.deliver(BODY, url, "offline-token", opener) == 1
    opener.assert_not_called()
    assert "offline-token" not in capsys.readouterr().err


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_default_transport_never_follows_authenticated_redirect(monkeypatch, status, capsys):
    seen = []

    class SyntheticHTTPS(request.HTTPSHandler):
        def https_open(self, req):
            seen.append((req.full_url, req.get_header("Authorization")))
            first = req.full_url == "https://receiver.example/hook"
            headers = Message()
            if first:
                headers["Location"] = "https://other.example/collect"
            response = addinfourl(io.BytesIO(b""), headers, req.full_url, status if first else 200)
            response.msg = "Synthetic response"
            return response

    monkeypatch.setattr(request, "HTTPSHandler", SyntheticHTTPS)
    monkeypatch.setattr(request, "_opener", request.build_opener(SyntheticHTTPS()))
    assert fire_alert.deliver(BODY, "https://receiver.example/hook", "offline-token") == 1
    assert seen == [("https://receiver.example/hook", "Bearer offline-token")]
    output = capsys.readouterr()
    assert "offline-token" not in output.out + output.err


def test_valid_https_webhook_preserves_auth_and_payload():
    response = MagicMock()
    response.__enter__.return_value.status = 200
    opener = Mock(return_value=response)
    assert fire_alert.deliver(BODY, "https://receiver.example/hook", "offline-token", opener) == 0
    sent = opener.call_args.args[0]
    assert sent.get_header("Authorization") == "Bearer offline-token"
    assert sent.get_method() == "POST"
    assert opener.call_args.kwargs["timeout"] == 30
