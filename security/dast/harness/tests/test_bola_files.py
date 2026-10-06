"""DAST-BOLA-FILES verdicts, including the owner control that stops a deny-all route passing."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from probes.access_control import bola_files  # noqa: E402
from probes.base import Verdict  # noqa: E402

FILE_ID = "0b6f4a59-6c1e-4d0e-9a39-2f1c6f0f9a11"


@dataclass
class StubIdentity:
    user_id: str


class StubContext:
    def __init__(self, attacker: dict[str, int], owner_status: int = 200, uploaded: bool = True):
        self.victim = StubIdentity("victim")
        self.attacker = StubIdentity("attacker")
        self._attacker = attacker
        self._owner_status = owner_status
        self._uploaded = uploaded
        self.requests: list[tuple[str, str, str]] = []

    def victim_file(self):
        return {"id": FILE_ID, "owner_id": "victim"} if self._uploaded else None

    def request(self, method, path, *, identity=None, json=None, **_):
        self.requests.append((identity.user_id, method, path))
        status = self._attacker.get(f"{method} {path}", 403)
        return httpx.Response(status, request=httpx.Request(method, f"http://t{path}"))

    def owner_can_read(self, path, identity):
        self.requests.append((identity.user_id, "GET", path))
        return self._owner_status == 200


BASE = f"/api/v1/files/{FILE_ID}"


def test_any_attacker_success_is_vulnerable() -> None:
    ctx = StubContext({f"POST {BASE}/share": 201})
    assert bola_files(ctx).verdict is Verdict.VULNERABLE


def test_attacker_refused_everywhere_and_owner_reads_is_secure() -> None:
    ctx = StubContext({})
    assert bola_files(ctx).verdict is Verdict.SECURE
    assert ("victim", "GET", BASE) in ctx.requests
    assert {(m, p) for who, m, p in ctx.requests if who == "attacker"} == {
        ("GET", BASE),
        ("GET", f"{BASE}/download"),
        ("POST", f"{BASE}/share"),
    }


def test_a_route_that_refuses_the_owner_too_never_passes() -> None:
    ctx = StubContext({}, owner_status=403)
    assert bola_files(ctx).verdict is Verdict.INCONCLUSIVE


def test_unexpected_status_is_inconclusive() -> None:
    ctx = StubContext({f"GET {BASE}/download": 502})
    assert bola_files(ctx).verdict is Verdict.INCONCLUSIVE


def test_no_seeded_file_is_inconclusive() -> None:
    assert bola_files(StubContext({}, uploaded=False)).verdict is Verdict.INCONCLUSIVE
