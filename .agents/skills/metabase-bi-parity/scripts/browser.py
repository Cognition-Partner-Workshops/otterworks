"""Sign the running Chrome into the local Metabase, or open dashboards in new windows.

    browser.py login                  # needs MB_ADMIN_PASSWORD; MB_URL, MB_ADMIN_EMAIL optional
    browser.py open <url> [<url> ...] # one new window per URL

Both attach to Chrome's CDP endpoint (CDP_URL, default http://localhost:29229).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request

from playwright.sync_api import sync_playwright

CDP_URL = os.environ.get("CDP_URL", "http://localhost:29229")
MB_URL = os.environ.get("MB_URL", "http://127.0.0.1:3000").rstrip("/")


def session_id() -> str:
    body = {
        "username": os.environ.get("MB_ADMIN_EMAIL", "admin@otterworks.local"),
        "password": os.environ["MB_ADMIN_PASSWORD"],
    }
    request = urllib.request.Request(
        MB_URL + "/api/session",
        method="POST",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())["id"]


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ("login", "open"):
        print(__doc__, file=sys.stderr)
        return 2
    with sync_playwright() as p:
        context = p.chromium.connect_over_cdp(CDP_URL).contexts[0]
        if sys.argv[1] == "login":
            port = urllib.parse.urlparse(MB_URL).port or 80
            sid = session_id()
            for host in ("127.0.0.1", "localhost"):
                cookie = {"name": "metabase.SESSION", "value": sid, "httpOnly": True}
                context.add_cookies([{**cookie, "url": f"http://{host}:{port}"}])
            print("Metabase session cookie set")
            return 0
        page = context.pages[0] if context.pages else context.new_page()
        cdp = context.new_cdp_session(page)
        for url in sys.argv[2:]:
            cdp.send("Target.createTarget", {"url": url, "newWindow": True})
            print("opened", url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
