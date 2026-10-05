#!/usr/bin/env python3
"""Connectivity probe for the OtterWorks billing migration (Oracle OW_BILLING -> MongoDB Atlas).

Capability checks, not just authentication, under the connectivity policy
d-connectivity-policy (auto: live when the named secret is set and reachable,
local fixture fallback otherwise; online: live only):

  oracle      read OW_BILLING.TENANTS as the read-only principal, then attempt an
              insert inside a READ ONLY transaction; the attempt must be refused by
              Oracle for a missing privilege (ORA-01031, or ORA-41900 on 23ai) and is
              rolled back, so nothing is written even if the refusal did not come.
  atlas       ping, connectionStatus {showPrivileges}, then insert + delete of one
              probe document in the migration database only; the probe collection
              is dropped afterwards. No other database is touched.
  accessList  the calling IP is covered by the project IP access list (Atlas Admin
              API, read-only).
  fallback    availability of the local fixtures (mongo:7 image, Oracle Free image
              and fixture container); exercised only when a live endpoint is down.

Secrets are referenced by name only (MONGODB_ATLAS_URI, OW_TP_ORACLE_RO_DSN,
MONGODB_ATLAS_PUBLIC_KEY / MONGODB_ATLAS_PRIVATE_KEY / MONGODB_ATLAS_PROJECT_ID)
and never printed. A result with runMode "fallback" is never merge evidence.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import oracledb
import requests
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from requests.auth import HTTPDigestAuth

DB_NAME_RE = re.compile(r"^ow_tp_billing_[A-Za-z0-9]+$")
PROBE_COLLECTION = "_connectivity_probe"
ORA_MISSING_PRIVILEGE = {1031, 41900}  # ORA-01031 insufficient privileges; ORA-41900 missing <priv> privilege (23ai)
DML_SYSTEM_PRIVILEGES = {"INSERT ANY TABLE", "UPDATE ANY TABLE", "DELETE ANY TABLE", "ALTER ANY TABLE", "DROP ANY TABLE", "CREATE ANY TABLE"}
DML_OBJECT_PRIVILEGES = {"INSERT", "UPDATE", "DELETE", "ALTER"}
ORA_READ_ONLY_TRANSACTION = 1456
ATLAS_API = "https://cloud.mongodb.com/api/atlas/v2"
ATLAS_ACCEPT = "application/vnd.atlas.2024-08-05+json"
LOCAL_MONGO_NAME = "ow-billing-mongo"
LOCAL_MONGO_PORT = int(os.environ.get("OW_BILLING_LOCAL_MONGO_PORT", "27117"))
ORACLE_FIXTURE_PORT = os.environ.get("ORACLE_BILLING_DB_PORT", "52521")
ORACLE_FIXTURE_IMAGE = "container-registry.oracle.com/database/free:latest"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def oracle_error(exc: oracledb.Error) -> dict:
    err = exc.args[0] if exc.args else None
    code = getattr(err, "code", None) or getattr(err, "full_code", None)
    message = getattr(err, "message", str(exc)).strip()
    return {"code": code, "message": message.splitlines()[0]}


def oracle_kwargs(source: str) -> dict:
    if source == "live":
        raw = os.environ["OW_TP_ORACLE_RO_DSN"]
        try:
            cfg = json.loads(raw)
            return {"user": cfg["user"], "password": cfg["password"], "dsn": cfg["dsn"]}
        except (ValueError, KeyError, TypeError):
            return {"dsn": raw}
    return {"user": "ow_billing", "password": "ow_billing", "dsn": f"localhost:{ORACLE_FIXTURE_PORT}/FREEPDB1"}


def probe_oracle(source: str) -> dict:
    result = {"source": source, "secretEnv": "OW_TP_ORACLE_RO_DSN" if source == "live" else None,
              "thinMode": oracledb.is_thin_mode()}
    with oracledb.connect(**oracle_kwargs(source)) as con:
        con.autocommit = False
        cur = con.cursor()
        cur.execute("SELECT USER FROM dual")
        result["principal"] = cur.fetchone()[0]
        result["serverVersion"] = con.version
        cur.execute("SELECT COUNT(*) FROM OW_BILLING.TENANTS")
        result["read"] = {"statement": "SELECT COUNT(*) FROM OW_BILLING.TENANTS",
                          "tenantsCount": cur.fetchone()[0], "result": "ok"}
        cur.execute("SELECT privilege FROM session_privs ORDER BY privilege")
        result["sessionPrivileges"] = [row[0] for row in cur.fetchall()]
        cur.execute("SELECT privilege, COUNT(*) FROM user_tab_privs WHERE owner = 'OW_BILLING' "
                    "GROUP BY privilege ORDER BY privilege")
        result["owBillingObjectPrivileges"] = {row[0]: row[1] for row in cur.fetchall()}

        insert = "INSERT INTO OW_BILLING.TENANTS SELECT * FROM OW_BILLING.TENANTS WHERE 1 = 0"
        attempt = {"statement": insert, "transaction": "SET TRANSACTION READ ONLY", "rowsAffected": 0}
        con.rollback()
        cur.execute("SET TRANSACTION READ ONLY")
        try:
            cur.execute(insert)
            attempt["rowsAffected"] = cur.rowcount
            attempt["result"] = "accepted"
            attempt["error"] = None
        except oracledb.Error as exc:
            err = oracle_error(exc)
            attempt["error"] = err
            if err["code"] in ORA_MISSING_PRIVILEGE:
                attempt["result"] = "refused"
                attempt["refusedBy"] = "missing-privilege"
            elif err["code"] == ORA_READ_ONLY_TRANSACTION:
                attempt["result"] = "refused"
                attempt["refusedBy"] = "read-only-transaction"
            else:
                attempt["result"] = "failed-other"
                attempt["refusedBy"] = None
        finally:
            con.rollback()
            attempt["rolledBack"] = True
        result["insert"] = attempt
    result["dmlPrivileges"] = sorted(DML_SYSTEM_PRIVILEGES & set(result["sessionPrivileges"])
                                     | DML_OBJECT_PRIVILEGES & set(result["owBillingObjectPrivileges"]))
    result["readOnlyPrincipal"] = (result["insert"].get("refusedBy") == "missing-privilege"
                                   and not result["dmlPrivileges"])
    return result


def oracle_fixture_healthy() -> bool:
    out = subprocess.run(["docker", "ps", "--filter", "name=otterworks-oracle-billing",
                          "--filter", "health=healthy", "--format", "{{.Names}}"],
                         capture_output=True, text=True, check=False)
    return bool(out.stdout.strip())


def check_oracle(mode: str) -> dict:
    attempts = []
    if os.environ.get("OW_TP_ORACLE_RO_DSN"):
        try:
            result = probe_oracle("live")
            result["runMode"] = "live"
            return result
        except Exception as exc:  # noqa: BLE001 - recorded, never printed with the DSN
            attempts.append({"source": "live", "error": type(exc).__name__ + ": " + str(exc).splitlines()[0]})
    else:
        attempts.append({"source": "live", "error": "OW_TP_ORACLE_RO_DSN is not set"})
    if mode == "online":
        return {"runMode": "live", "result": "unreachable", "attempts": attempts}
    if not oracle_fixture_healthy():
        attempts.append({"source": "fixture", "error": "fixture not running/healthy; make oracle-billing-up"})
        return {"runMode": "fallback", "result": "unavailable", "attempts": attempts}
    result = probe_oracle("fixture")
    result["runMode"] = "fallback"
    result["attempts"] = attempts
    result["note"] = "fixture login is the schema owner, not a read-only principal; never merge evidence"
    return result


def connection_status(client: MongoClient) -> dict:
    status = client.admin.command({"connectionStatus": 1, "showPrivileges": True})
    info = status["authInfo"]
    users = info.get("authenticatedUsers") or [{"user": "unavailable", "db": "unavailable"}]
    return {"user": users[0]["user"], "authDb": users[0]["db"],
            "roles": info.get("authenticatedUserRoles", []),
            "privilegeResources": sorted({json.dumps(p["resource"], sort_keys=True)
                                          for p in info.get("authenticatedUserPrivileges", [])})}


def probe_atlas(uri: str, db_name: str, source: str) -> dict:
    client = MongoClient(uri, serverSelectionTimeoutMS=15000)
    try:
        ping = client.admin.command({"ping": 1})
        hello = client.admin.command({"hello": 1})
        result = {"source": source, "secretEnv": "MONGODB_ATLAS_URI" if source == "live" else None,
                  "ping": ping.get("ok"), "host": hello.get("me") or hello.get("primary"),
                  "migrationDb": db_name}
        if source == "live":
            result["principal"] = connection_status(client)
            result["scopeEnforcement"] = "convention"
            result["scopeNote"] = ("principal holds *AnyDatabase roles; the write boundary to the migration "
                                   "database is enforced by convention (migration/billing/README.md, UNT-3); "
                                   "no cross-database probe was run")
        db = client[db_name]
        result["read"] = {"collections": sorted(db.list_collection_names()), "result": "ok"}
        marker = {"probe": "connectivity_probe", "at": now()}
        inserted = db[PROBE_COLLECTION].insert_one(marker)
        deleted = db[PROBE_COLLECTION].delete_one({"_id": inserted.inserted_id}).deleted_count
        remaining = db[PROBE_COLLECTION].count_documents({})
        db.drop_collection(PROBE_COLLECTION)
        result["write"] = {"database": db_name, "collection": PROBE_COLLECTION, "inserted": 1,
                           "deleted": deleted, "remaining": remaining, "collectionDropped": True,
                           "result": "accepted" if deleted == 1 and remaining == 0 else "failed"}
        return result
    finally:
        client.close()


def local_mongo_up() -> bool:
    ps = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True, check=False)
    if LOCAL_MONGO_NAME in ps.stdout.split():
        return True
    subprocess.run(["docker", "rm", "-f", LOCAL_MONGO_NAME], capture_output=True, check=False)
    run = subprocess.run(["docker", "run", "-d", "--name", LOCAL_MONGO_NAME,
                          "-p", f"127.0.0.1:{LOCAL_MONGO_PORT}:27017", "mongo:7"], capture_output=True, check=False)
    return run.returncode == 0


def check_atlas(mode: str, db_name: str) -> dict:
    attempts = []
    if os.environ.get("MONGODB_ATLAS_URI"):
        try:
            result = probe_atlas(os.environ["MONGODB_ATLAS_URI"], db_name, "live")
            result["runMode"] = "live"
            return result
        except PyMongoError as exc:
            attempts.append({"source": "live", "error": type(exc).__name__ + ": " + str(exc).splitlines()[0]})
    else:
        attempts.append({"source": "live", "error": "MONGODB_ATLAS_URI is not set"})
    if mode == "online":
        return {"runMode": "live", "result": "unreachable", "attempts": attempts}
    if not local_mongo_up():
        attempts.append({"source": "fixture", "error": f"could not start {LOCAL_MONGO_NAME} (mongo:7)"})
        return {"runMode": "fallback", "result": "unavailable", "attempts": attempts}
    result = probe_atlas(f"mongodb://127.0.0.1:{LOCAL_MONGO_PORT}/", db_name, "fixture")
    result["runMode"] = "fallback"
    result["attempts"] = attempts
    result["note"] = "local mongo:7 fixture, no authentication; never merge evidence"
    return result


def check_access_list() -> dict:
    result = {"api": f"{ATLAS_API}/groups/<project>/accessList", "method": "GET"}
    try:
        ip = requests.get("https://api.ipify.org", timeout=10).text.strip()
        ipaddress.ip_address(ip)
        result["callingIp"] = ip
    except Exception as exc:  # noqa: BLE001
        result.update(result="unknown", error=f"public IP lookup failed: {exc}")
        return result
    keys = ("MONGODB_ATLAS_PUBLIC_KEY", "MONGODB_ATLAS_PRIVATE_KEY", "MONGODB_ATLAS_PROJECT_ID")
    if not all(os.environ.get(k) for k in keys):
        result.update(result="unknown", error="Atlas API key secrets are not set")
        return result
    project = os.environ["MONGODB_ATLAS_PROJECT_ID"]
    auth = HTTPDigestAuth(os.environ["MONGODB_ATLAS_PUBLIC_KEY"], os.environ["MONGODB_ATLAS_PRIVATE_KEY"])
    entries = []
    page = 1
    while True:
        r = requests.get(f"{ATLAS_API}/groups/{project}/accessList",
                         params={"pageNum": page, "itemsPerPage": 100},
                         auth=auth, headers={"Accept": ATLAS_ACCEPT}, timeout=30)
        if not r.ok:
            result.update(result="unknown", error=f"HTTP {r.status_code}")
            return result
        body = r.json()
        entries.extend(body.get("results", []))
        if len(entries) >= body.get("totalCount", 0) or len(body.get("results", [])) < 100:
            break
        page += 1
    cidrs = [e.get("cidrBlock") or e.get("ipAddress") for e in entries]
    cidrs = [c for c in cidrs if c]
    address = ipaddress.ip_address(ip)
    covering = [c for c in cidrs if address in ipaddress.ip_network(c, strict=False)]
    result.update(entries=len(cidrs), coveringEntries=covering,
                  result="covered" if covering else "not-covered")
    return result


def image_present(image: str) -> bool:
    return subprocess.run(["docker", "image", "inspect", image], capture_output=True, check=False).returncode == 0


def check_fallback(oracle_mode: str, atlas_mode: str) -> dict:
    ps = subprocess.run(["docker", "ps", "--format", "{{.Names}} {{.Status}}"], capture_output=True, text=True, check=False)
    running = dict(line.split(" ", 1) for line in ps.stdout.splitlines() if " " in line)
    return {
        "policy": "auto: live when the named secret is set and reachable, local fixture otherwise",
        "mongo": {"image": "mongo:7", "imagePresent": image_present("mongo:7"),
                  "container": LOCAL_MONGO_NAME, "port": LOCAL_MONGO_PORT,
                  "containerStatus": running.get(LOCAL_MONGO_NAME, "not running"),
                  "exercised": atlas_mode == "fallback"},
        "oracle": {"image": ORACLE_FIXTURE_IMAGE, "imagePresent": image_present(ORACLE_FIXTURE_IMAGE),
                   "fixture": "make oracle-billing-up && make oracle-billing-seed NS=demo",
                   "port": int(ORACLE_FIXTURE_PORT), "fixtureHealthy": oracle_fixture_healthy(),
                   "exercised": oracle_mode == "fallback"},
    }


def summarize_preflight(path: Path | None) -> dict | None:
    if path is None:
        return None
    if not path.exists():
        return {"manifest": str(path), "result": "missing"}
    manifest = json.loads(path.read_text())
    return {"command": "make tp-preflight PLATFORM=atlas", "manifest": str(path),
            "checkedAt": manifest.get("checked_at"),
            "probes": {p["id"]: {"result": p["result"], "detail": p["detail"]} for p in manifest.get("probes", [])},
            "note": ("run with MONGODB_ATLAS_URI unset so the repo preflight's db-user-write probe "
                     "(which targets the ow_tp_preflight database) is skipped; the wire-protocol write "
                     "capability is proven below against the migration database only")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", required=True, help="migration database name (ow_tp_billing_<run>)")
    parser.add_argument("--mode", choices=("auto", "online"), default=os.environ.get("OW_BILLING_ENV_MODE", "auto"))
    parser.add_argument("--preflight", type=Path, help="tp-preflight atlas manifest to summarize")
    parser.add_argument("--out", type=Path, help="write the JSON result here")
    args = parser.parse_args()
    if not DB_NAME_RE.match(args.db):
        print(f"--db must match {DB_NAME_RE.pattern}", file=sys.stderr)
        return 2

    oracle = check_oracle(args.mode)
    atlas = check_atlas(args.mode, args.db)
    access_list = check_access_list()
    fallback = check_fallback(oracle["runMode"], atlas["runMode"])
    run_mode = "live" if oracle["runMode"] == "live" and atlas["runMode"] == "live" else "fallback"

    checks = {
        "oracleRead": oracle.get("read", {}).get("result") == "ok",
        "oracleInsertRefusedByPrivilege": oracle.get("insert", {}).get("refusedBy") == "missing-privilege",
        "oracleReadOnlyPrincipal": bool(oracle.get("readOnlyPrincipal")),
        "atlasRead": atlas.get("read", {}).get("result") == "ok",
        "atlasWriteMigrationDb": atlas.get("write", {}).get("result") == "accepted",
        "accessListCoversCallingIp": access_list.get("result") == "covered",
    }
    if run_mode == "fallback":
        checks["oracleInsertRefusedByPrivilege"] = checks["oracleReadOnlyPrincipal"] = False
    verdict = "PASS" if run_mode == "live" and all(checks.values()) else "FAIL"
    report = {
        "kind": "connectivity-probe",
        "checkedAt": now(),
        "policy": args.mode,
        "runMode": run_mode,
        "migrationDb": args.db,
        "preflight": summarize_preflight(args.preflight),
        "oracle": oracle,
        "atlas": atlas,
        "accessList": access_list,
        "fallback": fallback,
        "checks": checks,
        "verdict": verdict,
    }
    rendered = json.dumps(report, indent=2, default=str)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n")
    print(rendered)
    print(f"\nconnectivity_probe: {verdict} (runMode={run_mode})")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
