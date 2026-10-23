"""ReconciliationController JSON / CSV / HTML under /api/reports/reconciliation and
/api/v1/reports/reconciliation, per ARCHIVE_STORE value."""
import re

import pytest

from conftest import assert_recent_utc, headers_of, http

PREFIXES = ["/api/reports/reconciliation", "/api/v1/reports/reconciliation"]
SUFFIXES = ["", "/latest", "/char-run-002", "/latest.csv", "/latest.html", "/char-run-001.csv"]
GENERATED = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


def shape(resp):
    ctype = resp.headers.get("Content-Type", "")
    return {"status": resp.status_code, "content_type": ctype,
            "body": resp.json() if "json" in ctype else resp.text}


def check_generated(value):
    from datetime import datetime, timezone
    assert GENERATED.fullmatch(value), value
    assert_recent_utc(datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc))


@pytest.mark.parametrize("instance", ["off", "db2"])
@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("suffix", SUFFIXES)
def test_no_ledger_is_404(instance, prefix, suffix, snapshot):
    resp = http("GET", instance, prefix + suffix)
    assert resp.status_code == 404
    snapshot("reconciliation_%s" % instance, shape(resp))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_list_runs(prefix, snapshot):
    resp = http("GET", "pg", prefix)
    assert resp.status_code == 200
    assert [r["run_id"] for r in resp.json()] == ["char-run-002", "char-run-001"]
    snapshot("reconciliation_pg__list", shape(resp))


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("run", ["char-run-001", "char-run-002", "latest"])
def test_run_json(prefix, run, snapshot):
    resp = http("GET", "pg", "%s/%s" % (prefix, run))
    assert resp.status_code == 200
    body = resp.json()
    check_generated(body["generated_at"])
    body["generated_at"] = "<now ISO UTC>"
    snapshot("reconciliation_pg__json_%s" % ("char-run-002" if run == "latest" else run),
             {"status": resp.status_code, "content_type": resp.headers.get("Content-Type"), "body": body})


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("run", ["char-run-001", "char-run-002", "latest"])
def test_run_csv(prefix, run, snapshot):
    resp = http("GET", "pg", "%s/%s.csv" % (prefix, run))
    assert resp.status_code == 200
    snapshot("reconciliation_pg__csv_%s" % ("char-run-002" if run == "latest" else run),
             {"headers": headers_of(resp, ("Content-Type", "Content-Disposition")),
              "body": resp.content.decode("utf-8")})


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("run", ["char-run-001", "char-run-002", "latest"])
def test_run_html(prefix, run, snapshot):
    resp = http("GET", "pg", "%s/%s.html" % (prefix, run))
    assert resp.status_code == 200
    text = resp.content.decode("utf-8")
    m = re.search(r"generated (%s)" % GENERATED.pattern, text)
    assert m, text[:500]
    check_generated(m.group(1))
    text = text.replace(m.group(1), "<now ISO UTC>")
    snapshot("reconciliation_pg__html_%s" % ("char-run-002" if run == "latest" else run),
             {"headers": headers_of(resp, ("Content-Type", "Content-Disposition")), "body": text})


@pytest.mark.parametrize("suffix", ["/no-such-run", "/no-such-run.csv", "/no-such-run.html", "/other-ns-run"])
def test_unknown_run(suffix, snapshot):
    resp = http("GET", "pg", PREFIXES[1] + suffix)
    assert resp.status_code == 404
    snapshot("reconciliation_pg__unknown", shape(resp))
