import json
import os
import re
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener


SERVICE_ACCOUNT_DIR = Path("/var/run/secrets/kubernetes.io/serviceaccount")
STATE_CONFIGMAP = "jira-devin-relay-label-state"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ConfigMapState:
    def __init__(self):
        namespace = (SERVICE_ACCOUNT_DIR / "namespace").read_text().strip()
        self.url = f"https://kubernetes.default.svc/api/v1/namespaces/{namespace}/configmaps/{STATE_CONFIGMAP}"
        context = ssl.create_default_context(cafile=str(SERVICE_ACCOUNT_DIR / "ca.crt"))
        self.opener = build_opener(NoRedirect(), HTTPSHandler(context=context))

    def request(self, method="GET", data=None):
        token = (SERVICE_ACCOUNT_DIR / "token").read_text().strip()
        req = Request(self.url, method=method, data=data, headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/merge-patch+json",
        })
        with self.opener.open(req, timeout=2) as response:
            return json.load(response)

    def load(self):
        return {key for key, value in self.request().get("data", {}).items() if value == "true"}

    def save(self, key, present):
        self.request("PATCH", json.dumps({"data": {key: "true" if present else None}}).encode())


def label_added(changelog):
    items = changelog.get("items") if isinstance(changelog, dict) else None
    if not isinstance(items, list):
        return False
    for item in items:
        if not isinstance(item, dict) or item.get("field") != "labels":
            continue
        old, new = item.get("fromString"), item.get("toString")
        if (old is None or isinstance(old, str)) and isinstance(new, str):
            if "devin" in re.split(r"[,\s]+", new) and "devin" not in re.split(r"[,\s]+", old or ""):
                return True
    return False


class LabelGate:
    def __init__(self, state):
        self.state = state
        self.seen = state.load()
        self.lock = Lock()

    def skip_reason(self, payload, key):
        event = payload.get("webhookEvent")
        if event not in ("jira:issue_created", "jira:issue_updated"):
            return "unsupported_event"
        fields = payload["issue"].get("fields")
        labels = fields.get("labels") if isinstance(fields, dict) else None
        changelog = payload.get("changelog") if event == "jira:issue_updated" else None
        added = changelog is not None and label_added(changelog)
        if not added and not isinstance(labels, list):
            return "missing_labels"
        present = added or "devin" in labels
        with self.lock:
            previous = key in self.seen
            if present != previous:
                self.state.save(key, present)
                if present:
                    self.seen.add(key)
                else:
                    self.seen.remove(key)
            if event == "jira:issue_created":
                return None if present else "devin_label_absent"
            if changelog is not None:
                return None if added else "changelog_did_not_add_devin"
            if not present:
                return "devin_label_absent"
            return "devin_label_already_seen" if previous else None


class Relay(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def reply(self, status):
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        self.reply(200 if self.path == "/health" else 404)

    def skip(self, key, reason, status=204):
        print(f"issue={key} skip_reason={reason}", flush=True)
        self.reply(status)

    def do_POST(self):
        if self.path != "/webhook":
            self.reply(404)
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self.reply(411)
            return
        if not 0 <= length <= 4 * 1024 * 1024:
            self.reply(413)
            return
        try:
            self.connection.settimeout(10)
            body = self.rfile.read(length)
        except TimeoutError:
            self.reply(408)
            return
        if len(body) != length:
            self.reply(400)
            return
        try:
            payload = json.loads(body)
            key = payload["issue"]["key"]
        except (ValueError, KeyError, TypeError):
            self.skip("-", "invalid_payload")
            return
        if not isinstance(key, str) or not re.fullmatch(r"[A-Z0-9_]+-[0-9]+", key):
            self.skip("-", "invalid_issue_key")
            return
        try:
            reason = self.server.gate.skip_reason(payload, key)
        except (OSError, ValueError):
            self.skip(key, "label_state_unavailable", 503)
            return
        if reason is not None:
            self.skip(key, reason)
            return
        request = Request(self.server.upstream_url, data=body, headers={
            "Content-Type": self.headers.get("Content-Type", "application/json"),
            "X-Webhook-Secret": self.server.upstream_secret,
        })
        try:
            with build_opener(NoRedirect()).open(request, timeout=10) as response:
                status = response.status
        except HTTPError as error:
            status = error.code
            error.close()
        except (URLError, OSError, ValueError):
            status = None
        print(f"issue={key} upstream_status={status if status is not None else 'unavailable'}",
              flush=True)
        self.reply(status if status is not None and 200 <= status < 300 else 502)


def main():
    url = os.environ.get("DEVIN_JIRA_WEBHOOK_URL", "")
    secret = os.environ.get("DEVIN_JIRA_WEBHOOK_SECRET", "")
    try:
        target = urlsplit(url)
        valid = target.scheme == "https" and target.hostname and secret and "\r" not in secret and "\n" not in secret
    except ValueError:
        valid = False
    if not valid:
        raise SystemExit("An HTTPS upstream URL and webhook secret are required")
    try:
        gate = LabelGate(ConfigMapState())
    except (OSError, ValueError):
        raise SystemExit("Relay label state unavailable")
    with ThreadingHTTPServer(("", 8080), Relay) as server:
        server.upstream_url = url
        server.upstream_secret = secret
        server.gate = gate
        print(f"Relay listening on :8080; label filter enabled; tracked_issues={len(gate.seen)}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
