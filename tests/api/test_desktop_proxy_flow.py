"""Desktop (Electron) embedded-server flows against the real API gateway.

The Electron shell (frontend/client-app/desktop) serves the web build from an
embedded local server that reverse-proxies /api/v1/* to the gateway. These tests
start that server (compiled `desktop/build/server.js`) with Node, point it at
OTTERWORKS_API_BASE_URL, and drive the same API flows the renderer uses through
it. Requires `npm ci && npm run build` in frontend/client-app/desktop.
"""

import json
import os
import shutil
import socket
import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlparse

import httpx
import pytest


pytestmark = pytest.mark.api_flow

REPO_ROOT = Path(__file__).resolve().parents[2]
DESKTOP_DIR = REPO_ROOT / "frontend" / "client-app" / "desktop"
SERVER_JS = DESKTOP_DIR / "build" / "server.js"
INDEX_HTML = '<!doctype html><html><body><div id="root"></div></body></html>'

LAUNCHER = r"""
const { startAppServer } = require(process.argv[1]);
startAppServer({ webRoot: process.argv[2], gatewayUrl: process.argv[3], port: 0 })
  .then((app) => { process.stdout.write(app.url + "\n"); })
  .catch((err) => { console.error(err); process.exit(1); });
process.stdin.on("end", () => process.exit(0));
process.stdin.resume();
"""


class DesktopServer:
    def __init__(self, process: subprocess.Popen, url: str):
        self.process = process
        self.url = url
        parsed = urlparse(url)
        self.host = parsed.hostname
        self.port = parsed.port

    def raw_get(self, path: str) -> str:
        """Send an un-normalised request line (httpx would collapse dot-segments)."""
        with socket.create_connection((self.host, self.port), timeout=5) as sock:
            sock.sendall(f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode())
            chunks = []
            while chunk := sock.recv(65536):
                chunks.append(chunk)
        return b"".join(chunks).decode(errors="replace")


def _start_desktop_server(web_root: Path, gateway_url: str) -> DesktopServer:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    if not SERVER_JS.exists():
        pytest.skip(f"{SERVER_JS} missing; run `npm ci && npm run build` in {DESKTOP_DIR}")
    process = subprocess.Popen(
        [node, "-e", LAUNCHER, str(SERVER_JS), str(web_root), gateway_url],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    url = process.stdout.readline().strip()
    if not url.startswith("http://"):
        process.kill()
        raise AssertionError(f"desktop server failed to start: {process.stderr.read()}")
    return DesktopServer(process, url)


def _stop(server: DesktopServer) -> None:
    server.process.stdin.close()
    try:
        server.process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.process.kill()


@pytest.fixture(scope="module")
def desktop_web_root(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("desktop-dist")
    (root / "index.html").write_text(INDEX_HTML)
    return root


@pytest.fixture(scope="module")
def desktop_server(desktop_web_root: Path, base_url: str) -> Iterator[DesktopServer]:
    server = _start_desktop_server(desktop_web_root, base_url)
    try:
        yield server
    finally:
        _stop(server)


@pytest.fixture
def desktop_client(desktop_server: DesktopServer) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=desktop_server.url, timeout=httpx.Timeout(15.0, connect=3.0)) as client:
        yield client


def test_desktop_serves_spa_and_proxies_gateway_health(api_client, desktop_client):
    for route in ("/", "/login", "/files", "/documents/abc/edit"):
        page = desktop_client.get(route)
        assert page.status_code == 200, route
        assert page.text == INDEX_HTML, route

    direct = api_client.client.post("/api/v1/auth/login", json={})
    proxied = desktop_client.post("/api/v1/auth/login", json={})
    # Auth-service validation semantics belong to the auth area; the desktop proxy
    # must only pass status, content type and JSON body through unchanged.
    assert proxied.status_code == direct.status_code, proxied.text
    assert "application/json" in proxied.headers.get("content-type", "")
    assert proxied.json()["message"] == direct.json()["message"]


def test_desktop_register_login_profile_through_proxy(api_client, desktop_client):
    email = api_client.unique_email("desktop-auth")
    password = "OtterworksTest123!"
    register = desktop_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "displayName": "Desktop Flow"},
    )
    assert register.status_code == 201, register.text

    login = desktop_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    via_desktop = desktop_client.get("/api/v1/auth/profile", headers=headers)
    via_gateway = api_client.client.get("/api/v1/auth/profile", headers=headers)
    assert via_desktop.status_code == 200, via_desktop.text
    assert via_desktop.json() == via_gateway.json()
    assert via_desktop.json()["email"] == email

    wrong = {"email": email, "password": "wrong-password"}
    bad_login = desktop_client.post("/api/v1/auth/login", json=wrong)
    direct_bad_login = api_client.client.post("/api/v1/auth/login", json=wrong)
    assert bad_login.status_code == direct_bad_login.status_code, bad_login.text
    assert bad_login.status_code in (400, 401), bad_login.text
    assert "accessToken" not in bad_login.text


def test_desktop_protected_routes_require_auth_like_gateway(api_client, desktop_client):
    for route in ("/api/v1/auth/profile", "/api/v1/documents/", "/api/v1/files"):
        direct = api_client.client.get(route)
        proxied = desktop_client.get(route)
        assert proxied.status_code == direct.status_code, route
        assert proxied.status_code == 401, f"{route}: {proxied.status_code} {proxied.text}"


def test_desktop_document_create_list_open(api_client, desktop_client):
    user = api_client.register_user("desktop-docs")
    title = f"Desktop doc {uuid.uuid4().hex[:6]}"
    created = desktop_client.post(
        "/api/v1/documents/",
        headers=user.auth_headers,
        json={"title": title, "content": "Written from the desktop shell"},
    )
    assert created.status_code == 201, created.text
    document = created.json()
    api_client.created_documents.append(document["id"])

    opened = desktop_client.get(f"/api/v1/documents/{document['id']}", headers=user.auth_headers)
    assert opened.status_code == 200, opened.text
    assert opened.json()["title"] == title

    direct = api_client.client.get(f"/api/v1/documents/{document['id']}", headers=user.auth_headers)
    assert direct.json()["title"] == title

    listing = desktop_client.get("/api/v1/documents/", headers=user.auth_headers)
    assert listing.status_code == 200, listing.text
    assert title in json.dumps(listing.json())


def test_desktop_multipart_upload_and_file_listing(api_client, desktop_client):
    user = api_client.register_user("desktop-files")
    payload = os.urandom(256 * 1024)
    upload = desktop_client.post(
        "/api/v1/files/upload",
        headers=user.auth_headers,
        files={"file": ("desktop.bin", payload, "application/octet-stream")},
    )
    assert upload.status_code == 201, upload.text
    file_meta = upload.json()["file"]
    api_client.created_files.append(file_meta["id"])
    assert file_meta["owner_id"] == user.id
    assert int(file_meta.get("size_bytes", file_meta.get("size", len(payload)))) == len(payload)

    listing = desktop_client.get(
        "/api/v1/files",
        headers=user.auth_headers,
        params={"owner_id": user.id, "page": 1, "page_size": 10},
    )
    assert listing.status_code == 200, listing.text
    assert any(item["id"] == file_meta["id"] for item in listing.json()["files"])

    download = desktop_client.get(f"/api/v1/files/{file_meta['id']}/download", headers=user.auth_headers)
    assert download.status_code == 200, download.text
    assert download.json()["url"]


def test_desktop_gateway_down_returns_json_502(desktop_web_root):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        dead_port = probe.getsockname()[1]
    server = _start_desktop_server(desktop_web_root, f"http://127.0.0.1:{dead_port}")
    try:
        with httpx.Client(base_url=server.url, timeout=5) as client:
            login = client.post("/api/v1/auth/login", json={"email": "a@b.test", "password": "x"})
            assert login.status_code == 502
            assert login.json()["error"] == "bad_gateway"
            assert client.get("/login").text == INDEX_HTML
    finally:
        _stop(server)


@pytest.mark.gap_revealer
def test_desktop_proxy_does_not_expose_non_api_gateway_routes(desktop_server):
    """[REAL] `/api/v1/../../metrics` passes the raw /api/v1 prefix check but is
    forwarded as `/metrics`, exposing gateway-internal routes (Prometheus metrics)
    through the desktop origin. nginx normalises first and serves the SPA instead."""
    for path in ("/api/v1/../../metrics", "/api/v1/%2e%2e/%2e%2e/metrics"):
        response = desktop_server.raw_get(path)
        assert "api_gateway_http" not in response, f"{path} reached gateway /metrics"
