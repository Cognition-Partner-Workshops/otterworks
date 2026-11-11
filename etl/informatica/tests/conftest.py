import os
import shutil
import subprocess
import sys
import time
import uuid

import pytest

ESTATE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ESTATE)

from runner import db  # noqa: E402

FIXTURE = os.path.join(ESTATE, "tests", "fixture")


def _connect(dbname, port):
    import psycopg

    return psycopg.connect(host=db.env("TD_HOST"), port=port, dbname=dbname, user=db.env("TD_USER"),
                           password=db.env("TD_PASSWORD"), autocommit=True, connect_timeout=3)


def _server():
    """(port, cleanup) of a reachable PostgreSQL: TD_* env first, else a throwaway container."""
    port = db.env("TD_PORT")
    try:
        _connect(db.env("TD_DB"), port).close()
        return port, None
    except Exception:  # noqa: BLE001
        pass
    if os.environ.get("TD_PORT") or not shutil.which("docker"):
        return None, None
    name = f"sfx-d1110-informatica-pytest-{uuid.uuid4().hex[:6]}"
    subprocess.run(["docker", "run", "-d", "--rm", "--name", name, "--label", "sfx.run_token=sfx-d1110",
                    "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "-e", "POSTGRES_DB=teradata", "-p", "127.0.0.1::5432", "postgres:16"],
                   check=True, capture_output=True)
    port = subprocess.run(["docker", "port", name, "5432/tcp"], check=True, capture_output=True, text=True).stdout.split(":")[-1].strip()
    for _ in range(60):
        try:
            _connect("teradata", port).close()
            break
        except Exception:  # noqa: BLE001
            time.sleep(1)
    return port, lambda: subprocess.run(["docker", "rm", "-f", name], capture_output=True)


@pytest.fixture(scope="session")
def pg_server():
    port, cleanup = _server()
    if port is None:
        pytest.skip("no PostgreSQL reachable through TD_* and docker is unavailable")
    yield port
    if cleanup:
        cleanup()


@pytest.fixture()
def warehouse(pg_server, tmp_path, monkeypatch):
    """A fresh database loaded with the fixture schema; TD_* env points at it."""
    name = f"sfx_d1110_t_{uuid.uuid4().hex[:8]}"
    with _connect(db.env("TD_DB") if not os.environ.get("TD_DB") else os.environ["TD_DB"], pg_server) as c:
        c.execute(f"CREATE DATABASE {name}")
    with _connect(name, pg_server) as c:
        with open(os.path.join(FIXTURE, "bootstrap.sql"), encoding="utf-8") as fh:
            c.execute(fh.read())
    monkeypatch.setenv("TD_PORT", str(pg_server))
    monkeypatch.setenv("TD_DB", name)
    monkeypatch.setenv("LANDING_DIR", os.path.join(FIXTURE, "landing"))
    monkeypatch.setenv("PMROOTDIR", str(tmp_path / "infa_shared"))
    conn = _connect(name, pg_server)
    yield conn
    conn.close()
    with _connect("postgres", pg_server) as c:
        c.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
