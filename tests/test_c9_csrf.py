"""C9: legacy-billing rejects state-changing requests that carry no CSRF token."""
import pathlib
import sys

import pytest

APP_DIR = pathlib.Path(__file__).resolve().parents[1] / "services" / "legacy-billing" / "app"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.syspath_prepend(str(APP_DIR))
    sys.modules.pop("app", None)
    import app as billing

    billing.app.config["TESTING"] = True
    calls = []
    monkeypatch.setattr(billing, "execute", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(billing, "select", lambda *a, **k: [])
    return billing.app.test_client(), calls


@pytest.mark.parametrize("path,data", [
    ("/plans/t1/change", {"plan_id": "p", "effective_on": "2026-01-01"}),
    ("/api/dunning/schedule", {"as_of": "2026-01-01"}),
    ("/api/dunning/suspend", {"as_of": "2026-01-01"}),
])
def test_cross_site_form_post_is_rejected(client, path, data):
    http, calls = client
    resp = http.post(path, data=data)
    assert resp.status_code == 400
    assert calls == []


def test_post_with_valid_token_is_accepted(client):
    http, calls = client
    from flask_wtf.csrf import generate_csrf
    import app as billing

    with billing.app.test_request_context():
        token = generate_csrf()
        cookie_session = dict(__import__("flask").session)
    with http.session_transaction() as sess:
        sess.update(cookie_session)
    resp = http.post("/api/dunning/schedule", data={"as_of": "2026-01-01"}, headers={"X-CSRFToken": token})
    assert resp.status_code != 400
    assert calls


def test_http_client_can_bootstrap_token_and_post(client):
    http, calls = client
    resp = http.get("/api/csrf-token")
    assert resp.status_code == 200
    token = resp.get_json()["csrf_token"]
    resp = http.post("/api/dunning/schedule", data={"as_of": "2026-01-01"}, headers={"X-CSRFToken": token})
    assert resp.status_code != 400
    assert calls


def test_bootstrapped_token_needs_its_session_cookie(client):
    http, calls = client
    token = http.get("/api/csrf-token").get_json()["csrf_token"]
    http._cookies.clear()
    resp = http.post("/api/dunning/schedule", data={"as_of": "2026-01-01"}, headers={"X-CSRFToken": token})
    assert resp.status_code == 400
    assert calls == []
