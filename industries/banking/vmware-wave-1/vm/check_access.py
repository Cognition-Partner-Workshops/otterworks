"""Check legitimate and rejected requests against local, loopback-only VM stand-ins."""

import base64
import hashlib
import hmac
import json
import os
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def encoded(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def token(subject, role):
    header = encoded(b'{"alg":"HS256","typ":"JWT"}')
    payload = encoded(
        json.dumps(
            {
                "sub": subject,
                "roles": [role],
                "type": "access",
                "exp": int(time.time()) + 300,
            }
        ).encode()
    )
    data = f"{header}.{payload}"
    signature = hmac.new(
        os.environ["JWT_SECRET"].encode(), data.encode(), hashlib.sha256
    ).digest()
    return "Bearer " + data + "." + encoded(signature)


def request(port, path, authorization=None, body=None, content_type="application/json"):
    headers = {"Content-Type": content_type}
    if authorization:
        headers["Authorization"] = authorization
    scheme = "https" if port == 8085 else "http"
    req = Request(f"{scheme}://127.0.0.1:{port}{path}", headers=headers, data=body)
    try:
        # This self-signed TLS exception is restricted to the loopback-only fixture.
        with urlopen(
            req, timeout=5, context=ssl._create_unverified_context()
        ) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


def check(expected, *args, **kwargs):
    status, body = request(*args, **kwargs)
    assert status == expected, f"{args[:2]}: expected {expected}, received {status}"
    return body


def main():
    for key in (
        "BANK_VM_PASSWORD",
        "NOTIFY_SERVICE_TOKEN",
        "NOTIFY_OUTBOX_TOKEN",
        "JWT_SECRET",
    ):
        if not os.environ.get(key):
            raise RuntimeError(f"Set {key} before starting the VM stand-ins")
    owner = (
        "Basic "
        + base64.b64encode(
            f"smoke-owner:{os.environ['BANK_VM_PASSWORD']}".encode()
        ).decode()
    )
    for port, path, authorization in [
        (8081, "/statements/accounts", owner),
        (8085, "/documents/HG611000001", token("auditor", "COMPLIANCE")),
    ]:
        for attempt in range(40):
            try:
                if request(port, path, authorization)[0] == 200:
                    break
            except (URLError, TimeoutError):
                pass
            time.sleep(3)
        else:
            raise RuntimeError(
                f"Authenticated stand-in on port {port} did not become ready"
            )
    check(401, 8081, "/statements/accounts")
    check(401, 8081, "/statements/statement?account=HG611000001")
    check(200, 8081, "/statements/statement?account=HG611000001", owner)
    check(403, 8081, "/statements/statement?account=HG621000002", owner)
    message = json.dumps(
        {"account": "HG611000001", "kind": "statement_ready", "fields": {}}
    ).encode()
    service = "Bearer " + os.environ["NOTIFY_SERVICE_TOKEN"]
    consumer = "Bearer " + os.environ["NOTIFY_OUTBOX_TOKEN"]
    check(401, 8084, "/notify", body=message)
    check(202, 8084, "/notify", service, message)
    check(401, 8084, "/outbox/HG611000001")
    check(401, 8084, "/outbox/HG611000001", service)
    messages = json.loads(check(200, 8084, "/outbox/HG611000001", consumer))
    assert messages and all(msg["account"] == "****0001" for msg in messages)
    check(401, 8085, "/documents/HG611000001")
    check(403, 8085, "/documents/HG611000001", token("customer", "USER"))
    check(200, 8085, "/documents/HG611000001", token("auditor", "COMPLIANCE"))
    multipart = (
        '--fixture\r\nContent-Disposition: form-data; name="kind"\r\n\r\npassport\r\n'
        '--fixture\r\nContent-Disposition: form-data; name="file"; filename="smoke.txt"\r\n'
        "Content-Type: text/plain\r\n\r\nsynthetic fixture\r\n--fixture--\r\n"
    ).encode()
    check(
        401,
        8085,
        "/documents/HG611000001",
        body=multipart,
        content_type="multipart/form-data; boundary=fixture",
    )
    check(
        201,
        8085,
        "/documents/HG611000001",
        token("onboarding-service", "SERVICE"),
        multipart,
        "multipart/form-data; boundary=fixture",
    )
    print(
        "Authenticated banking controls and anonymous/non-owner rejection checks passed"
    )


if __name__ == "__main__":
    main()
