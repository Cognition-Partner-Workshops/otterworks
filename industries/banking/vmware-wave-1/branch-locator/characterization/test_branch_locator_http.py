"""Characterization tests for branch-locator, run over HTTP against a running app.

The golden files were recorded from the VM stand-in (web-02: Python 2.7, Flask 1.1
dev server, settings.py, /etc/hosts geocoder) on data/seed.sql with the geocoder
stub from vm/geo-stub. The same tests run unchanged against the replatformed
container:

    BRANCH_LOCATOR_URL=http://localhost:8083 pytest characterization   # VM stand-in
    BRANCH_LOCATOR_URL=http://localhost:8087 pytest characterization   # container

Optional, for side effects and outages (skipped when unset):
    BRANCH_LOCATOR_LOG_CMD  shell command printing the app's log output
    GEO_CONTAINER           docker container of the geocoder (stopped and restarted)
    DB_CONTAINER            docker container of the database (stopped and restarted)
    BRANCH_LOCATOR_TZ       zone the app computes open_now in (default UTC, the stand-in's)

RECORD=1 rewrites the golden files; only do that against the VM stand-in.
"""
import datetime
import http.client
import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import quote, urlsplit
from zoneinfo import ZoneInfo

import pytest

BASE = os.environ.get("BRANCH_LOCATOR_URL", "http://localhost:8083").rstrip("/")
RECORD = os.environ.get("RECORD") == "1"
TZ = ZoneInfo(os.environ.get("BRANCH_LOCATOR_TZ", "UTC"))
HERE = Path(__file__).parent
GOLDEN = HERE / "golden"
SEED = HERE.parents[1] / "data" / "seed.sql"

_url = urlsplit(BASE)
PREFIX = _url.path

QUERIES = {
    "harbour": "harbour",
    "market": "market",
    "old-town": "old town",
    "river": "river",
    "hill": "hill",
    "lake": "lake",
    "fallback": "zzz",
    "mixed-case": "Harbour Point",
    "padded": "  lake  ",
}


def request(path, method="GET"):
    conn = http.client.HTTPConnection(_url.hostname, _url.port or 80, timeout=20)
    conn.request(method, PREFIX + path)
    resp = conn.getresponse()
    body = resp.read().decode("utf-8")
    conn.close()
    return resp, body


def hhmm():
    return datetime.datetime.now(TZ).strftime("%H:%M")


def strip_open_now(doc):
    doc = json.loads(json.dumps(doc))
    for b in doc.get("branches", []):
        b.pop("open_now", None)
    return doc


def typed(value):
    """JSON value with its types made explicit, so 10 and 10.0 do not compare equal."""
    if isinstance(value, dict):
        return {k: typed(v) for k, v in value.items()}
    if isinstance(value, list):
        return [typed(v) for v in value]
    return (type(value).__name__, value)


def golden_json(name, doc):
    f = GOLDEN / name
    if RECORD:
        f.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    assert f.exists(), f"missing golden file {f}; record it against the VM stand-in with RECORD=1"
    assert typed(doc) == typed(json.loads(f.read_text(encoding="utf-8")))


def golden_text(name, body):
    f = GOLDEN / name
    if RECORD:
        f.write_text(body, encoding="utf-8")
    assert f.exists(), f"missing golden file {f}; record it against the VM stand-in with RECORD=1"
    assert body == f.read_text(encoding="utf-8")


def seed_branches():
    rx = re.compile(r"INSERT INTO branches \(name,address,lat,lon,opens,closes\) VALUES "
                    r"\('([^']*)','([^']*)',(-?[\d.]+),(-?[\d.]+),'([\d:]+)','([\d:]+)'\);")
    return {n: (a, float(la), float(lo), o, c) for n, a, la, lo, o, c in rx.findall(SEED.read_text())}


def wait_healthy(timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp, _ = request("/api/nearest?q=harbour")
            if resp.status == 200:
                return
        except OSError:
            pass
        time.sleep(2)
    pytest.fail("app did not answer /api/nearest again after the dependency restart")


@pytest.mark.parametrize("slug", sorted(QUERIES))
def test_nearest(slug):
    before = hhmm()
    resp, body = request("/api/nearest?q=" + quote(QUERIES[slug]))
    after = hhmm()
    assert resp.status == 200
    assert resp.getheader("Content-Type") == "application/json"
    doc = json.loads(body)
    assert len(doc["branches"]) == 3
    for b in doc["branches"]:
        assert isinstance(b["open_now"], bool)
        allowed = {b["opens"] <= t < b["closes"] for t in (before, after)}
        assert b["open_now"] in allowed
    golden_json(f"nearest-{slug}.json", strip_open_now(doc))


def test_every_seeded_branch_is_reachable_and_matches_seed():
    seed = seed_branches()
    assert len(seed) == 6
    seen = set()
    for slug in QUERIES:
        doc = json.loads((GOLDEN / f"nearest-{slug}.json").read_text(encoding="utf-8"))
        for b in doc["branches"]:
            assert (b["address"], b["lat"], b["lon"], b["opens"], b["closes"]) == seed[b["name"]]
            seen.add(b["name"])
    assert seen == set(seed)


@pytest.mark.parametrize("path", ["/api/nearest", "/api/nearest?q=", "/api/nearest?q=%20", "/api/nearest?x=harbour"])
def test_missing_query_is_400(path):
    resp, body = request(path)
    assert resp.status == 400
    assert resp.getheader("Content-Type") == "application/json"
    assert typed(json.loads(body)) == typed({"error": "q is required"})


def test_index_page():
    resp, body = request("/")
    assert resp.status == 200
    assert resp.getheader("Content-Type") == "text/html; charset=utf-8"
    golden_text("index.html", body)


def test_unknown_path_is_404():
    resp, _ = request("/no-such-page")
    assert resp.status == 404


def test_post_is_405():
    resp, _ = request("/api/nearest?q=harbour", method="POST")
    assert resp.status == 405


@pytest.mark.skipif(not os.environ.get("BRANCH_LOCATOR_LOG_CMD"), reason="BRANCH_LOCATOR_LOG_CMD not set")
def test_lookup_is_logged():
    token = uuid.uuid4().hex[:8]
    resp, _ = request("/api/nearest?q=" + quote(f"harbour {token}"))
    assert resp.status == 200
    time.sleep(1)
    out = subprocess.run(os.environ["BRANCH_LOCATOR_LOG_CMD"], shell=True, capture_output=True, text=True).stdout
    line = f"INFO nearest q=harbour {token} -> ['Harbour Point', 'Market Square', 'Hillcrest']"
    assert line in out


@pytest.mark.parametrize("env", ["GEO_CONTAINER", "DB_CONTAINER"])
def test_dependency_down_is_500(env):
    name = os.environ.get(env)
    if not name:
        pytest.skip(f"{env} not set")
    subprocess.run(["docker", "stop", name], check=True, capture_output=True)
    try:
        resp, _ = request("/api/nearest?q=harbour")
        assert resp.status == 500
        resp, _ = request("/")
        assert resp.status == 200
    finally:
        subprocess.run(["docker", "start", name], check=True, capture_output=True)
    wait_healthy()
