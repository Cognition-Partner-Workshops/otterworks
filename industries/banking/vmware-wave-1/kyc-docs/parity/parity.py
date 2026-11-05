#!/usr/bin/env python3
"""Capture ordered HTTP responses, distributing requests across base URLs."""
import argparse
import hashlib
import http.client
import json
from pathlib import Path
import ssl
from urllib.parse import urlsplit


FIXTURES = {
    "passport.pdf": b"%PDF-1.4\nfixed passport fixture\n%%EOF\n",
    "id-card.jpg": b"\xff\xd8\xfffixed ID card fixture\xff\xd9",
    "address.png": b"\x89PNG\r\n\x1a\nfixed proof of address fixture\x00",
    "payslip.JPEG": b"\xff\xd8\xfffixed uppercase extension payslip fixture\xff\xd9",
    "notes.exe": b"MZ fixed non-allowed extension fixture",
    "no-extension": b"fixed extensionless fixture\x00\x01",
}
BOUNDARY = "kyc-fixed-parity-boundary"


def multipart(filename=None):
    if filename is None:
        parts = ['Content-Disposition: form-data; name="other"\r\n\r\nvalue'.encode()]
    else:
        header = ('Content-Disposition: form-data; name="file"; filename="' + filename
                  + '"\r\nContent-Type: application/octet-stream\r\n\r\n').encode()
        parts = [header + FIXTURES[filename]]
    return b"".join(b"--" + BOUNDARY.encode() + b"\r\n" + part + b"\r\n"
                    for part in parts) + b"--" + BOUNDARY.encode() + b"--\r\n"


def cases():
    result = []
    def upload(name, customer, kind, filename):
        path = "/documents/" + customer
        if kind is not None:
            path += "?kind=" + kind
        result.append((name, "POST", path, multipart(filename),
                       "multipart/form-data; boundary=" + BOUNDARY))
    for customer in ("HG611000001", "HG621000002"):
        for kind, filename in (("passport", "passport.pdf"), ("id-card", "id-card.jpg"),
                               ("proof-of-address", "address.png"), ("payslip", "payslip.JPEG")):
            upload(customer + "-" + kind, customer, kind, filename)
    for name, customer in (("lowercase-id", "hg611000001"), ("short-id", "HG61"),
                            ("path-id", "..%2Fetc")):
        upload(name, customer, "passport", "passport.pdf")
    upload("unknown-kind", "HG611000001", "selfie", "passport.pdf")
    upload("exe-extension", "HG611000001", "passport", "notes.exe")
    upload("no-extension", "HG611000001", "id-card", "no-extension")
    upload("missing-kind", "HG611000001", None, "passport.pdf")
    upload("missing-file", "HG611000001", "passport", None)
    result.append(("non-multipart", "POST", "/documents/HG611000001?kind=passport",
                   b"plain request", "text/plain"))
    for name, path in (("list-first", "/documents/HG611000001"),
                       ("list-second", "/documents/HG621000002"),
                       ("list-empty", "/documents/HG631000003"),
                       ("list-bad-id", "/documents/hg611000001"),
                       ("documents-root", "/documents/"),
                       ("trailing-slash", "/documents/HG611000001/")):
        result.append((name, "GET", path, None, None))
    return result


def run(bases, insecure, out):
    out.mkdir(parents=True, exist_ok=True)
    index = []
    for i, (name, method, path, body, content_type) in enumerate(cases(), 1):
        base = urlsplit(bases[(i - 1) % len(bases)])
        if base.scheme not in ("http", "https") or not base.hostname or base.query or base.fragment:
            raise ValueError("base must be an HTTP(S) URL without query or fragment")
        if base.scheme == "https":
            context = ssl._create_unverified_context() if insecure else ssl.create_default_context()
            conn = http.client.HTTPSConnection(base.hostname, base.port, context=context, timeout=30)
        else:
            conn = http.client.HTTPConnection(base.hostname, base.port, timeout=30)
        try:
            conn.request(method, base.path.rstrip("/") + path, body=body,
                         headers={"Content-Type": content_type} if content_type else {})
            response = conn.getresponse()
            record = dict(case=name, method=method, path=path, status=response.status,
                          content_type=response.getheader("Content-Type", ""), body=response.read().decode("utf-8"))
        finally:
            conn.close()
        filename = f"{i:02d}-{name}.json"
        (out / filename).write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        index.append(filename)
        print(f"{i:02d} {name}: {record['status']} {record['content_type']}")
    (out / "cases.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    fixtures = {name: dict(size=len(data), sha256=hashlib.sha256(data).hexdigest())
                for name, data in FIXTURES.items()}
    (out / "fixtures.json").write_text(json.dumps(fixtures, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", action="append", required=True)
    parser.add_argument("--insecure", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.base, args.insecure, args.out)
