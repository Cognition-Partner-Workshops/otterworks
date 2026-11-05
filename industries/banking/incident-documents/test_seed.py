import importlib.util
import json
import re
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import pytest
import yaml

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("bank_seed", HERE / "seed.py")
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)
EXPECTED_SHA256 = "509deec6d2a217ea62acf1ca35976ab23eb674669010e517a0c326f02101da57"


def test_deterministic_payloads():
    first = seed.build_payloads()
    assert first == seed.build_payloads()
    assert seed.content_digest(first) == EXPECTED_SHA256
    assert len(first) == 6
    fixture = yaml.safe_load((HERE.parents[2] / "incident/scenarios.yaml").read_text())
    assert seed.OWNER_ID != fixture["seed"]["owner_id"]
    assert seed.FOLDER_ID != fixture["seed"]["folder_id"]
    titles = [payload["title"] for payload in first]
    assert len(titles) == len(set(titles))
    for payload in first:
        assert payload["owner_id"] == seed.OWNER_ID
        assert payload["folder_id"] == seed.FOLDER_ID
        assert payload["title"].startswith("SYNTHETIC ")
        assert "synthetic rehearsal data" in payload["content"]
        assert payload["content_type"] == "text/markdown"


def test_no_pii_shapes():
    text = json.dumps(seed.build_payloads())
    assert not re.search(r"\d{13,19}", text)
    assert not re.search(r"\b\d{3}-\d{2}-\d{4}\b", text)
    assert not re.search(r"\b[A-Z]{2}\s?\d{6}\s?[A-D]\b", text)
    for email in re.findall(r"[\w.+-]+@([\w.-]+)", text):
        assert email.lower() in {"example.com", "example.org", "example.net"}


def test_seed_empty_then_idempotent(monkeypatch):
    stored = []

    def request(url, headers, payload=None):
        assert headers == {"Authorization": "Bearer test"}
        if payload is not None:
            assert url == "http://test/api/v1/documents/"
            stored.append(payload)
            return {"id": "test"}
        assert parse_qs(urlsplit(url).query)["owner_id"] == [seed.OWNER_ID]
        return {"items": stored, "total": len(stored)}

    monkeypatch.setattr(seed, "request_json", request)
    assert seed.seed_documents("http://test/", {"Authorization": "Bearer test"}) == 6
    assert seed.seed_documents("http://test", {"Authorization": "Bearer test"}) == 0
    assert stored == seed.build_payloads()


def test_seed_lists_all_pages_before_creating(monkeypatch):
    pages = []
    payloads = seed.build_payloads()

    def request(url, headers, payload=None):
        assert payload is None
        page = int(parse_qs(urlsplit(url).query)["page"][0])
        pages.append(page)
        return {"items": payloads[:3] if page == 1 else payloads[3:], "total": 101}

    monkeypatch.setattr(seed, "request_json", request)
    assert seed.seed_documents("http://test", {}) == 0
    assert pages == [1, 2]


@pytest.mark.parametrize("fail_create", [False, True])
def test_http_failure_is_not_swallowed(monkeypatch, fail_create):
    def request(url, headers, payload=None):
        if not fail_create or payload is not None:
            raise HTTPError(url, 503, "Unavailable", {}, None)
        return {"items": [], "total": 0}

    monkeypatch.setattr(seed, "request_json", request)
    with pytest.raises(HTTPError):
        seed.seed_documents("http://test", {})


def test_dry_run_without_network_or_auth(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("dry-run must not use network or auth")

    monkeypatch.setattr(seed, "bearer", forbidden)
    monkeypatch.setattr(seed, "request_json", forbidden)
    monkeypatch.setattr("sys.argv", ["seed.py", "--dry-run"])
    seed.main()
    output = capsys.readouterr().out
    payload_json, digest = output.rsplit("sha256=", 1)
    assert json.loads(payload_json) == seed.build_payloads()
    assert digest.strip() == EXPECTED_SHA256
