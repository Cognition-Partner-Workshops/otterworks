"""App-level parity for unit u-01-tenancy: replay the tenancy read paths on Oracle
(pkg_plans through backends.oracle) and on MongoDB (backends.mongo) and diff the rows.

Read-only on both sides. Operations: list_plans; entitlement(tenant, on) for every tenant in
the fixture on three dates; tenant_profile(tenant) (the /me tenant row).

  env -u MONGODB_ATLAS_URI python services/legacy-billing/migration/mongo/parity_tenancy.py \
      --source-dsn-secret OW_BILLING_FIXTURE_DSN --target-uri-secret MONGO_LOCAL_URI \
      --target-db ow_billing_migration --out <dir>
"""

import argparse
import json
import os
import sys
from contextlib import contextmanager
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "app"))
sys.path.insert(0, str(HERE.parent))

from common import check_allowlist, secret_from_env

ON_DATES = (date(2025, 12, 31), date(2026, 1, 15), date(2026, 3, 1))


def configure(args):
    spec = json.loads(secret_from_env(args.source_dsn_secret))
    host, rest = spec["dsn"].split(":", 1)
    port, service = rest.split("/", 1)
    os.environ.update(ORACLE_USER=spec["user"], ORACLE_PASSWORD=spec["password"],
                      ORACLE_HOST=host, ORACLE_PORT=port, ORACLE_SERVICE=service)
    check_allowlist(args.target_db)
    os.environ["MONGO_BILLING_URI"] = secret_from_env(args.target_uri_secret)
    os.environ["MONGO_BILLING_DB"] = args.target_db


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dsn-secret", required=True)
    parser.add_argument("--target-uri-secret", required=True)
    parser.add_argument("--target-db", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    configure(args)

    from backends import mongo, oracle

    # One source connection for the whole replay (source concurrency cap 1; the app
    # backend opens one per call, which exhausts the Oracle Free listener).
    shared = oracle.oracle_connect()

    @contextmanager
    def reuse_connection():
        yield shared

    oracle.oracle_connect = reuse_connection

    ops, mismatches = [], []

    def compare(name, left, right):
        ops.append(name)
        if left != right:
            mismatches.append({"op": name, "oracle": left, "mongo": right})

    # `codes` belongs to another batch (u-00-codes); when it is absent from the local
    # namespace the status label of /me cannot be resolved and is excluded, not faked.
    codes_present = "codes" in mongo._db().list_collection_names()

    def profile_rows(rows_):
        if codes_present:
            return rows_
        return [{k: v for k, v in row.items() if k != "status"} for row in rows_]

    compare("list_plans", oracle.list_plans(), mongo.list_plans())
    tenant_ids = [row["id"] for row in oracle.query("SELECT id FROM tenants ORDER BY id")]
    for tenant_id in tenant_ids:
        for on in ON_DATES:
            compare(f"entitlement:{tenant_id}:{on}", oracle.entitlement(tenant_id, on),
                    mongo.entitlement(tenant_id, on))
        compare(f"tenant_profile:{tenant_id}", profile_rows(oracle.tenant_profile(tenant_id)),
                profile_rows(mongo.tenant_profile(tenant_id)))
    compare("entitlement:unknown-tenant", oracle.entitlement("no-such-tenant", ON_DATES[1]),
            mongo.entitlement("no-such-tenant", ON_DATES[1]))

    verdict = "PASS" if not mismatches else "FAIL"
    result = {"kind": "app-parity", "unit": "u-01-tenancy", "operations": len(ops),
              "tenants": len(tenant_ids), "mismatches": len(mismatches), "verdict": verdict,
              "codes_collection_present": codes_present,
              "unverified": [] if codes_present else ["tenant_profile.status (codes lookup)"],
              "mismatch_ops": [m["op"] for m in mismatches][:50]}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "app_parity.json").write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps(result, indent=1))
    if mismatches:
        print(json.dumps(mismatches[:5], indent=1, default=str), file=sys.stderr)
    sys.exit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
