"""Emit user_id, devin_mode and acus_consumed for explicitly configured v3 session ids only.

Usage: COLLECTION_GOVERNANCE_SESSION_IDS="devin-a,devin-b" python -m collection_slack.governance
       python -m collection_slack.governance --ids-file ids.txt

Never lists or crawls sessions; each id is fetched with GET /sessions/{id}.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .config import ConfigError, load_config
from .devin_client import DevinClient, VerificationError, normalize_session_id
from .httpjson import HTTPFailure


def _ids(args: argparse.Namespace) -> list[str]:
    raw: list[str] = []
    if args.ids_file:
        with open(args.ids_file, encoding="utf-8") as fh:
            raw += [line.strip() for line in fh if line.strip() and not line.startswith("#")]
    raw += [s.strip() for s in os.environ.get("COLLECTION_GOVERNANCE_SESSION_IDS", "").split(",") if s.strip()]
    out: list[str] = []
    for r in raw:
        sid = normalize_session_id(r)
        if sid not in out:
            out.append(sid)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ids-file")
    args = parser.parse_args(argv)
    env = dict(os.environ)
    env["COLLECTION_MODE"] = "live"
    env.setdefault("COLLECTION_ACCESS_TOKEN", "governance-helper-unused")
    env.setdefault("COLLECTION_CREATE_AS_USER_ID", "governance-unused")
    try:
        client = DevinClient(load_config(env))
        ids = _ids(args)
    except (ConfigError, VerificationError, ValueError) as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
    if not ids:
        print("no session ids configured", file=sys.stderr)
        return 2
    rc = 0
    for sid in ids:
        try:
            data = client.get_session(sid)
        except HTTPFailure as exc:
            print(json.dumps({"session_id": sid, "error": f"status={exc.status} {exc.reason}".strip()}))
            rc = 1
            continue
        print(
            json.dumps(
                {
                    "session_id": sid,
                    "user_id": data.get("user_id"),
                    "devin_mode": data.get("devin_mode"),
                    "acus_consumed": data.get("acus_consumed"),
                }
            )
        )
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
