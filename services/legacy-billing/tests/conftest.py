import subprocess
from pathlib import Path
from time import monotonic, sleep

import psycopg
import pytest

from app.app import app

SQL_DIR = Path(__file__).resolve().parents[1] / "db"
SQL_FILES = [
    "schema.sql",
    "procs/plans.sql",
    "procs/rating.sql",
    "procs/invoicing.sql",
    "procs/dunning.sql",
    "seed.sql",
]


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True).strip()


@pytest.fixture(scope="session")
def postgres():
    settings = {
        "host": "127.0.0.1",
        "dbname": "legacy_billing_test",
        "user": "billing",
        "password": "billing-test",
    }
    container = docker(
        "run", "--rm", "--detach", "--publish", "127.0.0.1::5432",
        "--env", f"POSTGRES_DB={settings['dbname']}",
        "--env", f"POSTGRES_USER={settings['user']}",
        "--env", f"POSTGRES_PASSWORD={settings['password']}",
        "postgres:16",
    )
    try:
        settings["port"] = docker("port", container, "5432/tcp").rsplit(":", 1)[1]
        deadline = monotonic() + 30
        while True:
            try:
                with psycopg.connect(**settings, connect_timeout=1):
                    break
            except psycopg.OperationalError:
                if monotonic() >= deadline:
                    raise
                sleep(0.2)
        yield settings
    finally:
        docker("rm", "--force", "--volumes", container)


@pytest.fixture
def db(postgres, monkeypatch):
    for variable, name in {
        "DB_HOST": "host",
        "DB_PORT": "port",
        "DB_NAME": "dbname",
        "DB_USER": "user",
        "DB_PASSWORD": "password",
    }.items():
        monkeypatch.setenv(variable, postgres[name])

    with psycopg.connect(**postgres, autocommit=True) as connection:
        with connection.transaction():
            connection.execute("DROP SCHEMA IF EXISTS billing CASCADE")
            for filename in SQL_FILES:
                connection.execute((SQL_DIR / filename).read_text(encoding="utf-8"))
        yield connection


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setitem(app.config, "TESTING", True)
    monkeypatch.setitem(app.config, "PROPAGATE_EXCEPTIONS", False)
    return app.test_client()
