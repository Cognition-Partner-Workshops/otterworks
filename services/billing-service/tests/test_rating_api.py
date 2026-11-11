from __future__ import annotations

import psycopg
from fastapi.testclient import TestClient

import app.main as main

TENANT = "00000000-0000-0000-0000-000000000001"


class FakeConnection:
    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def test_finalize_integrity_error_returns_bad_request(monkeypatch) -> None:
    def fake_finalize(*_args: object) -> list:
        raise psycopg.errors.ForeignKeyViolation("period id does not exist")

    monkeypatch.setattr(main, "migrate", lambda: None)
    monkeypatch.setattr(main, "connect", FakeConnection)
    monkeypatch.setattr(main, "finalize_rating", fake_finalize)
    with TestClient(main.app) as client:
        response = client.post(
            f"/api/tenants/{TENANT}/rating/finalize",
            json={"period_start": "2025-12-01", "period_end": "2025-12-31"},
        )
    assert response.status_code == 400
    assert response.json()["detail"] == "rating could not be finalized"
