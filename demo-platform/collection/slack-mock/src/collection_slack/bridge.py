"""Routes thread messages to exactly one of: a direct Devin session, the automation webhook, or nothing.

All network calls run on one worker thread so session creation per thread is serialized;
the SQLite claim in Store.claim_session makes the single-session guarantee hold across
concurrent requests and restarts.
"""

from __future__ import annotations

import logging
import queue
import re
import threading
from collections import Counter
from typing import Any

from .config import AutomationRule, Config
from .db import BOT_HANDLE, Store
from .devin_client import DevinClient, VerificationError
from .httpjson import HTTPFailure, request_json

log = logging.getLogger("collection_slack.bridge")

MENTION_RE = re.compile(r"(?<![\w@])@devin\b", re.IGNORECASE)
STUB_NOTE = "[STUB MODE] No Devin session was created. This workspace is not connected to the Devin API."

ACTIVE = "active"
CREATING = "creating"
VERIFYING = "verifying"


def mentions_devin(text: str) -> bool:
    return bool(MENTION_RE.search(text))


class Bridge:
    def __init__(self, config: Config, store: Store, client: DevinClient | None = None) -> None:
        self.config = config
        self.store = store
        self.client = client if client is not None else (DevinClient(config) if config.live else None)
        self.metrics: Counter[str] = Counter()
        self._jobs: queue.Queue[tuple[str, int] | None] = queue.Queue()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._barriers: dict[int, threading.Event] = {}

    # ---- lifecycle ----------------------------------------------------------
    def start(self) -> None:
        self._recover()
        worker = threading.Thread(target=self._worker, name="bridge-worker", daemon=True)
        worker.start()
        self._threads.append(worker)
        if self.client is not None:
            poller = threading.Thread(target=self._poller, name="bridge-poller", daemon=True)
            poller.start()
            self._threads.append(poller)

    def stop(self) -> None:
        self._stop.set()
        self._jobs.put(None)
        for t in self._threads:
            t.join(timeout=5)

    def drain(self, timeout: float = 10.0) -> None:
        """Test helper: wait until queued jobs are processed."""
        done = threading.Event()
        self._barriers[id(done)] = done
        self._jobs.put(("barrier", id(done)))
        done.wait(timeout)

    def _recover(self) -> None:
        for row in self.store.threads_with_state(CREATING):
            # We cannot know whether the create call reached the API; never create a second one silently.
            self.store.update_session(row["thread_id"], state="interrupted", detail="restart during create")
            self.store.add_system_message(
                row["thread_id"],
                "Session creation was interrupted by a restart. Mention @devin again to retry.",
            )
        for row in self.store.threads_with_state(VERIFYING):
            self._jobs.put(("thread", row["thread_id"]))
        for tid in self.store.threads_with_pending():
            self._jobs.put(("thread", tid))
        for mid in self.store.pending_automation():
            self._jobs.put(("automation", mid))

    # ---- routing --------------------------------------------------------------
    def on_user_message(self, thread_id: int, message_id: int, channel_name: str, body: str) -> str:
        """Decide the route for a new user message. Returns the route name."""
        self.metrics["messages_total"] += 1
        sess = self.store.session_for(thread_id)
        if sess is not None and sess["state"] in (ACTIVE, CREATING, VERIFYING):
            if self.store.claim_dispatch(message_id, "forward"):
                self.store.set_forward_state(message_id, "pending")
                self._jobs.put(("thread", thread_id))
            return "forward"

        rule = self._automation_rule(channel_name, body)
        if rule is not None:
            if self.store.claim_dispatch(message_id, "automation"):
                self._jobs.put(("automation", message_id))
            return "automation"

        if not mentions_devin(body):
            return "none"

        if not self.config.live:
            if self.store.claim_dispatch(message_id, "direct"):
                self.store.set_dispatch(message_id, "stub")
                self.store.add_system_message(thread_id, STUB_NOTE)
                self.metrics["stub_replies_total"] += 1
            return "stub"

        if self.store.claim_session(thread_id, message_id):
            self.store.claim_dispatch(message_id, "direct")
            self._jobs.put(("thread", thread_id))
            return "direct"
        # Lost the race: another message is creating the session; forward this one once it exists.
        sess = self.store.session_for(thread_id)
        if (
            sess is not None
            and sess["state"] in (ACTIVE, CREATING, VERIFYING)
            and self.store.claim_dispatch(message_id, "forward")
        ):
            self.store.set_forward_state(message_id, "pending")
            self._jobs.put(("thread", thread_id))
            return "forward"
        return "none"

    def _automation_rule(self, channel_name: str, body: str) -> AutomationRule | None:
        if not self.config.automation_enabled:
            return None
        for rule in self.config.automation_rules:
            if rule.channel and rule.channel != channel_name:
                continue
            if rule.kind == "mention" and mentions_devin(body):
                return rule
            if rule.kind == "alert" and rule.pattern is not None and rule.pattern.search(body):
                return rule
        return None

    # ---- worker ---------------------------------------------------------------
    def _worker(self) -> None:
        while not self._stop.is_set():
            job = self._jobs.get()
            if job is None:
                return
            kind, ident = job
            try:
                if kind == "thread":
                    self._process_thread(ident)
                elif kind == "automation":
                    self._process_automation(ident)
                elif kind == "barrier":
                    ev = self._barriers.pop(ident, None)
                    if ev:
                        ev.set()
            except Exception:  # noqa: BLE001 - keep the worker alive; details are not logged to avoid leaking payloads
                log.exception("bridge job %s failed", kind)

    def _process_thread(self, thread_id: int) -> None:
        sess = self.store.session_for(thread_id)
        if sess is None:
            return
        if sess["state"] == CREATING and sess["session_id"] is None:
            self._create_session(thread_id, sess["initial_message_id"])
            sess = self.store.session_for(thread_id)
        elif sess["state"] == VERIFYING and sess["session_id"]:
            self._verify(thread_id, sess["session_id"], sess["initial_message_id"], sess["session_url"])
            sess = self.store.session_for(thread_id)
        if sess is None or sess["state"] != ACTIVE:
            for row in self.store.pending_forwards(thread_id):
                if sess is not None and sess["state"] == CREATING:
                    return
                self.store.set_forward_state(row["id"], "skipped")
            return
        assert self.client is not None
        for row in self.store.pending_forwards(thread_id):
            text = f"{self.store.display_name(row['author_handle'])}: {row['body']}"
            try:
                self.client.send_message(sess["session_id"], text)
            except HTTPFailure as exc:
                self.metrics["http_failures_total"] += 1
                self.store.set_forward_state(row["id"], "failed")
                self.store.set_dispatch(row["id"], "failed", _describe(exc))
                self.store.add_system_message(thread_id, f"Could not forward a message to Devin ({_describe(exc)}).")
                continue
            self.metrics["forwards_total"] += 1
            self.store.set_forward_state(row["id"], "sent")
            self.store.set_dispatch(row["id"], "sent")

    def _create_session(self, thread_id: int, initial_message_id: int) -> None:
        assert self.client is not None
        msg = self.store.one("SELECT * FROM messages WHERE id = ?", (initial_message_id,))
        thread = self.store.thread(thread_id)
        if msg is None or thread is None:
            self.store.update_session(thread_id, state="failed", detail="missing message")
            return
        channel = self.store.channel(thread["channel_id"])
        channel_name = channel["name"] if channel else "unknown"
        author = self.store.display_name(msg["author_handle"])
        prompt = (
            f"You were mentioned in the mock Slack workspace, channel #{channel_name}, thread {thread_id}.\n"
            f"Later messages in this thread are forwarded to you prefixed with the author's name.\n\n"
            f"{author}: {msg['body']}"
        )
        try:
            created = self.client.create_session(prompt, f"#{channel_name} thread {thread_id}")
        except HTTPFailure as exc:
            self.metrics["http_failures_total"] += 1
            state = "interrupted" if exc.timed_out else "failed"
            self.store.update_session(thread_id, state=state, detail=_describe(exc))
            self.store.set_dispatch(initial_message_id, state, _describe(exc))
            self.store.add_system_message(
                thread_id, f"Devin session was not started ({_describe(exc)}). Mention @devin again to retry."
            )
            return
        except VerificationError as exc:
            # The create call succeeded, so a remote session may exist; never reclaim (no duplicate sessions).
            detail = f"{exc}; not retried automatically"
            self.metrics["verification_failures_total"] += 1
            self.store.update_session(thread_id, state="rejected", detail=detail)
            self.store.set_dispatch(initial_message_id, "rejected", detail)
            self.store.add_system_message(thread_id, f"Devin session could not be confirmed and will not be used ({detail}).")
            return
        self.store.update_session(thread_id, session_id=created.session_id, session_url=created.url, state=VERIFYING)
        self._verify(thread_id, created.session_id, initial_message_id, created.url)

    def _verify(self, thread_id: int, session_id: str, initial_message_id: int, url: str | None) -> None:
        assert self.client is not None
        try:
            self.client.verify_session(session_id)
        except (VerificationError, HTTPFailure) as exc:
            detail = str(exc) if isinstance(exc, VerificationError) else _describe(exc)
            self.metrics["verification_failures_total"] += 1
            self.store.update_session(thread_id, state="rejected", detail=detail)
            self.store.set_dispatch(initial_message_id, "rejected", detail)
            self.store.add_system_message(thread_id, f"Devin session failed verification and will not be used ({detail}).")
            try:
                self.client.archive_session(session_id)
            except HTTPFailure:
                self.metrics["http_failures_total"] += 1
            return
        self.metrics["sessions_created_total"] += 1
        self.store.update_session(thread_id, state=ACTIVE, session_url=url)
        self.store.set_dispatch(initial_message_id, "sent")
        self.store.add_system_message(thread_id, "Devin session started for this thread (persona and Fusion verified).")

    def _process_automation(self, message_id: int) -> None:
        msg = self.store.one(
            """SELECT m.*, c.name AS channel_name FROM messages m JOIN threads t ON t.id = m.thread_id
               JOIN channels c ON c.id = t.channel_id WHERE m.id = ?""",
            (message_id,),
        )
        if msg is None or not self.config.automation_url or not self.config.automation_secret:
            self.store.set_dispatch(message_id, "failed", "automation not configured")
            return
        payload: dict[str, Any] = {
            "source": "collection-slack-mock",
            "event": "alert" if not mentions_devin(msg["body"]) else "mention",
            "channel": msg["channel_name"],
            "thread_id": msg["thread_id"],
            "message_id": message_id,
            "author": self.store.display_name(msg["author_handle"]),
            "text": msg["body"],
        }
        try:
            request_json(
                "POST",
                self.config.automation_url,
                label="automation_webhook",
                headers={"X-Webhook-Secret": self.config.automation_secret},
                body=payload,
                timeout=self.config.http_timeout,
            )
        except HTTPFailure as exc:
            self.metrics["http_failures_total"] += 1
            self.store.set_dispatch(message_id, "failed", _describe(exc))
            self.store.add_system_message(msg["thread_id"], f"Automation webhook call failed ({_describe(exc)}).")
            return
        self.metrics["automation_posts_total"] += 1
        self.store.set_dispatch(message_id, "sent")
        self.store.add_system_message(msg["thread_id"], "Sent to the configured Devin automation (no direct session).")

    # ---- poller ---------------------------------------------------------------
    def _poller(self) -> None:
        while not self._stop.wait(self.config.poll_interval):
            self.poll_once()

    def poll_once(self) -> int:
        assert self.client is not None
        added = 0
        for sess in self.store.threads_with_state(ACTIVE):
            cursor = sess["last_cursor"]
            for _ in range(20):
                try:
                    items, end_cursor, has_next = self.client.list_messages(sess["session_id"], cursor)
                except HTTPFailure:
                    self.metrics["http_failures_total"] += 1
                    break
                for item in items:
                    if item.source == "devin" and self.store.add_devin_message(sess["thread_id"], item.event_id, item.message):
                        added += 1
                if end_cursor:
                    cursor = end_cursor
                    self.store.update_session(sess["thread_id"], last_cursor=end_cursor)
                if not has_next or not end_cursor:
                    break
        self.metrics["devin_messages_total"] += added
        return added


def _describe(exc: HTTPFailure) -> str:
    if exc.status is None:
        return exc.reason or "network error"
    return f"HTTP {exc.status}" + (f" {exc.error_code}" if exc.error_code else "")


__all__ = ["Bridge", "BOT_HANDLE", "mentions_devin"]
