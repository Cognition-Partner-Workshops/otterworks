"""Characterization tests for statements-web, run over HTTP against a running app.

The golden files were recorded from the VM stand-in (Tomcat 8.5, JNDI datasource,
/opt/app/conf settings) on data/seed.sql. The same tests run unchanged against the
replatformed container:

    STATEMENTS_URL=http://localhost:8081/statements pytest characterization   # VM stand-in
    STATEMENTS_URL=http://localhost:8080/statements pytest characterization   # container

RECORD=1 rewrites the golden files; only do that against the VM stand-in.
"""
import http.client
import os
import re
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

import pytest

BASE = os.environ.get("STATEMENTS_URL", "http://localhost:8081/statements").rstrip("/")
RECORD = os.environ.get("RECORD") == "1"
HERE = Path(__file__).parent
GOLDEN = HERE / "golden"
SEED = HERE.parents[1] / "data" / "seed.sql"

_url = urlsplit(BASE)
CONTEXT = _url.path


def get(path, cookie=None):
    conn = http.client.HTTPConnection(_url.hostname, _url.port or 80, timeout=15)
    headers = {"Cookie": cookie} if cookie else {}
    conn.request("GET", CONTEXT + path, headers=headers)
    resp = conn.getresponse()
    body = resp.read().decode("utf-8")
    conn.close()
    return resp, body


def golden(name, body):
    f = GOLDEN / name
    if RECORD:
        f.write_text(body, encoding="utf-8")
    assert f.exists(), f"missing golden file {f}; record it against the VM stand-in with RECORD=1"
    assert body == f.read_text(encoding="utf-8")


def seed_accounts():
    return re.findall(r"INSERT INTO accounts VALUES \('(\w+)','([^']*)','(\w+)'\);", SEED.read_text())


def seed_lines(account):
    rx = re.compile(r"VALUES \('" + account + r"','([\d-]+)','([^']*)',(-?[\d.]+),(-?[\d.]+)\);")
    return [(d, desc, Decimal(a), Decimal(b)) for d, desc, a, b in rx.findall(SEED.read_text())]


ACCOUNTS = [a for a, _, _ in seed_accounts()]


def test_seed_has_the_expected_shape():
    assert len(ACCOUNTS) == 24
    assert "HG611000001" in ACCOUNTS


def test_accounts_page():
    resp, body = get("/accounts")
    assert resp.status == 200
    assert resp.getheader("Content-Type").replace(" ", "").lower() == "text/html;charset=utf-8"
    golden("accounts.html", body)


def test_accounts_page_lists_every_seed_account_in_order():
    _, body = get("/accounts")
    listed = re.findall(r'<a href="statement\?account=(\w+)">\w+</a></td><td>([^<]*)</td>', body)
    assert listed == [(a, h) for a, h, _ in sorted(seed_accounts())]


@pytest.mark.parametrize("account", ACCOUNTS)
def test_statement_page(account):
    resp, body = get(f"/statement?account={account}")
    assert resp.status == 200
    assert resp.getheader("Content-Type").replace(" ", "").lower() == "text/html;charset=utf-8"
    golden(f"statement-{account}.html", body)


@pytest.mark.parametrize("account", ACCOUNTS)
def test_statement_matches_seed_rows(account):
    _, body = get(f"/statement?account={account}")
    rows = re.findall(r'<tr><td>([\d-]+)</td><td>([^<]*)</td><td class="n">(-?[\d.]+)</td><td class="n">(-?[\d.]+)</td></tr>', body)
    expected = sorted(seed_lines(account), key=lambda r: r[0])
    assert [(d, s, Decimal(a), Decimal(b)) for d, s, a, b in rows] == expected
    net = sum((r[2] for r in expected), Decimal("0.00"))
    assert f'<p id="summary">{len(expected)} lines, net movement {net}</p>' in body


def test_statement_for_unknown_account_is_empty():
    resp, body = get("/statement?account=HG999999999")
    assert resp.status == 200
    golden("statement-unknown.html", body)


@pytest.mark.parametrize("query", ["", "?account=", "?account=hg611000001", "?account=HG61", "?account=HG611000001%27--"])
def test_statement_rejects_bad_account(query):
    resp, _ = get(f"/statement{query}")
    assert resp.status == 400


def test_last_viewed_account_follows_the_session():
    resp, _ = get("/statement?account=HG611000001")
    cookie = resp.getheader("Set-Cookie")
    assert cookie and cookie.startswith("JSESSIONID=")
    assert f"Path={CONTEXT}" in cookie and "HttpOnly" in cookie
    resp, body = get("/accounts", cookie=cookie.split(";")[0])
    assert resp.status == 200
    assert resp.getheader("Set-Cookie") is None
    golden("accounts-last-viewed.html", body)


def test_first_accounts_visit_starts_a_session():
    resp, _ = get("/accounts")
    assert resp.getheader("Set-Cookie", "").startswith("JSESSIONID=")


def test_context_root_redirects_to_accounts():
    resp, body = get("/")
    assert resp.status == 200
    golden("index.html", body)


def test_context_without_slash_redirects():
    resp, _ = get("")
    assert resp.status == 302
    assert resp.getheader("Location").endswith(CONTEXT + "/")
