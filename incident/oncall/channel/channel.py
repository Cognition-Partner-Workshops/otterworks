#!/usr/bin/env python3
"""Incident channel for the on-call storm demo.

A chat-style page (#inc-otterworks) that stands in for Slack. Alertmanager posts
the oncall group to /alertmanager and the page shows one thread per groupKey with
an alert card that updates in place. The paged Devin session posts into the thread
with a bearer token, and the people on the page reply as a persona; each reply is
forwarded to the bound session through the Devin v3 API.

Python 3.12 standard library only, so it runs from a ConfigMap on python:3.12-slim.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_BODY_BYTES = 1024 * 1024
MAX_TEXT_CHARS = 20_000
MAX_ATTACHMENTS = 12
PERSONA_IDS = ("sre", "incident-manager")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")


# --------------------------------------------------------------------------- config


@dataclass(frozen=True)
class Persona:
    key: str
    name: str
    user_id: str


@dataclass(frozen=True)
class Config:
    channel_token: str = ""
    devin_api_key: str = field(default="", repr=False)
    devin_api_base: str = "https://partner-workshops.devinenterprise.com/api"
    devin_app_url: str = "https://partner-workshops.devinenterprise.com"
    devin_org_id: str = ""
    grafana_url: str = "https://grafana.otterworks.app"
    grafana_dashboard_uid: str = "oncall-storm"
    alertmanager_url: str = "https://alertmanager.otterworks.app"
    state_file: str = "/data/state.json"
    basic_auth_user: str = "oncall"
    basic_auth_password: str = field(default="", repr=False)
    channel_name: str = "inc-otterworks"
    api_timeout_seconds: float = 10.0
    personas: tuple[Persona, ...] = ()

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Config:
        e = dict(os.environ if env is None else env)

        def get(name: str, default: str) -> str:
            value = e.get(name, "").strip()
            return value or default

        personas = (
            Persona(
                "sre", get("PERSONA_SRE_NAME", "SRE (on call)"), get("PERSONA_SRE_USER_ID", "")
            ),
            Persona(
                "incident-manager",
                get("PERSONA_IM_NAME", "Incident manager"),
                get("PERSONA_IM_USER_ID", ""),
            ),
        )
        return cls(
            channel_token=e.get("CHANNEL_TOKEN", "").strip(),
            devin_api_key=e.get("DEVIN_API_KEY", "").strip(),
            devin_api_base=get("DEVIN_API_BASE", cls.devin_api_base).rstrip("/"),
            devin_app_url=get("DEVIN_APP_URL", cls.devin_app_url).rstrip("/"),
            devin_org_id=get("DEVIN_ORG_ID", ""),
            grafana_url=get("GRAFANA_URL", cls.grafana_url).rstrip("/"),
            grafana_dashboard_uid=get("GRAFANA_DASHBOARD_UID", cls.grafana_dashboard_uid),
            alertmanager_url=get("ALERTMANAGER_URL", cls.alertmanager_url).rstrip("/"),
            state_file=get("STATE_FILE", cls.state_file),
            basic_auth_user=get("BASIC_AUTH_USER", cls.basic_auth_user),
            basic_auth_password=e.get("BASIC_AUTH_PASSWORD", "").strip(),
            channel_name=get("CHANNEL_NAME", cls.channel_name).lstrip("#"),
            api_timeout_seconds=float(get("DEVIN_API_TIMEOUT_SECONDS", "10")),
            personas=personas,
        )

    def persona(self, key: str) -> Persona | None:
        for p in self.personas:
            if p.key == key:
                return p
        return None


def log(event: str, **fields: object) -> None:
    record = {"ts": now_iso(), "event": event, **fields}
    print(json.dumps(record, sort_keys=True), file=sys.stderr, flush=True)


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def parse_ts(value: str | None) -> datetime | None:
    if not value or value.startswith("0001-"):
        return None
    try:
        text = value.strip().replace("Z", "+00:00")
        # Alertmanager emits nanoseconds; fromisoformat takes at most six digits.
        text = re.sub(r"(\.\d{6})\d+", r"\1", text)
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def hhmmss(value: str | None) -> str:
    parsed = parse_ts(value)
    return parsed.strftime("%H:%M:%S") if parsed else ""


def thread_id_for(group_key: str) -> str:
    return hashlib.sha256(group_key.encode("utf-8")).hexdigest()[:12]


def scrub(text: str, secrets: tuple[str, ...]) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[redacted]")
    return text


def is_http_url(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 2048:
        return False
    parsed = urllib.parse.urlsplit(value)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


# ---------------------------------------------------------------------------- state


class Channel:
    """Threads in memory, mirrored to a JSON snapshot after every change."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.lock = threading.RLock()
        self.threads: dict[str, dict] = {}
        self.version = 0
        self.message_seq = 0
        self.load()

    # snapshot ---------------------------------------------------------------

    def load(self) -> None:
        path = self.config.state_file
        if not path or not os.path.exists(path):
            return
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            threads = data.get("threads", [])
            self.threads = {t["id"]: t for t in threads}
            self.version = int(data.get("version", 0)) + 1
            self.message_seq = int(data.get("message_seq", 0))
            log("snapshot_loaded", threads=len(self.threads), path=path)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            log("snapshot_unreadable", path=path, error=type(exc).__name__)
            self.threads = {}

    def save(self) -> None:
        path = self.config.state_file
        if not path:
            return
        data = {
            "version": self.version,
            "message_seq": self.message_seq,
            "saved_at": now_iso(),
            "threads": list(self.threads.values()),
        }
        directory = os.path.dirname(path) or "."
        tmp = os.path.join(directory, f".{os.path.basename(path)}.{os.getpid()}.tmp")
        try:
            os.makedirs(directory, exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, separators=(",", ":"))
            os.replace(tmp, path)
        except OSError as exc:
            log("snapshot_write_failed", path=path, error=type(exc).__name__)

    def changed(self) -> None:
        self.version += 1
        self.save()

    # lookups ----------------------------------------------------------------

    def find(self, key: str) -> dict | None:
        with self.lock:
            if key == "latest":
                return next(reversed(self.threads.values()), None)
            if key in self.threads:
                return self.threads[key]
            return self.threads.get(thread_id_for(key))

    def next_message_id(self) -> str:
        self.message_seq += 1
        return f"m{self.message_seq}"

    # mutations --------------------------------------------------------------

    def ingest_alertmanager(self, payload: dict) -> dict:
        group_key = payload.get("groupKey")
        alerts = payload.get("alerts")
        if not isinstance(group_key, str) or not group_key or not isinstance(alerts, list):
            raise ValueError("payload needs groupKey and alerts")
        tid = thread_id_for(group_key)
        stamp = now_iso()
        with self.lock:
            thread = self.threads.get(tid)
            created = thread is None
            if thread is None:
                thread = {
                    "id": tid,
                    "group_key": group_key,
                    "created_at": stamp,
                    "notifications": 0,
                    "alerts": {},
                    "session": None,
                    "messages": [],
                }
                self.threads[tid] = thread
            thread["updated_at"] = stamp
            thread["notifications"] += 1
            thread["receiver"] = str(payload.get("receiver", ""))
            thread["group_labels"] = string_map(payload.get("groupLabels"))
            thread["common_labels"] = string_map(payload.get("commonLabels"))
            thread["external_url"] = str(payload.get("externalURL", ""))
            for alert in alerts:
                if not isinstance(alert, dict):
                    continue
                labels = string_map(alert.get("labels"))
                annotations = string_map(alert.get("annotations"))
                fingerprint = (
                    str(alert.get("fingerprint") or "")
                    or hashlib.sha256(json.dumps(labels, sort_keys=True).encode()).hexdigest()[:16]
                )
                thread["alerts"][fingerprint] = {
                    "name": labels.get("alertname", "unnamed alert"),
                    "service": labels.get("service", "unknown"),
                    "severity": labels.get("severity", "info"),
                    "namespace": labels.get("namespace", ""),
                    "status": "resolved" if alert.get("status") == "resolved" else "firing",
                    "starts_at": str(alert.get("startsAt", "")),
                    "ends_at": str(alert.get("endsAt", "")),
                    "summary": annotations.get("summary", ""),
                    "runbook_url": annotations.get("runbook_url", ""),
                    "dashboard_url": annotations.get("dashboard_url", ""),
                    "generator_url": str(alert.get("generatorURL", "")),
                }
            firing = any(a["status"] == "firing" for a in thread["alerts"].values())
            thread["status"] = "firing" if firing else "resolved"
            self.changed()
            return {"thread_id": tid, "created": created, "alerts": len(thread["alerts"])}

    def post_devin_message(self, key: str, body: dict) -> dict:
        text = body.get("text", "")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text is required")
        attachments = body.get("attachments") or []
        if not isinstance(attachments, list):
            raise ValueError("attachments must be a list of URLs")
        urls = [a for a in attachments if is_http_url(a)][:MAX_ATTACHMENTS]
        with self.lock:
            thread = self.find(key)
            if thread is None:
                raise LookupError(key)
            session = dict(thread.get("session") or {})
            session_id = body.get("session_id")
            if isinstance(session_id, str) and session_id.strip():
                session["session_id"] = normalize_session_id(session_id)
            org_id = body.get("org_id")
            if isinstance(org_id, str) and org_id.strip():
                session["org_id"] = org_id.strip()
            session_url = body.get("session_url")
            if is_http_url(session_url):
                session["session_url"] = session_url
            if session:
                thread["session"] = session
            author = body.get("author")
            message = {
                "id": self.next_message_id(),
                "kind": "devin",
                "author": author.strip()[:80]
                if isinstance(author, str) and author.strip()
                else "Devin",
                "text": text[:MAX_TEXT_CHARS],
                "attachments": urls,
                "at": now_iso(),
            }
            thread["messages"].append(message)
            thread["updated_at"] = message["at"]
            self.changed()
            return {"thread_id": thread["id"], "message_id": message["id"]}

    def add_reply(self, key: str, persona: Persona, text: str) -> tuple[dict, dict]:
        with self.lock:
            thread = self.find(key)
            if thread is None:
                raise LookupError(key)
            message = {
                "id": self.next_message_id(),
                "kind": "human",
                "persona": persona.key,
                "author": persona.name,
                "text": text[:MAX_TEXT_CHARS],
                "attachments": [],
                "at": now_iso(),
                "delivery": {"state": "sending"},
            }
            thread["messages"].append(message)
            thread["updated_at"] = message["at"]
            self.changed()
            return thread, message

    def set_delivery(self, thread_id: str, message_id: str, delivery: dict) -> None:
        with self.lock:
            thread = self.threads.get(thread_id)
            if thread is None:
                return
            for message in thread["messages"]:
                if message["id"] == message_id:
                    message["delivery"] = delivery
                    self.changed()
                    return

    def reset(self) -> int:
        with self.lock:
            count = len(self.threads)
            self.threads = {}
            self.changed()
            return count


def string_map(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(k): str(v) for k, v in value.items()}


def normalize_session_id(value: str) -> str:
    value = value.strip()
    return value if value.startswith("devin-") else f"devin-{value}"


# ------------------------------------------------------------------- Devin forward


def forward_to_devin(config: Config, session: dict, persona: Persona, text: str) -> dict:
    """Forward a reply to the bound session and return the delivery record behind the tick."""
    session_id = session.get("session_id", "")
    org_id = session.get("org_id") or config.devin_org_id
    if not session_id:
        return {
            "state": "not_sent",
            "detail": "waiting for Devin to join the thread, reply kept here",
        }
    if not org_id:
        return {"state": "not_sent", "detail": "thread is bound without an org id, reply kept here"}
    if not config.devin_api_key:
        return {
            "state": "not_sent",
            "detail": "DEVIN_API_KEY is unset on the channel, reply kept here",
        }
    url = (
        f"{config.devin_api_base}/v3/organizations/{urllib.parse.quote(org_id, safe='')}"
        f"/sessions/{urllib.parse.quote(session_id, safe='')}/messages"
    )
    if not persona.user_id:
        env_name = "PERSONA_SRE_USER_ID" if persona.key == "sre" else "PERSONA_IM_USER_ID"
        return {
            "state": "not_sent",
            "detail": f"{env_name} is unset on the channel, reply kept here",
        }
    body = {"message": text, "message_as_user_id": persona.user_id}
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {config.devin_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "otterworks-incident-channel/1",
        },
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=config.api_timeout_seconds) as resp:
            status = resp.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        log("devin_forward_failed", session_id=session_id, error=type(exc).__name__)
        return {"state": "failed", "detail": "Devin API unreachable", "at": now_iso()}
    elapsed_ms = int((time.monotonic() - started) * 1000)
    ok = 200 <= status < 300
    log("devin_forward", session_id=session_id, persona=persona.key, status=status, ms=elapsed_ms)
    return {"state": "delivered" if ok else "failed", "status": status, "at": now_iso()}


# ---------------------------------------------------------------------- rendering

_URL_RE = re.compile(r"https?://(?:(?!&quot;|&#x27;|&lt;|&gt;)[^\s<>\"'\x60])+")
_TRAILING_PUNCT = ".,;:!?)"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _link(url_escaped: str, label_escaped: str | None = None) -> str:
    label = label_escaped if label_escaped is not None else url_escaped
    return f'<a href="{url_escaped}" target="_blank" rel="noopener noreferrer">{label}</a>'


def _image(url_escaped: str, alt_escaped: str) -> str:
    return (
        f'<a class="img" href="{url_escaped}" target="_blank" rel="noopener noreferrer">'
        f'<img src="{url_escaped}" alt="{alt_escaped}" loading="lazy"></a>'
    )


def render_inline(text_escaped: str, stash: list[str]) -> str:
    """Apply inline markup to escaped text, parking finished HTML in `stash` for later passes."""

    def keep(fragment: str) -> str:
        stash.append(fragment)
        return f"\x00{len(stash) - 1}\x00"

    def autolink(match: re.Match[str]) -> str:
        url = match.group(0)
        tail = ""
        while url and url[-1] in _TRAILING_PUNCT:
            tail = url[-1] + tail
            url = url[:-1]
        return keep(_link(url)) + tail

    text = re.sub(
        r"\x60([^\x60\n]+)\x60", lambda m: keep(f"<code>{m.group(1)}</code>"), text_escaped
    )
    text = re.sub(
        r"!\[([^\]\n]*)\]\((https?://[^\s)]+)\)",
        lambda m: keep(_image(m.group(2), m.group(1))),
        text,
    )
    text = re.sub(
        r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)", lambda m: keep(_link(m.group(2), m.group(1))), text
    )
    text = _URL_RE.sub(autolink, text)
    text = re.sub(r"\*\*([^*\n]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])_([^_\n]+)_(?![\w*])", r"<em>\1</em>", text)
    return text


def render_markdown_lite(source: str) -> str:
    """Escape first, then apply a small markdown subset (code, bold, links, images, lists)."""
    stash: list[str] = []
    escaped = esc(source.replace("\r\n", "\n").replace("\x00", ""))

    def fence(match: re.Match[str]) -> str:
        stash.append(f"<pre><code>{match.group(1).strip(chr(10))}</code></pre>")
        return f"\n\x00{len(stash) - 1}\x00\n"

    escaped = re.sub(r"\x60\x60\x60[a-zA-Z0-9_-]*\n?(.*?)\x60\x60\x60", fence, escaped, flags=re.S)

    blocks: list[str] = []
    paragraph: list[str] = []
    items: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append("<p>" + "<br>".join(paragraph) + "</p>")
            paragraph.clear()

    def flush_items() -> None:
        if items:
            blocks.append("<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>")
            items.clear()

    for raw in escaped.split("\n"):
        line = raw.rstrip()
        if re.fullmatch(r"\x00\d+\x00", line):
            flush_paragraph()
            flush_items()
            blocks.append(line)
            continue
        bullet = re.match(r"^\s*[-*] +(.*)$", line)
        if bullet:
            flush_paragraph()
            items.append(render_inline(bullet.group(1), stash))
        elif not line.strip():
            flush_paragraph()
            flush_items()
        else:
            flush_items()
            paragraph.append(render_inline(line, stash))
    flush_paragraph()
    flush_items()
    rendered = "".join(blocks)
    for _ in range(3):
        rendered = re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], rendered)
    return rendered


def grafana_link(config: Config, namespace: str) -> str:
    query = urllib.parse.urlencode({"var-namespace": namespace} if namespace else {})
    url = f"{config.grafana_url}/d/{config.grafana_dashboard_uid}"
    return f"{url}?{query}" if query else url


def alertmanager_link(config: Config, group_labels: dict[str, str]) -> str:
    matchers = ",".join(f'{k}="{v}"' for k, v in sorted(group_labels.items()))
    return f"{config.alertmanager_url}/#/alerts?filter={urllib.parse.quote('{' + matchers + '}')}"


def session_link(config: Config, session: dict | None) -> str:
    if not session:
        return ""
    if session.get("session_url"):
        return session["session_url"]
    sid = session.get("session_id", "")
    if not sid:
        return ""
    return f"{config.devin_app_url}/sessions/{sid.removeprefix('devin-')}"


SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}


def thread_title(thread: dict) -> str:
    labels = thread.get("group_labels") or {}
    common = thread.get("common_labels") or {}
    group = labels.get("oncall_group") or common.get("oncall_group") or common.get("alertname")
    namespace = labels.get("namespace") or common.get("namespace") or ""
    firing = sum(1 for a in thread["alerts"].values() if a["status"] == "firing")
    head = f"[FIRING:{firing}]" if thread["status"] == "firing" else "[RESOLVED]"
    parts = [p for p in (group or "alert group", namespace) if p]
    return f"{head} {', '.join(parts)}"


def render_card(config: Config, thread: dict) -> str:
    alerts = list(thread["alerts"].values())
    firing = [a for a in alerts if a["status"] == "firing"]
    resolved = [a for a in alerts if a["status"] == "resolved"]
    services: dict[str, dict[str, int]] = {}
    for a in alerts:
        s = services.setdefault(a["service"], {"firing": 0, "critical": 0, "total": 0})
        s["total"] += 1
        if a["status"] == "firing":
            s["firing"] += 1
            if a["severity"] == "critical":
                s["critical"] += 1
    chips = []
    for name, s in sorted(services.items(), key=lambda kv: (-kv[1]["firing"], kv[0])):
        if s["critical"]:
            cls = "chip crit"
        elif s["firing"]:
            cls = "chip warn"
        else:
            cls = "chip ok"
        count = s["firing"] if s["firing"] else s["total"]
        chips.append(
            f'<span class="{cls}" data-service="{esc(name)}">{esc(name)} <b>{count}</b></span>'
        )
    starts = [parse_ts(a["starts_at"]) for a in alerts]
    first = min((s for s in starts if s), default=None)
    rows = []
    ordered = sorted(
        alerts,
        key=lambda a: (
            a["status"] == "resolved",
            SEVERITY_RANK.get(a["severity"], 3),
            a["service"],
            a["name"],
        ),
    )
    for a in ordered:
        state = a["status"]
        when = (
            f"resolved {esc(hhmmss(a['ends_at']))}"
            if state == "resolved" and hhmmss(a["ends_at"])
            else f"since {esc(hhmmss(a['starts_at']))}"
        )
        runbook = (
            f' <a class="mini" href="{esc(a["runbook_url"])}" target="_blank" '
            f'rel="noopener noreferrer">runbook</a>'
            if is_http_url(a["runbook_url"])
            else ""
        )
        rows.append(
            f'<li class="alert {esc(state)}" data-alert="{esc(a["name"])}">'
            f'<span class="sev {esc(a["severity"])}">{esc(a["severity"])}</span>'
            f'<span class="aname">{esc(a["name"])}</span>'
            f'<span class="svc">{esc(a["service"])}</span>'
            f'<span class="when">{when}</span>{runbook}'
            + (f'<span class="sum">{esc(a["summary"])}</span>' if a["summary"] else "")
            + "</li>"
        )
    status = thread["status"]
    if status == "firing":
        hot = sum(1 for s in services.values() if s["firing"])
        line = f"{len(firing)} firing across {hot} {'service' if hot == 1 else 'services'}"
        if resolved:
            line += f", {len(resolved)} resolved"
    else:
        line = f"All {len(alerts)} alerts resolved"
    if first:
        line += f". First alert at {first.strftime('%H:%M:%S')} UTC"
    namespace = (thread.get("group_labels") or {}).get("namespace") or (
        thread.get("common_labels") or {}
    ).get("namespace", "")
    links = [
        _link(esc(grafana_link(config, namespace)), "Grafana dashboard"),
        _link(esc(alertmanager_link(config, thread.get("group_labels") or {})), "Alertmanager"),
    ]
    devin = session_link(config, thread.get("session"))
    if devin:
        links.append(_link(esc(devin), "Devin session"))
    common = thread.get("common_labels") or {}
    meta = []
    for key in ("branch", "fix_branch"):
        if common.get(key):
            meta.append(f'<span class="tag">{esc(key)}: {esc(common[key])}</span>')
    return (
        f'<div class="card {esc(status)}" data-status="{esc(status)}" data-count="{len(alerts)}"'
        f' data-firing="{len(firing)}">'
        f'<div class="card-title">{esc(thread_title(thread))}</div>'
        f'<div class="card-line">{esc(line)}. '
        f"Updated {esc(hhmmss(thread.get('updated_at')))} UTC, "
        f"notification {thread['notifications']}.</div>"
        f'<div class="chips">{"".join(chips)}</div>'
        f'<ul class="alerts">{"".join(rows)}</ul>'
        f'<div class="links">{" ".join(links)}{"".join(meta)}</div>'
        "</div>"
    )


def render_delivery(message: dict) -> str:
    delivery = message.get("delivery") or {}
    state = delivery.get("state", "")
    if state == "delivered":
        text = "Delivered to Devin"
    elif state == "sending":
        text = "Sending to Devin"
    elif state == "failed":
        status = delivery.get("status")
        text = (
            f"Not delivered (HTTP {status})" if status else "Not delivered (Devin API unreachable)"
        )
    elif state == "not_sent":
        detail = str(delivery.get("detail", "reply kept here"))
        text = detail[:1].upper() + detail[1:]
    else:
        return ""
    return f'<div class="tick {esc(state)}"><i></i>{esc(text)}</div>'


def avatar(message: dict) -> str:
    if message["kind"] == "devin":
        return '<div class="avatar devin">D</div>'
    initials = "IM" if message.get("persona") == "incident-manager" else "SRE"
    return f'<div class="avatar {esc(message.get("persona", ""))}">{initials}</div>'


def looks_like_image(url: str) -> bool:
    name = urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1].lower()
    return name.endswith(IMAGE_SUFFIXES) or "." not in name


def render_message(message: dict) -> str:
    images = "".join(
        _image(esc(url), "attachment")
        if looks_like_image(url)
        else f'<div class="file">{_link(esc(url))}</div>'
        for url in message.get("attachments", [])
    )
    app = '<span class="app">APP</span>' if message["kind"] == "devin" else ""
    return (
        f'<div class="msg {esc(message["kind"])}" id="{esc(message["id"])}">'
        f"{avatar(message)}"
        f'<div class="body"><div class="who"><b>{esc(message["author"])}</b>{app}'
        f'<span class="time">{esc(hhmmss(message["at"]))}</span></div>'
        f'<div class="text">{render_markdown_lite(message["text"])}</div>'
        + (f'<div class="images">{images}</div>' if images else "")
        + render_delivery(message)
        + "</div></div>"
    )


def render_thread(config: Config, thread: dict) -> str:
    replies = "".join(render_message(m) for m in thread["messages"])
    count = len(thread["messages"])
    reply_label = f"{count} {'reply' if count == 1 else 'replies'}" if count else "No replies yet"
    return (
        f'<section class="thread" id="t-{esc(thread["id"])}" data-thread="{esc(thread["id"])}">'
        '<div class="msg root"><div class="avatar am">AM</div><div class="body">'
        '<div class="who"><b>Alertmanager</b><span class="app">APP</span>'
        f'<span class="time">{esc(hhmmss(thread.get("created_at")))}</span></div>'
        f"{render_card(config, thread)}</div></div>"
        f'<div class="replies"><div class="rcount">{esc(reply_label)}</div>{replies}</div>'
        "</section>"
    )


EMPTY_STATE = (
    '<div class="empty">When Alertmanager pages the oncall group, the alert card shows up '
    "here and Devin replies in its thread.</div>"
)


def render_threads(config: Config, threads: list[dict]) -> str:
    if not threads:
        return EMPTY_STATE
    return "".join(render_thread(config, t) for t in threads)


def thread_options(threads: list[dict]) -> list[dict]:
    return [{"id": t["id"], "title": thread_title(t)} for t in threads]


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>#__CHANNEL__ | OtterWorks incidents</title>
<style>
:root{--bg:#fff;--side:#3f0e40;--line:#e6e6e6;--muted:#616061;--text:#1d1c1d;
--crit:#c8102e;--warn:#b26b00;--ok:#1f8a4c;--link:#1264a3}
*{box-sizing:border-box}
body{margin:0;font:15px/1.46 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
color:var(--text);background:var(--bg);display:flex;height:100vh}
nav{width:220px;background:var(--side);color:#cfc3cf;padding:14px 0;flex:none}
nav .ws{color:#fff;font-weight:700;font-size:17px;padding:0 16px 14px;
border-bottom:1px solid #5a2a5b}
nav .sec{padding:14px 16px 4px;font-size:13px}
nav .ch{padding:3px 16px;font-size:15px}
nav .ch.on{background:#1164a3;color:#fff;font-weight:600}
main{flex:1;display:flex;flex-direction:column;min-width:0}
header{padding:10px 20px;border-bottom:1px solid var(--line)}
header h1{margin:0;font-size:18px}
header .topic{color:var(--muted);font-size:13px}
#feed{flex:1;overflow-y:auto;padding:8px 20px 20px}
.empty{color:var(--muted);padding:40px 0;text-align:center}
.thread{border-bottom:1px solid var(--line);padding:10px 0}
.msg{display:flex;gap:10px;padding:6px 0}
.avatar{width:36px;height:36px;border-radius:6px;flex:none;display:flex;align-items:center;
justify-content:center;color:#fff;font-weight:700;font-size:12px}
.avatar.am{background:#e6522c}.avatar.devin{background:#2b3a55}
.avatar.sre{background:#2eb67d}.avatar.incident-manager{background:#ecb22e;color:#1d1c1d}
.body{min-width:0;flex:1}
.who b{font-weight:800}.who .time{color:var(--muted);font-size:12px;margin-left:8px}
.app{background:#eee;color:var(--muted);font-size:10px;font-weight:700;padding:1px 4px;
border-radius:3px;margin-left:6px;vertical-align:1px}
.card{border-left:4px solid var(--crit);background:#fafafa;padding:8px 12px;margin-top:4px;
border-radius:0 6px 6px 0}
.card.resolved{border-left-color:var(--ok)}
.card-title{font-weight:700}
.card-line{color:var(--muted);font-size:13px;margin:2px 0 6px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:6px}
.chip{border-radius:12px;padding:1px 10px;font-size:13px;border:1px solid}
.chip.crit{color:var(--crit);border-color:var(--crit);background:#fdecef}
.chip.warn{color:var(--warn);border-color:var(--warn);background:#fff6e5}
.chip.ok{color:var(--ok);border-color:var(--ok);background:#e9f7ef}
.alerts{list-style:none;margin:0;padding:0;font-size:13px}
.alert{padding:3px 0;border-top:1px dashed #e3e3e3}
.alert span{margin-right:8px}
.alert .aname{font-weight:600;font-family:ui-monospace,Menlo,Consolas,monospace}
.alert .svc,.alert .when{color:var(--muted)}
.alert .sum{color:#454245;margin-left:8px}
.alert.resolved .aname,.alert.resolved .sev{color:var(--ok)}
.alert.resolved .sev{border-color:var(--ok)}
.sev{display:inline-block;width:64px;text-align:center;font-size:11px;font-weight:700;
text-transform:uppercase;border:1px solid;border-radius:3px}
.sev.critical{color:var(--crit)}.sev.warning{color:var(--warn)}
.links{margin-top:8px;font-size:13px}
.links a{margin-right:14px}
.tag{color:var(--muted);margin-right:10px;font-family:ui-monospace,Menlo,Consolas,monospace}
a{color:var(--link);text-decoration:none}a:hover{text-decoration:underline}
a.mini{font-size:12px}
.replies{margin-left:46px;border-left:2px solid var(--line);padding-left:12px}
.rcount{color:var(--link);font-size:13px;font-weight:600;padding:2px 0}
.text p{margin:2px 0 6px}.text ul{margin:2px 0 6px;padding-left:22px}
.text code{background:#f3f3f3;border:1px solid #e1e1e1;border-radius:3px;padding:0 3px;
font-size:13px;color:#c01343}
.text pre{background:#f6f6f6;border:1px solid #e1e1e1;border-radius:4px;padding:8px;
overflow-x:auto;font-size:13px}
.text pre code{background:none;border:0;color:var(--text);padding:0}
.images{display:flex;flex-wrap:wrap;gap:8px;margin:4px 0}
.images img,.text img{max-width:420px;max-height:260px;border:1px solid var(--line);
border-radius:6px;display:block}
.tick{font-size:12px;color:var(--muted);margin-top:2px;display:flex;align-items:center;gap:5px}
.tick i{display:inline-block;width:6px;height:10px;border:solid currentColor;
border-width:0 2px 2px 0;transform:rotate(45deg);margin:0 3px 3px 2px}
.tick.delivered{color:var(--ok)}
.tick.failed,.tick.not_sent{color:var(--crit)}
.tick.failed i,.tick.not_sent i{width:10px;height:2px;border-width:0 0 2px 0;transform:none;
margin:0 2px}
.tick.sending i{border-width:0 0 2px 0;width:10px;height:2px;transform:none}
footer{border-top:1px solid var(--line);padding:10px 20px}
form{border:1px solid #bbb;border-radius:8px;padding:8px}
form .row{display:flex;gap:8px;align-items:center;margin-bottom:6px;font-size:13px;
color:var(--muted)}
select{font:inherit;font-size:13px;padding:2px 4px}
textarea{width:100%;border:0;resize:vertical;font:inherit;min-height:44px;outline:none}
button{background:#007a5a;color:#fff;border:0;border-radius:4px;padding:5px 14px;
font-weight:700;cursor:pointer}
button:disabled{background:#999;cursor:default}
#hint{font-size:12px;color:var(--muted)}
</style></head>
<body>
<nav><div class="ws">OtterWorks</div><div class="sec">Channels</div>
<div class="ch"># otterworks-alerts</div><div class="ch on"># __CHANNEL__</div>
<div class="ch"># platform-oncall</div></nav>
<main>
<header><h1>#__CHANNEL__</h1>
<div class="topic">Pages for the OtterWorks oncall group land here.
Devin picks up each page and works it in the thread.</div></header>
<div id="feed">__THREADS__</div>
<footer><form id="reply" autocomplete="off">
<div class="row"><label>Reply as <select id="persona">__PERSONAS__</select></label>
<label>in <select id="thread">__THREAD_OPTIONS__</select></label>
<span id="hint"></span></div>
<textarea id="text" placeholder="Reply in thread" maxlength="20000"></textarea>
<div class="row" style="justify-content:flex-end;margin:0"><button id="send">Send</button></div>
</form></footer>
</main>
<script>
(function(){
  var version = __VERSION__;
  var feed = document.getElementById('feed');
  var sel = document.getElementById('thread');
  var form = document.getElementById('reply');
  var text = document.getElementById('text');
  var send = document.getElementById('send');
  var hint = document.getElementById('hint');
  function nearBottom(){ return feed.scrollHeight - feed.scrollTop - feed.clientHeight < 120; }
  function setOptions(opts){
    var cur = sel.value;
    while (sel.firstChild) sel.removeChild(sel.firstChild);
    opts.forEach(function(o){
      var el = document.createElement('option'); el.value = o.id; el.textContent = o.title;
      sel.appendChild(el);
    });
    if (opts.some(function(o){ return o.id === cur; })) sel.value = cur;
    else if (opts.length) sel.value = opts[opts.length - 1].id;
    send.disabled = !opts.length;
  }
  function poll(){
    fetch('api/state?since=' + version, {cache: 'no-store'}).then(function(r){
      if (!r.ok) throw new Error(r.status); return r.json();
    }).then(function(s){
      if (s.version !== version) {
        var stick = nearBottom();
        version = s.version; feed.innerHTML = s.html; setOptions(s.threads);
        if (stick) feed.scrollTop = feed.scrollHeight;
      }
    }).catch(function(){}).finally(function(){ setTimeout(poll, 2000); });
  }
  form.addEventListener('submit', function(ev){
    ev.preventDefault();
    var body = text.value.trim();
    if (!body || !sel.value) return;
    send.disabled = true; hint.textContent = 'Posting your reply to the thread';
    fetch('api/threads/' + encodeURIComponent(sel.value) + '/reply', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({persona: document.getElementById('persona').value, text: body})
    }).then(function(r){ return r.json().then(function(j){ return [r.ok, j]; }); })
    .then(function(res){
      if (res[0]) { text.value = ''; hint.textContent = ''; }
      else hint.textContent = res[1].error || 'Reply failed';
    }).catch(function(){ hint.textContent = 'Reply failed, the channel is unreachable'; })
    .finally(function(){ send.disabled = !sel.value; version = -1; });
  });
  text.addEventListener('keydown', function(ev){
    if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); form.requestSubmit(); }
  });
  send.disabled = !sel.value;
  feed.scrollTop = feed.scrollHeight;
  setTimeout(poll, 2000);
})();
</script>
</body></html>
"""


def render_page(config: Config, channel: Channel) -> str:
    with channel.lock:
        threads = list(channel.threads.values())
        version = channel.version
        threads_html = render_threads(config, threads)
        options = thread_options(threads)
    persona_html = "".join(
        f'<option value="{esc(p.key)}">{esc(p.name)}</option>' for p in config.personas
    )
    option_html = "".join(
        f'<option value="{esc(o["id"])}"{" selected" if i == len(options) - 1 else ""}>'
        f"{esc(o['title'])}</option>"
        for i, o in enumerate(options)
    )
    replacements = {
        "__CHANNEL__": esc(config.channel_name),
        "__PERSONAS__": persona_html,
        "__THREAD_OPTIONS__": option_html,
        "__VERSION__": str(int(version)),
        "__THREADS__": threads_html,
    }
    return re.sub("|".join(replacements), lambda m: replacements[m.group(0)], PAGE)


def public_state(config: Config, channel: Channel) -> dict:
    with channel.lock:
        threads = list(channel.threads.values())
        return {
            "version": channel.version,
            "threads": thread_options(threads),
            "html": render_threads(config, threads),
            "data": [public_thread(config, t) for t in threads],
        }


def public_thread(config: Config, thread: dict) -> dict:
    session = thread.get("session") or {}
    return {
        "id": thread["id"],
        "group_key": thread["group_key"],
        "status": thread["status"],
        "title": thread_title(thread),
        "notifications": thread["notifications"],
        "alerts": list(thread["alerts"].values()),
        "session_id": session.get("session_id", ""),
        "session_url": session_link(config, session),
        "messages": thread["messages"],
        "created_at": thread["created_at"],
        "updated_at": thread["updated_at"],
    }


# ------------------------------------------------------------------------- server


class Handler(BaseHTTPRequestHandler):
    server_version = "incident-channel/1"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    @property
    def app(self) -> App:
        return self.server.app  # type: ignore[attr-defined]

    # plumbing ---------------------------------------------------------------

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return

    def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
        path = urllib.parse.urlsplit(self.path).path
        if path not in ("/healthz", "/health"):
            log(
                "http",
                method=self.command,
                path=path[:200],
                status=int(code) if str(code).isdigit() else code,
            )

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_html(self, status: int, page: str) -> None:
        body = page.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; img-src https: http: data:; style-src 'unsafe-inline'; "
            "script-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'self'; "
            "frame-ancestors 'none'",
        )
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def read_json(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY_BYTES:
            self.send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "body too large"})
            self.close_connection = True
            return None
        raw = self.rfile.read(length) if length else b""
        try:
            data = json.loads(raw or b"null")
        except ValueError:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "body must be JSON"})
            return None
        if not isinstance(data, dict):
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "body must be a JSON object"})
            return None
        return data

    def bearer_ok(self) -> bool:
        token = self.app.config.channel_token
        if not token:
            self.send_json(
                HTTPStatus.SERVICE_UNAVAILABLE, {"error": "CHANNEL_TOKEN is not configured"}
            )
            return False
        header = self.headers.get("Authorization", "")
        scheme, _, value = header.partition(" ")
        if scheme.lower() == "bearer" and hmac.compare_digest(
            value.strip().encode(), token.encode()
        ):
            return True
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("WWW-Authenticate", 'Bearer realm="incident-channel"')
        self.send_header("Content-Type", "application/json")
        body = b'{"error": "bearer token required"}'
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return False

    def basic_ok(self) -> bool:
        """nginx does basic auth at the ingress; this repeats it if BASIC_AUTH_PASSWORD is set."""
        password = self.app.config.basic_auth_password
        if not password:
            return True
        header = self.headers.get("Authorization", "")
        scheme, _, value = header.partition(" ")
        if scheme.lower() == "basic":
            try:
                user, _, given = base64.b64decode(value.strip()).decode("utf-8").partition(":")
            except (ValueError, UnicodeDecodeError):
                user, given = "", ""
            if hmac.compare_digest(user.encode(), self.app.config.basic_auth_user.encode()) and (
                hmac.compare_digest(given.encode(), password.encode())
            ):
                return True
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("WWW-Authenticate", 'Basic realm="OtterWorks incident channel"')
        self.send_header("Content-Length", "0")
        self.end_headers()
        return False

    def via_ingress(self) -> bool:
        return any(
            self.headers.get(h) for h in ("X-Forwarded-For", "X-Real-IP", "X-Forwarded-Host")
        )

    def thread_route(self, path: str) -> tuple[str, str] | None:
        match = re.fullmatch(r"/api/threads/(.+)/(messages|reply)", path)
        if not match:
            return None
        return urllib.parse.unquote(match.group(1)), match.group(2)

    # verbs ------------------------------------------------------------------

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_GET(self) -> None:  # noqa: N802
        parts = urllib.parse.urlsplit(self.path)
        path = parts.path
        if path in ("/healthz", "/health"):
            self.send_json(HTTPStatus.OK, {"ok": True, "threads": len(self.app.channel.threads)})
            return
        if path in ("/", "/index.html"):
            if self.basic_ok():
                self.send_html(HTTPStatus.OK, render_page(self.app.config, self.app.channel))
            return
        if path == "/api/state":
            if not self.basic_ok():
                return
            since = urllib.parse.parse_qs(parts.query).get("since", [""])[0]
            if since.lstrip("-").isdigit() and int(since) == self.app.channel.version:
                self.send_json(HTTPStatus.OK, {"version": self.app.channel.version})
                return
            self.send_json(HTTPStatus.OK, public_state(self.app.config, self.app.channel))
            return
        self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urllib.parse.urlsplit(self.path).path
        if path == "/alertmanager":
            self.post_alertmanager()
            return
        if path == "/api/reset":
            if self.bearer_ok() and self.read_json() is not None:
                cleared = self.app.channel.reset()
                log("reset", threads=cleared)
                self.send_json(HTTPStatus.OK, {"cleared": cleared})
            return
        route = self.thread_route(path)
        if route and route[1] == "messages":
            self.post_message(route[0])
            return
        if route and route[1] == "reply":
            self.post_reply(route[0])
            return
        self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def post_alertmanager(self) -> None:
        # In-cluster Alertmanager posts straight to the Service. Anything arriving through
        # the ingress (forwarded headers present) must carry the channel token.
        if self.via_ingress() and not self.bearer_ok():
            return
        payload = self.read_json()
        if payload is None:
            return
        try:
            result = self.app.channel.ingest_alertmanager(payload)
        except ValueError as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        log("alertmanager", **result, status=payload.get("status"))
        self.send_json(HTTPStatus.OK, result)

    def post_message(self, key: str) -> None:
        if not self.bearer_ok():
            return
        body = self.read_json()
        if body is None:
            return
        try:
            result = self.app.channel.post_devin_message(key, body)
        except LookupError:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "no such thread"})
            return
        except ValueError as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        log("devin_message", **result)
        self.send_json(HTTPStatus.CREATED, result)

    def post_reply(self, key: str) -> None:
        if not self.basic_ok():
            return
        content_type = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if content_type != "application/json":
            self.send_json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "send application/json"})
            return
        body = self.read_json()
        if body is None:
            return
        persona = self.app.config.persona(str(body.get("persona", "")))
        text = body.get("text")
        if persona is None:
            self.send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": f"persona must be one of {', '.join(PERSONA_IDS)}"},
            )
            return
        if not isinstance(text, str) or not text.strip():
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "text is required"})
            return
        text = text.strip()[:MAX_TEXT_CHARS]
        try:
            thread, message = self.app.channel.add_reply(key, persona, text)
        except LookupError:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "no such thread"})
            return
        delivery = forward_to_devin(
            self.app.config, dict(thread.get("session") or {}), persona, text
        )
        self.app.channel.set_delivery(thread["id"], message["id"], delivery)
        log(
            "reply",
            thread_id=thread["id"],
            message_id=message["id"],
            persona=persona.key,
            delivery=delivery["state"],
        )
        safe = json.loads(scrub(json.dumps(delivery), (self.app.config.devin_api_key,)))
        self.send_json(
            HTTPStatus.OK,
            {"thread_id": thread["id"], "message_id": message["id"], "delivery": safe},
        )


class App:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.channel = Channel(config)


def make_server(config: Config, host: str = "0.0.0.0", port: int = 8080) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    server.app = App(config)  # type: ignore[attr-defined]
    return server


def main() -> None:
    config = Config.from_env()
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    server = make_server(config, host, port)
    log(
        "listening",
        host=host,
        port=port,
        state_file=config.state_file,
        devin_api_base=config.devin_api_base,
        channel_token_set=bool(config.channel_token),
        devin_api_key_set=bool(config.devin_api_key),
        personas={p.key: {"name": p.name, "user_id_set": bool(p.user_id)} for p in config.personas},
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
