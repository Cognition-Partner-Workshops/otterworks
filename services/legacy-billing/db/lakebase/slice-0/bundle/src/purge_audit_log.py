"""Purge BILLING_AUDIT_LOG rows older than the retention window on the Lakebase run branch.

Legacy: JOB_PURGE_AUDIT_LOG, `DELETE FROM billing_audit_log WHERE logged_at < SYSDATE - 90`
with the error swallowed. Here the retention is a parameter, a failure fails the run, and the
target is an allowlist: the project and branch are read from the committed
.migration/policy.json (synced with the bundle) and the job connects to that branch's endpoint
and nothing else.
"""
import argparse
import json
import sys
from pathlib import Path

import psycopg
from databricks.sdk import WorkspaceClient
from psycopg import sql


def policy_path() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".migration" / "policy.json"
        if candidate.is_file():
            return candidate
    raise SystemExit("committed .migration/policy.json not found next to the bundle")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--retention-days", type=int, required=True)
    ap.add_argument("--endpoint-id", default="primary")
    args = ap.parse_args()
    if args.retention_days < 1:
        raise SystemExit("retention must be at least one day")
    if not args.endpoint_id.isidentifier():
        raise SystemExit(f"endpoint id must be a plain name, got {args.endpoint_id!r}")

    policy = json.loads(policy_path().read_text())
    targets = policy["targets"]
    lakebase = targets["lakebase"]
    branch = f"projects/{lakebase['project']}/branches/{lakebase['branch']}"
    database = lakebase.get("database", "databricks_postgres")
    schema = targets["schema_prefix"] + "slice_0"
    endpoint_name = f"{branch}/endpoints/{args.endpoint_id}"

    w = WorkspaceClient()
    endpoint = w.postgres.get_endpoint(endpoint_name)
    if endpoint.parent != branch:
        raise SystemExit(f"endpoint {endpoint.name} is not on the policy branch {branch}")
    token = w.postgres.generate_database_credential(endpoint_name).token
    me = w.current_user.me()
    user = next(e.value for e in me.emails if e.primary)
    creds = {"host": endpoint.status.hosts.host, "dbname": database, "user": user,
             "password": token, "sslmode": "require"}
    with psycopg.connect(**creds) as cn, cn.cursor() as cur:
        cur.execute(
            sql.SQL("DELETE FROM {}.billing_audit_log "
                    "WHERE logged_at < date_trunc('second', (now() AT TIME ZONE 'UTC')) "
                    "- make_interval(days => %s)").format(sql.Identifier(schema)),
            (args.retention_days,))
        print(f"purged {cur.rowcount} audit rows older than {args.retention_days} days "
              f"from {schema}.billing_audit_log on {branch}")
        cn.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
