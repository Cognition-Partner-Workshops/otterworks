"""QA integration tests for the Electron desktop shell's embedded server.

The desktop app (frontend/client-app/desktop) serves the client-app `dist/`
build from a local server that reverse-proxies /api/v1/* to the API gateway.
These tests boot that real server (compiled build/server.js) with Node against
the running local gateway and drive the core desktop flows through it:
register/login, profile, files, documents, error passthrough, offline handling
and the collab websocket the bundle connects to.

Requires: `npm run build` in frontend/client-app (dist/) and in
frontend/client-app/desktop (build/), plus the local stack (`make up`).
"""

import json
import os
import re
import shutil
import socket
import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import socketio


pytestmark = pytest.mark.api_flow

REPO_ROOT = Path(__file__).resolve().parents[2]
CLIENT_APP = REPO_ROOT / "frontend" / "client-app"
DESKTOP = CLIENT_APP / "desktop"
DIST = CLIENT_APP / "dist"
SERVER_JS = DESKTOP / "build" / "server.js"

BOOT_SCRIPT = """
const { startAppServer } = require(process.argv[1]);
startAppServer({ webRoot: process.argv[2], gatewayUrl: process.argv[3], port: 0 })
  .then((s) => console.log("URL " + s.url))
  .catch((e) => { console.error(e); process.exit(1); });
"""


def _start_desktop_server(gateway_url: str) -> tuple[subprocess.Popen, str]:
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    if not SERVER_JS.exists() or not (DIST / "index.html").exists():
        pytest.skip("desktop build/ or client-app dist/ missing; run the desktop + web builds first")
    proc = subprocess.Popen(
        ["node", "-e", BOOT_SCRIPT, str(SERVER_JS), str(DIST), gateway_url],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    line = proc.stdout.readline()
    match = re.match(r"URL (http://\S+)", line)
    if not match:
        proc.kill()
        raise AssertionError(f"desktop server failed to start: {line} {proc.stderr.read()}")
    return proc, match.group(1)


@pytest.fixture(scope="module")
def desktop_url(base_url: str) -> Iterator[str]:
    proc, url = _start_desktop_server(base_url)
    try:
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=5)


@pytest.fixture
def desktop(desktop_url: str) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=desktop_url, timeout=httpx.Timeout(15.0, connect=3.0)) as client:
        yield client


def _register_via_desktop(desktop: httpx.Client, run_id: str) -> dict:
    password = "OtterworksTest123!"
    email = f"qa-electron-{run_id}-{uuid.uuid4().hex[:8]}@example.test"
    response = desktop.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "displayName": "QA Electron"},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    return {
        "email": email,
        "password": password,
        "id": data["user"]["id"],
        "token": data["accessToken"],
        "headers": {"Authorization": f"Bearer {data['accessToken']}"},
    }


def test_desktop_serves_spa_shell_and_client_routes(desktop):
    for route in ["/", "/login", "/dashboard", "/files", "/documents/does-not-matter", "/settings"]:
        response = desktop.get(route)
        assert response.status_code == 200, route
        assert response.headers["content-type"].startswith("text/html")
        assert '<div id="root">' in response.text, route


def test_desktop_bundle_assets_are_served_with_immutable_cache(desktop):
    index = desktop.get("/").text
    assets = re.findall(r'/assets/[^"]+\.(?:js|css)', index)
    assert assets, "index.html references no hashed assets"
    for asset in assets:
        response = desktop.get(asset)
        assert response.status_code == 200, asset
        assert response.headers.get("cache-control") == "public, max-age=31536000, immutable"


def test_desktop_bundle_points_collab_ws_at_compose_port():
    bundle = "".join(p.read_text(errors="ignore") for p in (DIST / "assets").glob("*.js"))
    assert "ws://localhost:8084" in bundle, "dist/ was not built with VITE_COLLAB_WS_URL=ws://localhost:8084"


def test_register_login_and_profile_through_desktop_proxy(desktop, run_id):
    user = _register_via_desktop(desktop, run_id)
    login = desktop.post("/api/v1/auth/login", json={"email": user["email"], "password": user["password"]})
    assert login.status_code == 200, login.text
    body = login.json()
    assert body["tokenType"] == "Bearer"
    assert body["accessToken"] and body["refreshToken"]

    profile = desktop.get("/api/v1/auth/profile", headers={"Authorization": f"Bearer {body['accessToken']}"})
    assert profile.status_code == 200, profile.text
    assert profile.json()["email"] == user["email"]


def test_invalid_login_and_unauthenticated_calls_pass_through_as_json(desktop):
    bad = desktop.post(
        "/api/v1/auth/login",
        json={"email": f"nobody-{uuid.uuid4().hex[:6]}@example.test", "password": "wrong-password-1"},
    )
    assert bad.status_code in (400, 401), bad.text
    assert "application/json" in bad.headers.get("content-type", "")

    anon = desktop.get("/api/v1/auth/profile")
    assert anon.status_code == 401, anon.text


def test_proxy_matches_direct_gateway_for_files_list(desktop, api_client, run_id):
    user = _register_via_desktop(desktop, run_id)
    params = {"owner_id": user["id"], "page": 1, "page_size": 10}
    via_desktop = desktop.get("/api/v1/files", headers=user["headers"], params=params)
    direct = api_client.client.get("/api/v1/files", headers=user["headers"], params=params)
    assert via_desktop.status_code == direct.status_code == 200, via_desktop.text
    assert via_desktop.json() == direct.json()


def test_file_upload_list_and_download_through_desktop_proxy(desktop, api_client, run_id):
    user = _register_via_desktop(desktop, run_id)
    content = f"electron qa {run_id}".encode()
    upload = desktop.post(
        "/api/v1/files/upload",
        headers=user["headers"],
        files={"file": ("electron-qa.txt", content, "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    file_id = upload.json()["file"]["id"]
    api_client.created_files.append(file_id)

    listing = desktop.get(
        "/api/v1/files", headers=user["headers"], params={"owner_id": user["id"], "page": 1, "page_size": 10}
    )
    assert listing.status_code == 200, listing.text
    assert file_id in json.dumps(listing.json())

    meta = desktop.get(f"/api/v1/files/{file_id}", headers=user["headers"])
    assert meta.status_code == 200, meta.text


def test_document_create_open_and_edit_through_desktop_proxy(desktop, api_client, run_id):
    user = _register_via_desktop(desktop, run_id)
    created = desktop.post(
        "/api/v1/documents/",
        headers=user["headers"],
        json={"title": f"Electron QA {run_id}", "content": "hello from the desktop shell"},
    )
    assert created.status_code == 201, created.text
    doc = created.json()
    api_client.created_documents.append(doc["id"])

    opened = desktop.get(f"/api/v1/documents/{doc['id']}", headers=user["headers"])
    assert opened.status_code == 200, opened.text
    assert opened.json()["title"] == f"Electron QA {run_id}"

    # Visible through the gateway directly too (same backend, no desktop-side caching)
    direct = api_client.client.get(f"/api/v1/documents/{doc['id']}", headers=user["headers"])
    assert direct.status_code == 200
    assert direct.json()["id"] == doc["id"]


def test_non_api_paths_are_not_proxied_to_gateway(desktop):
    # The gateway answers /health with JSON; the desktop server must serve the SPA instead.
    response = desktop.get("/health")
    assert response.status_code == 200
    assert '<div id="root">' in response.text


def test_desktop_offline_gateway_returns_502_json(run_id):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        dead_port = s.getsockname()[1]
    proc, url = _start_desktop_server(f"http://127.0.0.1:{dead_port}")
    try:
        with httpx.Client(base_url=url, timeout=5) as client:
            login = client.post("/api/v1/auth/login", json={"email": "a@b.c", "password": "x"})
            assert login.status_code == 502
            assert login.json()["error"] == "bad_gateway"
            shell = client.get("/login")
            assert shell.status_code == 200 and '<div id="root">' in shell.text
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_collab_websocket_used_by_desktop_bundle_accepts_desktop_token(desktop, run_id):
    collab_url = os.getenv("OTTERWORKS_DESKTOP_COLLAB_URL", "http://localhost:8084")
    user = _register_via_desktop(desktop, run_id)
    client = socketio.Client(reconnection=False, request_timeout=5)
    try:
        client.connect(collab_url, auth={"token": user["token"]}, transports=["websocket"])
        assert client.connected
    finally:
        if client.connected:
            client.disconnect()
