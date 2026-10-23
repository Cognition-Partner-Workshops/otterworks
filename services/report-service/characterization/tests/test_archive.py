"""ArchiveController (/api/archive/documents, /api/v1/archive/documents,
/api/v1/reports/archive/documents) with ARCHIVE_STORE unset, db2 and postgresql."""
import pytest

from conftest import error_shape, headers_of, http

PREFIXES = ["/api/archive/documents", "/api/v1/archive/documents", "/api/v1/reports/archive/documents"]
DOC = "3f2c1d9e-0a4b-4c5d-8e6f-7a8b9c0d1e2f"
SHORT = "CHAR-DOC-SHORT"


def shape(resp):
    return {"status": resp.status_code, "content_type": resp.headers.get("Content-Type"),
            "body": resp.json() if "json" in resp.headers.get("Content-Type", "") else resp.text}


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("suffix", ["/" + DOC, "/" + DOC + "/hash", "/" + DOC + "?raw=true"])
def test_feature_off_is_404_with_hint(prefix, suffix, snapshot):
    resp = http("GET", "off", prefix + suffix)
    assert resp.status_code == 404
    assert resp.json() == {
        "error": "archive feature is not enabled",
        "hint": "archive feature is off; set ARCHIVE_STORE=db2, postgresql or azuresql to enable it",
    }
    snapshot("archive_off", shape(resp))


@pytest.mark.parametrize("instance", ["db2", "pg"])
@pytest.mark.parametrize("case,suffix", [
    ("doc", "/" + DOC),
    ("doc_raw", "/" + DOC + "?raw=true"),
    ("doc_raw_false", "/" + DOC + "?raw=false"),
    ("hash", "/" + DOC + "/hash"),
    ("short", "/" + SHORT),
    ("short_padded", "/" + SHORT + "%20%20"),
    ("short_raw", "/" + SHORT + "?raw=true"),
    ("short_hash", "/" + SHORT + "/hash"),
    ("unknown", "/no-such-doc"),
    ("unknown_padded", "/no-such-doc%20"),
    ("unknown_hash", "/no-such-doc/hash"),
    ("bad_raw", "/" + DOC + "?raw=maybe"),
])
def test_archive_store(instance, case, suffix, snapshot):
    resp = http("GET", instance, PREFIXES[0] + suffix)
    body = shape(resp)
    if case == "bad_raw":
        body = error_shape(resp)
    snapshot("archive_%s__%s" % (instance, case), body)
    for prefix in PREFIXES[1:]:
        other = http("GET", instance, prefix + suffix)
        assert other.status_code == resp.status_code
        if case != "bad_raw":
            assert shape(other) == shape(resp), prefix


@pytest.mark.parametrize("suffix", ["/" + DOC, "/" + SHORT])
def test_default_response_identical_across_stores(suffix):
    """CONTRACTS §10.4: without ?raw the document is the same from Db2 and PostgreSQL but for 'store'."""
    db2 = http("GET", "db2", PREFIXES[0] + suffix).json()
    pg = http("GET", "pg", PREFIXES[0] + suffix).json()
    assert db2.pop("store") == "db2"
    assert pg.pop("store") == "postgresql"
    assert db2 == pg


def test_hash_across_stores():
    """BusinessHash keeps key padding: Db2 pads ARCH_KEY CHAR(16), PostgreSQL stores VARCHAR(16), so a
    14-character key hashes differently per store (the MIG-04 signal) while FILEAUD rows, whose
    AUDIT_KEY fills CHAR(20), hash the same."""
    db2 = http("GET", "db2", PREFIXES[0] + "/" + DOC + "/hash").json()
    pg = http("GET", "pg", PREFIXES[0] + "/" + DOC + "/hash").json()
    assert [v["arch_key"] for v in db2["versions"]] == [v["arch_key"] for v in pg["versions"]]
    for d, p in zip(db2["versions"], pg["versions"]):
        assert d["events"] == p["events"]
        assert d["row_hash"] != p["row_hash"]
    assert db2["document_hash"] != pg["document_hash"]


def test_archive_security_headers(snapshot):
    resp = http("GET", "db2", PREFIXES[0] + "/" + DOC)
    snapshot("archive_headers", headers_of(resp))
