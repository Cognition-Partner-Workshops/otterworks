#!/usr/bin/env python3
"""Read sessions in one organization through the enterprise API (metadata only).

  sessions.py --org-name ViewOnly                      # every session, newest first
  sessions.py --org-name ViewOnly --owner user-...     # one persona's sessions
  sessions.py --org-name ViewOnly --session <id>       # one session, raw JSON
  sessions.py --org-name ViewOnly --archive <id>       # archive one session

Needs DEVIN_ENTERPRISE_API_KEY. DEVIN_API_BASE overrides the base URL.
"""
import argparse, http.client, json, os, sys, urllib.parse

BASE = os.environ.get("DEVIN_API_BASE", "https://partner-workshops.devinenterprise.com/api/v3")
HEADERS = {"Authorization": f"Bearer {os.environ['DEVIN_ENTERPRISE_API_KEY']}"}


ENDPOINT = urllib.parse.urlsplit(BASE)


def call(path, method="GET"):
    conn = http.client.HTTPSConnection(ENDPOINT.netloc, timeout=120)
    conn.request(method, ENDPOINT.path + path, headers=HEADERS)
    resp = conn.getresponse()
    body = resp.read()
    conn.close()
    if resp.status >= 400:
        sys.exit(f"{method} {path}: HTTP {resp.status} {body[:300]!r}")
    return json.loads(body) if body else {}


def org_id(name):
    orgs = call("/enterprise/organizations")
    items = orgs.get("items", orgs if isinstance(orgs, list) else [])
    key = name.lower().replace(" ", "").replace("-", "")
    for o in items:
        if key in (o.get("name") or "").lower().replace(" ", "").replace("-", ""):
            return o.get("org_id") or o.get("id")
    sys.exit(f"no organization matches {name!r}; have: {[o.get('name') for o in items]}")


def all_sessions(org):
    after = None
    while True:
        q = f"/organizations/{org}/sessions?first=200" + (f"&after={urllib.parse.quote(after)}" if after else "")
        r = call(q)
        for s in r.get("items", []):
            yield s
        info = r.get("page_info") or {}
        after = info.get("end_cursor") or r.get("end_cursor")
        if not info.get("has_next_page") or not after:
            break


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--org-name", required=True)
    ap.add_argument("--owner")
    ap.add_argument("--session")
    ap.add_argument("--archive")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    org = org_id(a.org_name)
    if a.session:
        print(json.dumps(call(f"/organizations/{org}/sessions/{a.session}"), indent=1))
        return
    if a.archive:
        print(json.dumps(call(f"/organizations/{org}/sessions/{a.archive}/archive", "POST"), indent=1))
        return
    rows = []
    for s in all_sessions(org):
        owner = s.get("creator_id") or s.get("owner_id") or s.get("user_id")
        if a.owner and owner != a.owner:
            continue
        if s.get("is_archived") or s.get("archived"):
            continue
        rows.append({"id": s.get("session_id") or s.get("id"), "owner": owner, "title": s.get("title"),
                     "status": s.get("status") or s.get("status_enum"), "parent": s.get("parent_session_id"),
                     "acu": s.get("acu_used") or s.get("acu")})
    if a.json:
        print(json.dumps(rows, indent=1))
        return
    for r in rows:
        print(f"{r['id']}  {'child ' if r['parent'] else '      '}{r['title']}")
    print(f"{len(rows)} sessions", file=sys.stderr)


if __name__ == "__main__":
    main()
