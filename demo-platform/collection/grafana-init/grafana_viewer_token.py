"""Create (or reuse) a Viewer-role service account and write its token for the Grafana MCP server.

Runs once per `up` inside the run-scoped Compose network. Never prints the token or admin password.
"""

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

URL = os.environ["GRAFANA_URL"].rstrip("/")
ADMIN = base64.b64encode(f"{os.environ['GRAFANA_ADMIN_USER']}:{os.environ['GRAFANA_ADMIN_PASSWORD']}".encode()).decode()
TOKEN_PATH = os.environ["TOKEN_PATH"]
OWNER_UID = int(os.environ.get("TOKEN_OWNER_UID", "1000"))
SA_NAME = "collection-mcp-viewer"


def call(method, path, body=None, auth=None):
    req = urllib.request.Request(URL + path, method=method, data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", auth or f"Basic {ADMIN}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 - fixed in-network URL
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        return exc.code, None


def main():
    for _ in range(60):
        try:
            if call("GET", "/api/health")[0] == 200:
                break
        except OSError:
            pass
        time.sleep(1)
    else:
        sys.exit("grafana not reachable")

    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, encoding="utf-8") as fh:
            existing = fh.read().strip()
        if existing and call("GET", "/api/search?limit=1", auth=f"Bearer {existing}")[0] == 200:
            print("grafana viewer token: reused")
            return

    status, found = call("GET", f"/api/serviceaccounts/search?query={SA_NAME}")
    if status != 200:
        sys.exit(f"service account search failed: HTTP {status}")
    accounts = [a for a in found["serviceAccounts"] if a["name"] == SA_NAME]
    if accounts:
        sa = accounts[0]
    else:
        status, sa = call("POST", "/api/serviceaccounts", {"name": SA_NAME, "role": "Viewer", "isDisabled": False})
        if status not in (200, 201):
            sys.exit(f"service account create failed: HTTP {status}")
    if sa["role"] != "Viewer":
        sys.exit("service account role is not Viewer; refusing to issue a token")
    status, tok = call("POST", f"/api/serviceaccounts/{sa['id']}/tokens", {"name": f"mcp-{int(time.time())}", "secondsToLive": 86400})
    if status != 200:
        sys.exit(f"token create failed: HTTP {status}")
    key = tok["key"]
    probe, _ = call("POST", "/api/folders", {"title": "write-probe"}, auth=f"Bearer {key}")
    if probe not in (401, 403):
        sys.exit(f"viewer token was able to write (HTTP {probe}); refusing")
    tmp = TOKEN_PATH + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o400)
    with os.fdopen(fd, "w") as fh:
        fh.write(key)
    os.chown(tmp, OWNER_UID, -1)
    os.replace(tmp, TOKEN_PATH)
    print(f"grafana viewer token: issued (role=Viewer, write probe HTTP {probe})")


if __name__ == "__main__":
    main()
