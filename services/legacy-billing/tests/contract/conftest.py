from pathlib import Path

import pytest

from app import app, db_connect

ROOT = Path(__file__).resolve().parents[2]


def reset_seed():
    # Only the disposable Docker database selected by make billing-contract.
    with db_connect() as connection:
        connection.execute("DROP SCHEMA IF EXISTS billing CASCADE")
        for path in [ROOT / "db/schema.sql", *sorted((ROOT / "db/procs").glob("*.sql")), ROOT / "db/seed.sql"]:
            connection.execute(path.read_text())


@pytest.fixture
def reset_db():
    reset_seed()
    return reset_seed


@pytest.fixture
def client(reset_db):
    class SeededClient(type(app.test_client())):
        def open(self, *args, **kwargs):
            reset_db()
            return super().open(*args, **kwargs)

    return SeededClient(app)


@pytest.fixture
def compare_requests(client):
    """Explicit mappings only; state_probe returns deterministic database state."""
    def compare(legacy, v1, *, unwrap=False, renames=None, status_map=None,
                legacy_body=None, v1_body=None, state_probe=None):
        old = client.open(**legacy)
        old_state = state_probe() if state_probe else None
        new = client.open(**v1)
        new_state = state_probe() if state_probe else None
        assert old.status_code == (status_map or {}).get(new.status_code, new.status_code)
        old_payload = legacy_body(old) if legacy_body else old.get_json()
        new_payload = v1_body(new) if v1_body else new.get_json()
        if unwrap:
            new_payload = new_payload["data"]

        def rename(value):
            if isinstance(value, list):
                return [rename(item) for item in value]
            if isinstance(value, dict):
                return {(renames or {}).get(key, key): rename(item) for key, item in value.items()}
            return value

        assert old_payload == rename(new_payload)
        if state_probe:
            assert old_state == new_state
        return old, new
    return compare
