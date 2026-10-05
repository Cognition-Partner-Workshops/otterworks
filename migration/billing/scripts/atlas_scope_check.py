#!/usr/bin/env python3
"""Prove the Atlas principal in MONGODB_ATLAS_URI is scoped to one migration database.

PASS requires the principal's roles to be exactly readWrite on --db (no
*AnyDatabase, no atlasAdmin, no roles on other databases). Only then is the
negative probe run: an insert into another database must be refused by Atlas
with an authorization error. When the principal is over-scoped the probe is
skipped, because the insert would succeed and write outside the migration
database. The secret value is never printed; only the username and roles are.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from pymongo import MongoClient
from pymongo.errors import OperationFailure

DB_NAME_RE = re.compile(r"^ow_tp_billing_[A-Za-z0-9]+$")
PROBE_COLLECTION = "_scope_check"
UNAUTHORIZED = 13


def connection_status(client: MongoClient) -> dict:
    status = client.admin.command({"connectionStatus": 1, "showPrivileges": True})
    info = status["authInfo"]
    users = info.get("authenticatedUsers") or [{"user": "unavailable", "db": "unavailable"}]
    return {
        "user": users[0]["user"],
        "authDb": users[0]["db"],
        "roles": info.get("authenticatedUserRoles", []),
        "privileges": info.get("authenticatedUserPrivileges", []),
    }


def evaluate_roles(roles: list[dict], db_name: str) -> list[str]:
    violations = []
    for role in roles:
        if role["role"] == "readWrite" and role["db"] == db_name:
            continue
        violations.append(f"{role['role']}@{role['db']}")
    if not any(r["role"] == "readWrite" and r["db"] == db_name for r in roles):
        violations.append(f"missing readWrite@{db_name}")
    return violations


def probe_denied(client: MongoClient, other_db: str) -> dict:
    marker = {"probe": "atlas_scope_check", "at": datetime.now(timezone.utc).isoformat()}
    try:
        client[other_db][PROBE_COLLECTION].insert_one(marker)
    except OperationFailure as exc:
        return {
            "database": other_db,
            "result": "refused" if exc.code == UNAUTHORIZED else "failed-other",
            "code": exc.code,
            "codeName": exc.details.get("codeName") if exc.details else None,
            "errmsg": exc.details.get("errmsg") if exc.details else str(exc),
        }
    client[other_db][PROBE_COLLECTION].delete_one({"probe": marker["probe"], "at": marker["at"]})
    return {"database": other_db, "result": "accepted", "code": None,
            "codeName": None, "errmsg": "insert succeeded; principal is not scoped"}


def probe_allowed(client: MongoClient, db_name: str) -> dict:
    marker = {"probe": "atlas_scope_check", "at": datetime.now(timezone.utc).isoformat()}
    inserted = client[db_name][PROBE_COLLECTION].insert_one(marker)
    client[db_name][PROBE_COLLECTION].delete_one({"_id": inserted.inserted_id})
    return {"database": db_name, "result": "accepted", "code": None, "codeName": None,
            "errmsg": "insert and delete succeeded"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", required=True, help="migration database name (ow_tp_billing_<run>)")
    parser.add_argument("--out", type=Path, help="write the JSON evidence here")
    parser.add_argument("--uri-env", default="MONGODB_ATLAS_URI", help="env var holding the URI")
    args = parser.parse_args()

    if not DB_NAME_RE.match(args.db):
        print(f"--db must match {DB_NAME_RE.pattern}", file=sys.stderr)
        return 2
    uri = os.environ.get(args.uri_env)
    if not uri:
        print(f"{args.uri_env} is not set", file=sys.stderr)
        return 2

    client = MongoClient(uri, serverSelectionTimeoutMS=15000)
    status = connection_status(client)
    violations = evaluate_roles(status["roles"], args.db)
    evidence = {
        "kind": "atlas-scope-check",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "uriEnv": args.uri_env,
        "migrationDb": args.db,
        "principal": {"user": status["user"], "authDb": status["authDb"], "roles": status["roles"]},
        "privilegeResources": sorted({json.dumps(p["resource"], sort_keys=True) for p in status["privileges"]}),
        "roleViolations": violations,
        "probes": [],
    }

    if violations:
        evidence["verdict"] = "FAIL"
        evidence["reason"] = ("principal holds roles outside readWrite@" + args.db
                              + "; negative probe skipped to avoid an out-of-scope write")
    else:
        other_db = f"{args.db}_denied_probe"
        denied = probe_denied(client, other_db)
        allowed = probe_allowed(client, args.db)
        evidence["probes"] = [denied, allowed]
        if denied["result"] == "refused" and allowed["result"] == "accepted":
            evidence["verdict"] = "PASS"
            evidence["reason"] = f"readWrite@{args.db} only; insert into {other_db} refused (code {UNAUTHORIZED})"
        else:
            evidence["verdict"] = "FAIL"
            evidence["reason"] = "roles look scoped but the probes disagree; inspect probes"

    rendered = json.dumps(evidence, indent=2, default=str)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n")
    print(rendered)
    print(f"\natlas_scope_check: {evidence['verdict']} - {evidence['reason']}")
    return 0 if evidence["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
