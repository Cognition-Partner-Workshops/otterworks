# /// script
# requires-python = ">=3.12"
# dependencies = ["PyJWT==2.9.0"]
# ///
"""Seed isolated synthetic bank documents through document-service."""

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OWNER_ID = "bada5eed-a001-4000-8000-000000000001"
FOLDER_ID = "bada5eed-f001-4000-8000-000000000001"
DOCUMENTS = Path(__file__).with_name("documents.json")
ENDPOINT = "/api/v1/documents/"


def build_payloads():
    return [
        {**document, "owner_id": OWNER_ID, "folder_id": FOLDER_ID}
        for document in json.loads(DOCUMENTS.read_text())
    ]


def content_digest(payloads):
    canonical = json.dumps(
        payloads, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def bearer():
    import jwt

    token = jwt.encode(
        {"user_id": OWNER_ID, "sub": OWNER_ID, "exp": int(time.time()) + 6 * 3600},
        os.environ.get(
            "JWT_SECRET", "otterworks-local-dev-jwt-secret-change-me-in-production"
        ),
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def request_json(url, headers, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = Request(
        url, data=data, headers={**headers, "Content-Type": "application/json"}
    )
    with urlopen(request, timeout=60) as response:
        if payload is not None and response.status != 201:
            raise RuntimeError(
                f"Document creation returned HTTP {response.status}, expected 201"
            )
        return json.load(response)


def seed_documents(base_url, headers):
    endpoint = base_url.rstrip("/") + ENDPOINT
    existing = set()
    page = 1
    while True:
        query = urlencode({"owner_id": OWNER_ID, "page": page, "size": 100})
        body = request_json(f"{endpoint}?{query}", headers)
        existing.update(item["title"] for item in body["items"])
        if page * 100 >= body["total"]:
            break
        page += 1
    created = 0
    for payload in build_payloads():
        if payload["title"] not in existing:
            request_json(endpoint, headers, payload)
            existing.add(payload["title"])
            created += 1
    return created


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    payloads = build_payloads()
    if args.dry_run:
        print(json.dumps(payloads, indent=2, ensure_ascii=False))
    else:
        base_url = os.environ.get("INCIDENT_BASE_URL", "http://localhost:8083")
        created = seed_documents(base_url, bearer())
        print(
            f"owner_id={OWNER_ID} created={created} skipped={len(payloads) - created}"
        )
    print(f"sha256={content_digest(payloads)}")


if __name__ == "__main__":
    main()
