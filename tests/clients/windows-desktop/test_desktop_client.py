"""Characterization tests for clients/windows-desktop.

They pin what the shipped executable does - the HTTP calls it makes, the text it shows and
the DPAPI session file it writes - by driving the real window via UI Automation against
``gateway_stub``. The same tests run unchanged against the .NET Framework 4.8 build and the
.NET 8 build; only ``OTTERWORKS_DESKTOP_EXE`` changes.
"""

from __future__ import annotations

import json
import socket
import uuid
from pathlib import Path
from typing import Any

from desktop_driver import dpapi_unprotect, session_store_path

NAME = "Ada Otter"
EMAIL = "ada@otterworks.test"
PASSWORD = "otterpass123"
TITLE = "Quarterly otter report"


def normalized(stub) -> list[dict[str, Any]]:
    """Request log with tokens replaced by their issue order, ready for before/after diffing."""
    tokens = {tok: f"<token#{i}>" for i, tok in enumerate(stub.issued_tokens, start=1)}
    out = []
    for req in stub.requests:
        headers = {k.lower(): v for k, v in req["headers"].items()}
        auth = headers.get("authorization")
        if auth and auth.startswith("Bearer "):
            auth = "Bearer " + tokens.get(auth[7:], "<unknown token>")
        out.append(
            {
                "method": req["method"],
                "path": req["path"],
                "query": req["query"],
                "body": req["body"],
                "authorization": auth,
                "content_type": headers.get("content-type"),
                "header_names": sorted(headers),
            }
        )
    return out


def seed_user(stub, email: str = EMAIL, password: str = PASSWORD, name: str = NAME) -> None:
    stub.state.users[email] = {"id": str(uuid.uuid4()), "email": email, "password": password, "displayName": name}


def snap(app, directory: Path | None, name: str, record: dict) -> None:
    record.setdefault("screens", {})[name] = app.texts()
    if directory is not None:
        app.screenshot(directory / f"{name}.png")


def test_register_documents_logout_login_flow(desktop_exe, stub, launch, screenshot_dir, record):
    app = launch(desktop_exe, stub.base_url)
    app.wait_for_text("Welcome back to OtterWorks.")
    record["start_screen"] = app.heading()
    assert record["start_screen"] == "Sign in"

    app.click("Create one")
    app.wait_for_text("Get started with OtterWorks.")
    app.fill(NAME, EMAIL, PASSWORD)
    snap(app, screenshot_dir, "01-register", record)

    app.click("Create account")
    app.wait_for_text("No documents yet")
    app.wait_idle()
    assert app.has_text("0 document(s).")
    assert app.has_text(f"Signed in as {NAME}")
    snap(app, screenshot_dir, "02-documents-empty", record)

    app.fill(TITLE)
    app.click("New")
    app.wait_for_text(TITLE)
    app.wait_for_text("1 document(s).")
    app.wait_idle()
    assert not app.has_text("No documents yet")
    snap(app, screenshot_dir, "03-document-created", record)

    app.click("Log out")
    app.wait_for_text("Welcome back to OtterWorks.")
    assert not any(t.startswith("Signed in as") for t in app.texts())
    snap(app, screenshot_dir, "04-logged-out", record)

    app.fill(EMAIL, PASSWORD)
    app.click("Sign in")
    app.wait_for_text(TITLE)
    app.wait_for_text("1 document(s).")
    app.wait_idle()
    snap(app, screenshot_dir, "05-document-persists", record)

    app.click("Files")
    app.wait_for_text("1 file(s).")
    app.wait_idle()

    requests = normalized(stub)
    record["requests"] = requests
    assert [(r["method"], r["path"], r["query"]) for r in requests] == [
        ("POST", "/api/v1/auth/register", {}),
        ("GET", "/api/v1/documents", {"page": ["1"], "size": ["50"]}),
        ("POST", "/api/v1/documents", {}),
        ("GET", "/api/v1/documents", {"page": ["1"], "size": ["50"]}),
        ("POST", "/api/v1/auth/login", {}),
        ("GET", "/api/v1/documents", {"page": ["1"], "size": ["50"]}),
        ("GET", "/api/v1/files", {"page": ["1"], "page_size": ["50"]}),
    ]
    assert requests[0]["body"] == {"displayName": NAME, "email": EMAIL, "password": PASSWORD}
    assert requests[2]["body"] == {"title": TITLE}
    assert requests[4]["body"] == {"email": EMAIL, "password": PASSWORD}
    assert [r["authorization"] for r in requests] == [
        None,
        "Bearer <token#1>",
        "Bearer <token#1>",
        "Bearer <token#1>",
        None,
        "Bearer <token#2>",
        "Bearer <token#2>",
    ]
    for r in requests:
        if r["method"] == "POST":
            assert r["content_type"] == "application/json; charset=utf-8"

    assert not session_store_path().exists(), "tokens must not be persisted unless persistTokens is on"


def test_login_with_wrong_password_shows_server_message(desktop_exe, stub, launch, record):
    seed_user(stub)
    app = launch(desktop_exe, stub.base_url)
    app.wait_for_text("Welcome back to OtterWorks.")
    app.fill(EMAIL, "not-the-password")
    app.click("Sign in")
    app.wait_for_text("Invalid credentials")
    app.wait_idle()
    record["screen"] = app.texts()
    record["requests"] = normalized(stub)
    assert app.heading() == "Sign in"


def test_duplicate_registration_shows_server_message(desktop_exe, stub, launch, record):
    seed_user(stub)
    app = launch(desktop_exe, stub.base_url)
    app.click("Create one")
    app.wait_for_text("Get started with OtterWorks.")
    app.fill(NAME, EMAIL, PASSWORD)
    app.click("Create account")
    app.wait_for_text("Email already registered")
    app.wait_idle()
    record["screen"] = app.texts()
    record["requests"] = normalized(stub)


def test_short_password_is_rejected_before_calling_the_api(desktop_exe, stub, launch, record):
    app = launch(desktop_exe, stub.base_url)
    app.click("Create one")
    app.wait_for_text("Get started with OtterWorks.")
    app.fill(NAME, EMAIL, "short")
    app.click("Create account")
    app.wait_for_text("Password must be at least 8 characters.")
    record["screen"] = app.texts()
    assert stub.requests == []


def test_unreachable_backend_reports_connection_error(desktop_exe, launch, record):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    app = launch(desktop_exe, f"http://127.0.0.1:{port}/api/v1")
    app.wait_for_text("Welcome back to OtterWorks.")
    app.fill(EMAIL, PASSWORD)
    app.click("Sign in")
    message = app.wait_for_text_prefix("Could not reach the OtterWorks backend.", timeout=40)
    headline, _, detail = message.partition("\n\n")
    record["headline"] = headline
    record["transport_detail"] = detail
    assert headline == (
        "Could not reach the OtterWorks backend. Verify it is running and that the API base URL is correct."
    )


def _register(app) -> None:
    app.wait_for_text("Welcome back to OtterWorks.")
    app.click("Create one")
    app.wait_for_text("Get started with OtterWorks.")
    app.fill(NAME, EMAIL, PASSWORD)
    app.click("Create account")
    app.wait_for_text("No documents yet")
    app.wait_idle()


def test_persisted_session_is_dpapi_protected_and_restored(desktop_exe, stub, launch, record):
    store = session_store_path()
    first = launch(desktop_exe, stub.base_url, persist_tokens=True)
    _register(first)
    first.close()

    token = stub.issued_tokens[0]
    raw = store.read_bytes()
    assert token.encode() not in raw and EMAIL.encode() not in raw, "session.dat must not be plaintext"
    session = json.loads(dpapi_unprotect(raw).decode("utf-8"))
    assert session["AccessToken"] == token
    assert session["User"]["email"] == EMAIL
    assert session["User"]["displayName"] == NAME
    record["session_shape"] = {
        "keys": sorted(session),
        "user_keys": sorted(session["User"]),
        "refresh_token_present": bool(session.get("RefreshToken")),
    }

    second = launch(desktop_exe, stub.base_url, persist_tokens=True)
    second.wait_for_text("No documents yet")
    second.wait_idle()
    assert second.has_text(f"Signed in as {NAME}")
    assert normalized(stub)[-1]["authorization"] == "Bearer <token#1>"
    record["restored_screen"] = second.texts()

    second.click("Log out")
    second.wait_for_text("Welcome back to OtterWorks.")
    assert not store.exists(), "logging out must delete the persisted session"


def test_session_written_by_peer_build_is_restored(desktop_exe, peer_exe, stub, launch, record):
    writer = launch(peer_exe, stub.base_url, persist_tokens=True)
    _register(writer)
    writer.close()
    assert session_store_path().exists()

    reader = launch(desktop_exe, stub.base_url, persist_tokens=True)
    reader.wait_for_text("No documents yet")
    reader.wait_idle()
    assert reader.has_text(f"Signed in as {NAME}")
    assert normalized(stub)[-1]["authorization"] == "Bearer <token#1>"
    record["restored_screen"] = reader.texts()
