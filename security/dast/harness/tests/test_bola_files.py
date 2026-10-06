"""DAST-BOLA-FILES verdicts, including the owner control that stops a deny-all route passing."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from probes.access_control import bola_files  # noqa: E402
from probes.base import Verdict  # noqa: E402

FILE_ID = "0b6f4a59-6c1e-4d0e-9a39-2f1c6f0f9a11"
BASE = f"/api/v1/files/{FILE_ID}"
ROUTES = [("GET", BASE), ("GET", f"{BASE}/download"), ("POST", f"{BASE}/share")]
OWNER_OK = {"GET": 200, "POST": 201}


@dataclass
class StubIdentity:
    user_id: str


class StubContext:
    def __init__(
        self,
        attacker: dict[str, int],
        owner: dict[str, int] | None = None,
        uploaded: bool = True,
    ):
        self.victim = StubIdentity("victim")
        self.attacker = StubIdentity("attacker")
        self.burner = StubIdentity("burner")
        self._statuses = {"attacker": attacker, "victim": owner or {}}
        self._uploaded = uploaded
        self.requests: list[tuple[str, str, str, object]] = []

    def victim_file(self):
        return {"id": FILE_ID, "owner_id": "victim"} if self._uploaded else None

    def request(self, method, path, *, identity=None, json=None, **_):
        self.requests.append((identity.user_id, method, path, json))
        default = 403 if identity.user_id == "attacker" else OWNER_OK[method]
        status = self._statuses[identity.user_id].get(f"{method} {path}", default)
        return httpx.Response(status, request=httpx.Request(method, f"http://t{path}"))

    def routes_tried_by(self, who: str) -> set[tuple[str, str]]:
        return {(m, p) for user, m, p, _ in self.requests if user == who}


def test_any_attacker_success_is_vulnerable() -> None:
    ctx = StubContext({f"POST {BASE}/share": 201})
    assert bola_files(ctx).verdict is Verdict.VULNERABLE


def test_attacker_refused_everywhere_and_owner_served_everywhere_is_secure() -> None:
    ctx = StubContext({})
    assert bola_files(ctx).verdict is Verdict.SECURE
    assert ctx.routes_tried_by("attacker") == set(ROUTES)
    assert ctx.routes_tried_by("victim") == set(ROUTES)


def test_owner_share_control_never_grants_the_attacker() -> None:
    ctx = StubContext({})
    bola_files(ctx)
    owner_shares = [body for who, m, _, body in ctx.requests if who == "victim" and m == "POST"]
    assert owner_shares and all(b["shared_with"] == "burner" for b in owner_shares)


@pytest.mark.parametrize("method,path", ROUTES)
def test_a_route_that_refuses_the_owner_too_never_passes(method: str, path: str) -> None:
    ctx = StubContext({}, owner={f"{method} {path}": 403})
    assert bola_files(ctx).verdict is Verdict.INCONCLUSIVE


def test_unexpected_status_is_inconclusive_after_trying_every_route() -> None:
    ctx = StubContext({f"GET {BASE}": 502})
    assert bola_files(ctx).verdict is Verdict.INCONCLUSIVE
    assert ctx.routes_tried_by("attacker") == set(ROUTES)


def test_unexpected_status_on_an_earlier_route_does_not_hide_a_later_breach() -> None:
    ctx = StubContext({f"GET {BASE}": 502, f"GET {BASE}/download": 500, f"POST {BASE}/share": 201})
    assert bola_files(ctx).verdict is Verdict.VULNERABLE


def test_a_breach_is_reported_before_a_later_request_can_fail() -> None:
    ctx = StubContext({f"GET {BASE}": 200})
    original = ctx.request

    def request(method, path, **kwargs):
        if path.endswith("/download"):
            raise httpx.ReadTimeout("timed out")
        return original(method, path, **kwargs)

    ctx.request = request
    assert bola_files(ctx).verdict is Verdict.VULNERABLE


def test_no_seeded_file_is_inconclusive() -> None:
    assert bola_files(StubContext({}, uploaded=False)).verdict is Verdict.INCONCLUSIVE
