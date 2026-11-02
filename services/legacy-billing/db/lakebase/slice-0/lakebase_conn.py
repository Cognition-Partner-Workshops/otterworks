"""Connection to the run's Lakebase branch for the migration principal.

The branch, project and database come from .migration/policy.json; the OAuth token is minted per
process with `databricks postgres generate-database-credential` (1 h lifetime) and never written
anywhere. `dsn()` prints a libpq DSN for dbx-recon's LakebaseTargetAdapter, which reads it from
the LAKEBASE_MIGRATION_DSN environment variable of the recon command only.
"""
import json
import subprocess
import sys
from pathlib import Path

import psycopg
from psycopg import conninfo

REPO = Path(__file__).resolve().parents[5]
POLICY = json.loads((REPO / ".migration" / "policy.json").read_text())
LAKEBASE = POLICY["targets"]["lakebase"]
PROJECT, BRANCH = LAKEBASE["project"], LAKEBASE["branch"]
DATABASE = LAKEBASE.get("database", "databricks_postgres")
ENDPOINT = f"projects/{PROJECT}/branches/{BRANCH}/endpoints/primary"
SCHEMA = POLICY["targets"]["schema_prefix"] + "slice_0"


def _cli(*args: str) -> dict:
    return json.loads(subprocess.run(["databricks", *args, "-o", "json"],
                                     check=True, capture_output=True, text=True).stdout)


def creds() -> dict:
    endpoint = _cli("postgres", "get-endpoint", ENDPOINT)
    token = _cli("postgres", "generate-database-credential", ENDPOINT)
    me = _cli("current-user", "me")
    user = next(e["value"] for e in me["emails"] if e.get("primary"))
    return {"host": endpoint["status"]["hosts"]["host"], "dbname": DATABASE, "user": user,
            "password": token["token"], "sslmode": "require"}


def connect() -> psycopg.Connection:
    return psycopg.connect(**creds())


def dsn() -> str:
    return conninfo.make_conninfo(**creds())


if __name__ == "__main__":
    if sys.argv[1:] == ["dsn"]:
        print(dsn())
    else:
        with connect() as cn, cn.cursor() as cur:
            cur.execute("SELECT current_user, current_database()")
            print(cur.fetchone())
