"""Black-box flows through the Electron desktop shell's embedded server.

The desktop app (frontend/client-app/desktop) serves the web build from a local
loopback server that reverse-proxies /api/v1/* to the API gateway. These tests
start that server (compiled build/server.js) in a Node subprocess pointed at the
real gateway and drive auth, files and documents through it, the same way the
Electron renderer does. Skipped when node or the desktop build is unavailable.
"""

import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import base64
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest


pytestmark = pytest.mark.api_flow

REPO_ROOT = Path(__file__).resolve().parents[2]
DESKTOP_DIR = REPO_ROOT / "frontend" / "client-app" / "desktop"
SERVER_JS = DESKTOP_DIR / "build" / "server.js"

LAUNCHER = """
const { startAppServer } = require(process.argv[1]);
startAppServer({ webRoot: process.argv[2], gatewayUrl: process.argv[3], port: 0 })
  .then((s) => { console.log(JSON.stringify({ url: s.url })); })
  .catch((e) => { console.error(e); process.exit(1); });
"""

INDEX_HTML = '<!doctype html><html><body><div id="root"></div></body></html>'


@pytest.fixture(scope="module")
def desktop_server(base_url: str) -> Iterator[str]:
    node = shutil.which("node")
    if not node or not SERVER_JS.exists():
        pytest.skip("node or desktop build missing (run `npm ci && npm run build` in frontend/client-app/desktop)")
    web_root = Path(tempfile.mkdtemp(prefix="otter-desktop-api-"))
    (web_root / "index.html").write_text(INDEX_HTML)
    proc = subprocess.Popen(
        [node, "-e", LAUNCHER, str(SERVER_JS), str(web_root), base_url],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        line = proc.stdout.readline()
        if not line:
            pytest.fail(f"desktop server failed to start: {proc.stderr.read()}")
        yield json.loads(line)["url"]
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        shutil.rmtree(web_root, ignore_errors=True)


@pytest.fixture
def desktop(desktop_server: str) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=desktop_server, timeout=httpx.Timeout(15.0, connect=3.0)) as client:
        yield client


def test_desktop_serves_spa_shell_for_client_routes(desktop, api_client):
    for route in ("/", "/login", "/dashboard", "/files", "/documents/abc"):
        response = desktop.get(route)
        assert response.status_code == 200, route
        assert '<div id="root">' in response.text


def test_desktop_proxy_register_login_and_profile(desktop, api_client):
    email = api_client.unique_email("desktop-proxy")
    password = "OtterworksTest123!"
    register = desktop.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "displayName": "Desktop Proxy"},
    )
    assert register.status_code == 201, register.text

    login = desktop.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    tokens = login.json()
    assert tokens["accessToken"] and tokens["refreshToken"]

    me = desktop.get("/api/v1/auth/profile", headers={"Authorization": f"Bearer {tokens['accessToken']}"})
    assert me.status_code == 200, me.text
    assert me.json()["email"] == email

    bad = desktop.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password"})
    assert bad.status_code in {400, 401}


def test_desktop_proxy_requires_auth_like_the_gateway(desktop, api_client):
    direct = api_client.client.get("/api/v1/files")
    proxied = desktop.get("/api/v1/files")
    assert proxied.status_code == direct.status_code == 401


def test_desktop_proxy_file_upload_listing_and_download(desktop, api_client):
    owner = api_client.register_user("desktop-files")
    headers = owner.auth_headers

    folder = desktop.post("/api/v1/folders", headers=headers, json={"name": f"Desktop {api_client.run_id}", "owner_id": owner.id})
    assert folder.status_code == 201, folder.text
    api_client.created_folders.append(folder.json()["id"])

    upload = desktop.post(
        "/api/v1/files/upload",
        headers=headers,
        files={"file": ("desktop.txt", b"uploaded through the desktop proxy", "text/plain")},
        data={"owner_id": owner.id, "folder_id": folder.json()["id"]},
    )
    assert upload.status_code == 201, upload.text
    file_id = upload.json()["file"]["id"]
    api_client.created_files.append(file_id)

    listing = desktop.get("/api/v1/files", headers=headers, params={"folder_id": folder.json()["id"]})
    assert listing.status_code == 200, listing.text
    assert any(item["id"] == file_id for item in listing.json()["files"])

    folders = desktop.get("/api/v1/folders", headers=headers)
    assert folders.status_code == 200
    assert any(f["id"] == folder.json()["id"] for f in folders.json()["folders"])

    detail = desktop.get(f"/api/v1/files/{file_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["name"] == "desktop.txt"

    download = desktop.get(f"/api/v1/files/{file_id}/download", headers=headers)
    assert download.status_code == 200, download.text


def test_desktop_proxy_document_create_edit_and_delete(desktop, api_client):
    owner = api_client.register_user("desktop-docs")
    headers = owner.auth_headers

    created = desktop.post("/api/v1/documents/", headers=headers, json={"title": "Desktop doc", "content": "<p>v1</p>"})
    assert created.status_code == 201, created.text
    doc_id = created.json()["id"]
    api_client.created_documents.append(doc_id)

    updated = desktop.put(f"/api/v1/documents/{doc_id}", headers=headers, json={"title": "Desktop doc", "content": "<p>v2 from desktop</p>"})
    assert updated.status_code == 200, updated.text

    fetched = desktop.get(f"/api/v1/documents/{doc_id}", headers=headers)
    assert fetched.status_code == 200
    assert "v2 from desktop" in fetched.json()["content"]

    via_gateway = api_client.client.get(f"/api/v1/documents/{doc_id}", headers=headers)
    assert via_gateway.json()["content"] == fetched.json()["content"]

    deleted = desktop.delete(f"/api/v1/documents/{doc_id}", headers=headers)
    assert deleted.status_code in {200, 204}, deleted.text


def test_desktop_proxy_reports_gateway_outage_as_502(base_url):
    node = shutil.which("node")
    if not node or not SERVER_JS.exists():
        pytest.skip("node or desktop build missing")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        dead_port = s.getsockname()[1]
    web_root = Path(tempfile.mkdtemp(prefix="otter-desktop-api-"))
    (web_root / "index.html").write_text(INDEX_HTML)
    proc = subprocess.Popen(
        [node, "-e", LAUNCHER, str(SERVER_JS), str(web_root), f"http://127.0.0.1:{dead_port}"],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        url = json.loads(proc.stdout.readline())["url"]
        response = httpx.get(f"{url}/api/v1/files", timeout=10)
        assert response.status_code == 502
        assert response.json()["error"] == "bad_gateway"
        assert httpx.get(f"{url}/files", timeout=10).status_code == 200
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        shutil.rmtree(web_root, ignore_errors=True)


def _ws_upgrade(url: str, path: str, timeout: float) -> str:
    host, port = url.removeprefix("http://").split(":")
    key = base64.b64encode(os.urandom(16)).decode()
    with socket.create_connection((host, int(port)), timeout=timeout) as sock:
        sock.sendall(
            (
                f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: Upgrade\r\n"
                f"Upgrade: websocket\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
            ).encode()
        )
        try:
            data = sock.recv(1024)
        except TimeoutError:
            return "timeout"
        return data.decode(errors="replace").split("\r\n", 1)[0] or "closed"


@pytest.mark.gap_revealer
@pytest.mark.xfail(
    reason="[REAL] DESKTOP-03: desktop proxyUpgrade ignores a non-101 gateway reply, so the client socket hangs",
    strict=True,
)
def test_desktop_proxy_answers_rejected_websocket_upgrade(desktop_server, api_client):
    direct = api_client.client.get("/api/v1/documents/ws", headers={"Connection": "Upgrade", "Upgrade": "websocket"})
    assert direct.status_code != 101
    start = time.monotonic()
    status_line = _ws_upgrade(desktop_server, "/api/v1/documents/ws", timeout=5)
    assert status_line != "timeout", f"no reply after {time.monotonic() - start:.1f}s"
