"""Server-side Devin v3 client. The API key lives only in this object's memory."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlencode

from .config import Config
from .httpjson import HTTPFailure, request_json

_SESSION_ID_RE = re.compile(r"^devin-[A-Za-z0-9]{6,64}$")


class VerificationError(Exception):
    """The created session does not carry the configured persona or mode."""


@dataclass(frozen=True)
class CreatedSession:
    session_id: str
    url: str | None


@dataclass(frozen=True)
class SessionMessage:
    event_id: str
    source: str
    message: str
    created_at: int


def normalize_session_id(raw: object) -> str:
    if not isinstance(raw, str):
        raise VerificationError("session_id missing")
    sid = raw if raw.startswith("devin-") else f"devin-{raw}"
    if not _SESSION_ID_RE.match(sid):
        raise VerificationError("session_id has an unexpected format")
    return sid


class DevinClient:
    def __init__(self, config: Config) -> None:
        if not (config.devin_api_key and config.devin_org_id and config.create_as_user_id):
            raise ValueError("DevinClient needs live configuration")
        self._key = config.devin_api_key
        self._org = config.devin_org_id
        self._user = config.create_as_user_id
        self._mode = config.devin_mode
        self._base = f"{config.devin_api_base}/v3/organizations/{quote(self._org, safe='')}"
        self._timeout = config.http_timeout
        self._repos = list(config.repos)
        self._tags = list(config.session_tags)
        self._max_acu = config.max_acu_limit

    def __repr__(self) -> str:
        return "DevinClient(<redacted>)"

    def _call(self, method: str, path: str, label: str, body: dict[str, Any] | None = None) -> Any:
        return request_json(
            method,
            self._base + path,
            label=label,
            headers={"Authorization": f"Bearer {self._key}"},
            body=body,
            timeout=self._timeout,
        )

    def create_session(self, prompt: str, title: str) -> CreatedSession:
        body: dict[str, Any] = {
            "prompt": prompt,
            "title": title[:120],
            "create_as_user_id": self._user,
            "devin_mode": self._mode,
            "tags": self._tags,
        }
        if self._repos:
            body["repos"] = self._repos
        if self._max_acu:
            body["max_acu_limit"] = self._max_acu
        data = self._call("POST", "/sessions", "create_session", body)
        if not isinstance(data, dict):
            raise VerificationError("create_session returned no object")
        sid = normalize_session_id(data.get("session_id"))
        url = data.get("url")
        return CreatedSession(sid, url if isinstance(url, str) and url.startswith("https://") else None)

    def get_session(self, session_id: str) -> dict[str, Any]:
        data = self._call("GET", f"/sessions/{quote(session_id, safe='')}", "get_session")
        if not isinstance(data, dict):
            raise VerificationError("get_session returned no object")
        return data

    def verify_session(self, session_id: str) -> dict[str, Any]:
        data = self.get_session(session_id)
        if data.get("user_id") != self._user:
            raise VerificationError("session user_id does not match the configured persona")
        if data.get("devin_mode") != self._mode:
            raise VerificationError("session devin_mode is not fusion")
        org = data.get("org_id")
        if org is not None and org != self._org:
            raise VerificationError("session org_id does not match configuration")
        return data

    def archive_session(self, session_id: str) -> None:
        self._call("POST", f"/sessions/{quote(session_id, safe='')}/archive", "archive_session", {})

    def send_message(self, session_id: str, text: str) -> None:
        self._call("POST", f"/sessions/{quote(session_id, safe='')}/messages", "send_message", {"message": text})

    def list_messages(self, session_id: str, after: str | None) -> tuple[list[SessionMessage], str | None, bool]:
        query = {"first": "100"}
        if after:
            query["after"] = after
        data = self._call("GET", f"/sessions/{quote(session_id, safe='')}/messages?{urlencode(query)}", "list_messages")
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise HTTPFailure("list_messages", 200, reason="bad-shape")
        out: list[SessionMessage] = []
        for item in data["items"]:
            if not isinstance(item, dict):
                continue
            eid, src, msg = item.get("event_id"), item.get("source"), item.get("message")
            if isinstance(eid, str) and isinstance(src, str) and isinstance(msg, str):
                created = item.get("created_at")
                out.append(SessionMessage(eid, src, msg, created if isinstance(created, int) else 0))
        cursor = data.get("end_cursor")
        return out, cursor if isinstance(cursor, str) else None, bool(data.get("has_next_page"))
