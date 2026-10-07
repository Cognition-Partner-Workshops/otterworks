"""Fixtures that run the real OtterWorks Desktop executable against the gateway stub.

Required: ``OTTERWORKS_DESKTOP_EXE`` = path to the built ``OtterWorks.Desktop.exe``.
Optional: ``OTTERWORKS_DESKTOP_PEER_EXE`` = a second build for the cross-build session test,
``OTTERWORKS_SCREENSHOT_DIR`` = where the flow screenshots go,
``OTTERWORKS_RESULTS_DIR`` = where each test writes its normalized observations (parity input).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from desktop_driver import DesktopApp, session_store_path  # noqa: E402
from gateway_stub import GatewayStub  # noqa: E402


def _exe_from_env(name: str) -> Path | None:
    value = os.environ.get(name)
    if not value:
        return None
    path = Path(value).resolve()
    if not path.is_file():
        raise pytest.UsageError(f"{name}={value} does not exist")
    return path


@pytest.fixture(scope="session")
def desktop_exe() -> Path:
    exe = _exe_from_env("OTTERWORKS_DESKTOP_EXE")
    if exe is None:
        pytest.skip("OTTERWORKS_DESKTOP_EXE is not set")
    return exe


@pytest.fixture(scope="session")
def peer_exe() -> Path:
    exe = _exe_from_env("OTTERWORKS_DESKTOP_PEER_EXE")
    if exe is None:
        pytest.skip("OTTERWORKS_DESKTOP_PEER_EXE is not set")
    return exe


@pytest.fixture
def stub() -> Iterator[GatewayStub]:
    with GatewayStub() as running:
        yield running


@pytest.fixture(autouse=True)
def isolated_session_store() -> Iterator[Path]:
    """Moves any real session.dat under %APPDATA% aside for the duration of a test."""
    store = session_store_path()
    backup = store.with_name("session.dat.pytest-backup")
    if backup.exists():
        # Left by an interrupted run: the backup is the real session, the store is test residue.
        store.unlink(missing_ok=True)
    elif store.exists():
        shutil.move(store, backup)
    try:
        yield store
    finally:
        store.unlink(missing_ok=True)
        if backup.exists():
            shutil.move(backup, store)


@pytest.fixture
def launch(tmp_path: Path) -> Iterator[Callable[..., DesktopApp]]:
    """Copies a build to a scratch dir with its own appsettings.json and starts it."""
    apps: list[DesktopApp] = []

    def _launch(exe: Path, api_base_url: str, persist_tokens: bool = False) -> DesktopApp:
        target = tmp_path / f"app{len(apps)}"
        if not target.exists():
            shutil.copytree(exe.parent, target)
        (target / "appsettings.json").write_text(
            json.dumps({"apiBaseUrl": api_base_url, "persistTokens": persist_tokens}), encoding="utf-8"
        )
        app = DesktopApp.start(target / exe.name)
        apps.append(app)
        return app

    yield _launch
    for app in apps:
        app.kill()


@pytest.fixture
def screenshot_dir() -> Path | None:
    value = os.environ.get("OTTERWORKS_SCREENSHOT_DIR")
    if not value:
        return None
    path = Path(value)
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def record(request: pytest.FixtureRequest) -> Iterator[dict]:
    """Observations a test wants compared before/after; written per test when enabled."""
    observations: dict = {}
    yield observations
    value = os.environ.get("OTTERWORKS_RESULTS_DIR")
    if value and observations:
        out = Path(value)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{request.node.name}.json").write_text(
            json.dumps(observations, indent=2, sort_keys=True), encoding="utf-8"
        )
