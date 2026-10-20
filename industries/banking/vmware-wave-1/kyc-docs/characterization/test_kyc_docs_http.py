"""Characterization tests for kyc-docs, run over HTTP against a running app.

The golden files were recorded from the VM stand-in (vm/compose.yaml service
kyc-01: Spring Boot 2.3 on JRE 11, HTTPS on 8443, uploads on local disk). The
same tests run unchanged against the replatformed container:

    KYC_URL=https://localhost:8085 pytest characterization    # VM stand-in
    KYC_URL=http://localhost:8080 pytest characterization     # container

Optional side-effect hooks (shell commands, run with the placeholders filled in):

    KYC_STORED_CMD  prints the stored bytes of one document, e.g.
                    'docker exec wave1-vm-kyc-01-1 cat /var/kyc/uploads/{customer}/{file}'
    KYC_LOGS_CMD    prints the application log, e.g.
                    'docker exec wave1-vm-kyc-01-1 cat /var/log/kyc/kyc-docs.log'

TLS verification is off: the VM serves a self-signed certificate.
RECORD=1 rewrites the golden files; only do that against the VM stand-in.
"""
import hashlib
import http.client
import json
import os
import random
import re
import shlex
import ssl
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import pytest

BASE = os.environ.get("KYC_URL", "https://localhost:8085").rstrip("/")
STORED_CMD = os.environ.get("KYC_STORED_CMD")
LOGS_CMD = os.environ.get("KYC_LOGS_CMD")
RECORD = os.environ.get("RECORD") == "1"
HERE = Path(__file__).parent
GOLDEN = HERE / "golden"
SEED = HERE.parents[1] / "data" / "seed.sql"
KINDS = ["passport", "id-card", "proof-of-address", "payslip"]
LIMIT = 10 * 1024 * 1024

_url = urlsplit(BASE)
PREFIX = _url.path


def _conn():
    if _url.scheme == "https":
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return http.client.HTTPSConnection(_url.hostname, _url.port or 443, timeout=30, context=ctx)
    return http.client.HTTPConnection(_url.hostname, _url.port or 80, timeout=30)


def request(method, path, body=None, headers=None):
    conn = _conn()
    conn.request(method, PREFIX + path, body=body, headers=headers or {})
    resp = conn.getresponse()
    data = resp.read().decode("utf-8")
    conn.close()
    return resp, data


def multipart(parts):
    """parts: list of (field name, filename or None, bytes)."""
    boundary = "kyc" + uuid.uuid4().hex
    out = b""
    for name, filename, content in parts:
        disp = f'form-data; name="{name}"'
        if filename is not None:
            disp += f'; filename="{filename}"'
        out += f"--{boundary}\r\nContent-Disposition: {disp}\r\n".encode()
        if filename is not None:
            out += b"Content-Type: application/octet-stream\r\n"
        out += b"\r\n" + content + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return out, {"Content-Type": f"multipart/form-data; boundary={boundary}"}


def upload(customer, kind, filename, content, field="file"):
    body, headers = multipart([(field, filename, content)])
    query = "" if kind is None else f"?kind={kind}"
    return request("POST", f"/documents/{customer}{query}", body, headers)


def normalize(body):
    body = re.sub(r'"timestamp":"[^"]+"', '"timestamp":"<ts>"', body)
    return re.sub(r"-\d{13}(\.[a-z]+)", r"-<millis>\1", body)


def golden(name, body):
    f = GOLDEN / name
    text = normalize(body)
    if RECORD:
        f.write_text(text + "\n", encoding="utf-8")
    assert f.exists(), f"missing golden file {f}; record it against the VM stand-in with RECORD=1"
    assert text + "\n" == f.read_text(encoding="utf-8")


def fresh_customer():
    # Not a seeded id and never used before, so the store has nothing for it.
    return "ZZ" + str(int(time.time() * 1000)) + str(random.randint(100, 999))


def seed_accounts():
    return re.findall(r"INSERT INTO accounts VALUES \('(\w+)',", SEED.read_text())


ACCOUNTS = seed_accounts()


def stored_bytes(customer, file):
    cmd = STORED_CMD.format(customer=customer, file=file)
    return subprocess.run(shlex.split(cmd), check=True, capture_output=True).stdout


def app_log():
    out = subprocess.run(shlex.split(LOGS_CMD), check=True, capture_output=True)
    return (out.stdout + out.stderr).decode("utf-8", "replace")


def assert_json(resp):
    assert resp.getheader("Content-Type") == "application/json"


def test_seed_has_the_expected_shape():
    assert len(ACCOUNTS) == 24
    assert "HG611000001" in ACCOUNTS


def test_list_for_customer_without_documents_is_empty():
    resp, body = request("GET", f"/documents/{fresh_customer()}")
    assert resp.status == 200
    assert_json(resp)
    assert body == "[]"


@pytest.mark.parametrize("account", ACCOUNTS)
def test_upload_and_list_every_seed_account(account):
    kind = KINDS[ACCOUNTS.index(account) % len(KINDS)]
    content = f"kyc document for {account}\n".encode() * 7
    resp, body = upload(account, kind, "Scan.PDF", content)
    assert resp.status == 201
    assert_json(resp)
    saved = json.loads(body)
    assert list(saved) == ["customer", "kind", "file", "bytes"]
    assert saved["customer"] == account and saved["kind"] == kind and saved["bytes"] == len(content)
    assert re.fullmatch(re.escape(kind) + r"-\d{13}\.pdf", saved["file"])
    resp, body = request("GET", f"/documents/{account}")
    assert resp.status == 200
    assert_json(resp)
    names = json.loads(body)
    assert saved["file"] in names
    assert names == sorted(names)
    if STORED_CMD:
        assert hashlib.sha256(stored_bytes(account, saved["file"])).hexdigest() == hashlib.sha256(content).hexdigest()


def test_upload_response_golden():
    resp, body = upload("HG611000001", "passport", "scan.PDF", b"x" * 100)
    assert resp.status == 201
    golden("upload-passport.json", body)


@pytest.mark.parametrize("filename,ext", [
    ("Scan.PDF", ".pdf"), ("a.JPG", ".jpg"), ("b.jpeg", ".jpeg"), ("c.Png", ".png"), ("d.png", ".png"),
    ("run.sh", ".bin"), ("noext", ".bin"), ("x.pdf.exe", ".bin"), (".pdf", ".pdf"), ("", ".bin"),
])
def test_extension_mapping(filename, ext):
    resp, body = upload("HG621000002", "id-card", filename, b"y" * 10)
    assert resp.status == 201
    assert json.loads(body)["file"].endswith(ext)
    assert re.fullmatch(r"id-card-\d{13}" + re.escape(ext), json.loads(body)["file"])


def test_listing_is_sorted_by_name_across_kinds():
    customer = fresh_customer()
    files = []
    for kind in ["proof-of-address", "passport", "payslip", "id-card"]:
        resp, body = upload(customer, kind, "f.png", b"z")
        assert resp.status == 201
        files.append(json.loads(body)["file"])
        time.sleep(0.005)
    resp, body = request("GET", f"/documents/{customer}")
    assert json.loads(body) == sorted(files)
    golden("list-four-kinds.json", body)


def test_list_with_trailing_slash():
    customer = fresh_customer()
    resp, body = upload(customer, "passport", "p.pdf", b"p")
    name = json.loads(body)["file"]
    resp, body = request("GET", f"/documents/{customer}/")
    assert resp.status == 200
    assert json.loads(body) == [name]


def test_empty_file_is_stored():
    resp, body = upload("HG631000003", "proof-of-address", "e.pdf", b"")
    assert resp.status == 201
    assert json.loads(body)["bytes"] == 0


def test_size_just_under_the_limit_is_accepted():
    content = os.urandom(LIMIT - 1000)
    resp, body = upload("HG641000004", "payslip", "big.png", content)
    assert resp.status == 201
    saved = json.loads(body)
    assert saved["bytes"] == len(content)
    if STORED_CMD:
        assert hashlib.sha256(stored_bytes("HG641000004", saved["file"])).digest() == hashlib.sha256(content).digest()


@pytest.mark.parametrize("size", [LIMIT, LIMIT + 1024 * 1024])
def test_oversize_upload_is_a_500(size):
    resp, body = upload("HG641000004", "payslip", "big.png", b"\0" * size)
    assert resp.status == 500
    assert_json(resp)
    golden(f"oversize-{size}.json", body.replace("HG641000004", "<customer>"))


@pytest.mark.parametrize("customer", ["bad..id", "hg611000002", "HG611", "A" * 21, "HG61100000%21"])
def test_upload_rejects_bad_customer(customer):
    resp, body = upload(customer, "passport", "a.pdf", b"a")
    assert resp.status == 400
    assert_json(resp)
    assert body == '{"error":"bad customer id"}'


def test_bad_customer_with_dots_gets_rfd_content_disposition():
    resp, _ = upload("bad..id", "passport", "a.pdf", b"a")
    assert resp.getheader("Content-Disposition") == "inline;filename=f.txt"


@pytest.mark.parametrize("customer", ["hg611000002", "HG611", "A" * 21])
def test_list_rejects_bad_customer(customer):
    resp, body = request("GET", f"/documents/{customer}")
    assert resp.status == 400
    assert_json(resp)
    assert body == '{"error":"bad customer id"}'


@pytest.mark.parametrize("kind", ["selfie", "Passport", "", "passport%20"])
def test_upload_rejects_unknown_kind(kind):
    resp, body = upload("HG611000001", kind, "a.pdf", b"a")
    assert resp.status == 400
    assert body == '{"error":"unknown document kind"}'


def test_bad_customer_is_checked_before_kind():
    resp, body = upload("bad", "selfie", "a.pdf", b"a")
    assert resp.status == 400
    assert body == '{"error":"bad customer id"}'


def test_missing_kind_is_a_400():
    resp, body = upload("HG611000001", None, "a.pdf", b"a")
    assert resp.status == 400
    assert_json(resp)
    golden("missing-kind.json", body)


def test_missing_file_part_is_a_400():
    resp, body = upload("HG611000001", "passport", "a.pdf", b"a", field="other")
    assert resp.status == 400
    golden("missing-file-part.json", body)


def test_file_part_without_filename_is_a_400():
    resp, body = upload("HG611000001", "passport", None, b"abc")
    assert resp.status == 400
    golden("file-part-without-filename.json", body)


def test_post_that_is_not_multipart_is_a_500():
    resp, body = request("POST", "/documents/HG611000001?kind=passport")
    assert resp.status == 500
    assert_json(resp)
    golden("not-multipart.json", body)


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
def test_other_methods_are_405(method):
    resp, body = request(method, "/documents/HG611000001")
    assert resp.status == 405
    assert resp.getheader("Allow") == "GET, POST"
    golden(f"method-{method}.json", body)


@pytest.mark.parametrize("path,name", [("/", "root"), ("/documents", "documents"), ("/documents/HG611000001/x", "nested")])
def test_unknown_paths_are_404(path, name):
    resp, body = request("GET", path)
    assert resp.status == 404
    assert_json(resp)
    golden(f"not-found-{name}.json", body)


@pytest.mark.skipif(not LOGS_CMD, reason="KYC_LOGS_CMD not set")
def test_upload_writes_one_log_line():
    customer = fresh_customer()
    upload(customer, "payslip", "p.pdf", b"q" * 33)
    time.sleep(0.5)
    lines = [l for l in app_log().splitlines() if f"for {customer} " in l]
    assert len(lines) == 1
    assert re.search(r" INFO .*com\.bank\.kyc\.DocumentController\s+: stored payslip for " + customer + r" \(33 bytes\)$", lines[0])
