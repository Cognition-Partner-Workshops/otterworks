"""Account-scoped daily storage lookup for support."""

from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import closing
from datetime import date
from pathlib import Path
from uuid import UUID

import snowflake.connector
import yaml
from cryptography.hazmat.primitives import serialization

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "attribution"))
import sf_attribution as sf  # noqa: E402

EP = sf.endpoint("cs_doc_usage_dashboard_support_lookup")
ROLE = "ROLE_CS_DOC_USAGE_DASHBOARD_SUPPORT_LOOKUP"
VIEW = f"{EP.database}.OPS.ACCOUNT_STORAGE_LOOKUP"
SOURCE = "workloads/doc_usage_dashboard/responder/support_lookup.py"
PROVENANCE = Path(__file__).resolve().parents[1] / "provenance.yaml"
COLUMNS = ("snapshot_date, account_id, account_email, tier, quota_bytes, used_bytes, "
           "remaining_bytes, usage_pct, usage_band, active_document_count")


class LookupError(RuntimeError):
    pass


def deployed_revision(path=PROVENANCE):
    doc = yaml.safe_load(Path(path).read_text())
    records = [r for r in doc.get("deployment", {}).get("installed", [])
               if r["type"] == "runtime_source" and r["name"] == SOURCE and r["status"] == "installed"]
    if not records or not sf.COMMIT_RE.fullmatch(records[-1]["revision"]):
        raise LookupError("An installed lookup source revision is required")
    revision = records[-1]["revision"]
    endpoint = next(e for e in doc["endpoints"] if e["csid"] == EP.csid)
    if endpoint.get("runtime_source") != {"path": SOURCE, "revision": revision}:
        raise LookupError("Endpoint runtime source must match the installed revision")
    return revision


def connection_parameters(path=PROVENANCE, env=None):
    env = os.environ if env is None else env
    params = sf.connection_params(
        EP, phase="runtime", account=env["SNOWFLAKE_EXT_ACCOUNT"],
        private_key_file="in-memory-only", commit=deployed_revision(path),
        run_id=sf.make_run_id(EP.workload, "runtime"), role=ROLE, schema="OPS",
    )
    params.pop("private_key_file")
    key = serialization.load_pem_private_key(env["SNOWFLAKE_EXT_SUPPORT_PRIVATE_KEY"].encode(), None)
    params.update(user=env["SNOWFLAKE_EXT_SUPPORT_USER"], private_key=key.private_bytes(
        serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    if params["user"].upper() != EP.service_user:
        raise LookupError("Support service identity required")
    params["session_parameters"].update(DEFAULT_SECONDARY_ROLES="NONE", TIMEZONE="UTC")
    params.update(login_timeout=30, network_timeout=60)
    return params


def lookup_sql(account_id, start_date=None, end_date=None):
    try:
        account_id = str(UUID(account_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("account_id must be a UUID") from exc
    dates = []
    for value in (start_date, end_date):
        if value is None:
            dates.append(None)
        elif isinstance(value, str):
            dates.append(date.fromisoformat(value))
        elif type(value) is date:
            dates.append(value)
        else:
            raise ValueError("Date bounds must be ISO dates")
    start, end = dates
    if start is not None and end is not None and start > end:
        raise ValueError("start_date must not exceed end_date")
    sql = f"SELECT {COLUMNS} FROM {VIEW} WHERE account_id = %s"
    binds = [account_id]
    for operator, value in ((">=", start), ("<=", end)):
        if value is not None:
            sql += f" AND snapshot_date {operator} %s"
            binds.append(value)
    return sql + " ORDER BY snapshot_date", tuple(binds)


def secondary_roles_empty(value):
    value = json.loads(value) if isinstance(value, str) else value
    return isinstance(value, dict) and value.get("roles") in ("", []) and value.get("value") in ("", [])


class Lookup:
    def __init__(self, connection):
        self.connection = connection
        self.output = {"queries": []}

    def query(self, sql, binds=None):
        with self.connection.cursor() as cursor:
            try:
                cursor.execute(sql, binds)
                return [dict(zip([d[0].lower() for d in cursor.description], row))
                        for row in cursor.fetchall()]
            finally:
                self.output["queries"].append({"sql": sql, "binds": binds, "query_id": cursor.sfqid})

    def identify(self):
        self.query("USE SECONDARY ROLES NONE")
        rows = self.query("SELECT CURRENT_USER() AS USER_NAME, CURRENT_ROLE() AS ROLE_NAME, "
                          "CURRENT_SECONDARY_ROLES() AS SECONDARY_ROLES")
        if len(rows) != 1:
            raise LookupError("Missing session identity")
        identity = rows[0]
        self.output["identity"] = identity
        if (identity["user_name"] != EP.service_user or identity["role_name"] != ROLE
                or not secondary_roles_empty(identity["secondary_roles"])):
            raise LookupError("Unexpected identity or nonempty secondary roles")

    def lookup(self, account_id, start_date=None, end_date=None):
        sql, binds = lookup_sql(account_id, start_date, end_date)
        self.identify()
        rows = self.query(sql, binds)
        if any(row["account_id"] != binds[0] for row in rows):
            raise LookupError("Lookup returned another account")
        self.output["rows"] = rows
        return rows


def lookup(account_id, start_date=None, end_date=None, path=PROVENANCE):
    lookup_sql(account_id, start_date, end_date)
    with closing(snowflake.connector.connect(**connection_parameters(path))) as connection:
        client = Lookup(connection)
        client.lookup(account_id, start_date, end_date)
        return client.output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("account_id")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    args = parser.parse_args()
    print(json.dumps(lookup(args.account_id, args.start_date, args.end_date), default=str, indent=2))


if __name__ == "__main__":
    main()
