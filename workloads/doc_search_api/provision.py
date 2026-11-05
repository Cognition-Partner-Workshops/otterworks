"""Provision the least-privilege search endpoint identity."""

import argparse
import os
import sys
from pathlib import Path

import snowflake.connector
from cryptography.hazmat.primitives import serialization

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "attribution"))
import sf_attribution as sf  # noqa: E402

EP = sf.endpoint("cs_doc_search_api_top_items")
ROLE = f"{sf.RUN_TOKEN}_DOC_SEARCH_API_ENDPOINT"


def provision_sql(public_key):
    comment = sf.sql_string(sf.external_comment(workload=EP.workload, csid=EP.csid))
    body = "".join(line.strip() for line in public_key.splitlines() if not line.startswith("-----"))
    return [
        f"CREATE ROLE IF NOT EXISTS {ROLE} COMMENT = {comment}",
        f"GRANT USAGE ON WAREHOUSE {EP.warehouse} TO ROLE {ROLE}",
        f"GRANT USAGE ON DATABASE {EP.database} TO ROLE {ROLE}",
        f"GRANT USAGE ON SCHEMA {EP.database}.APP TO ROLE {ROLE}",
        f"GRANT SELECT ON TABLE {EP.database}.APP.TOP_SEARCH_ITEMS TO ROLE {ROLE}",
        sf.service_user_ddl(EP, rsa_public_key=public_key, role=ROLE),
        f"ALTER USER {EP.service_user} SET RSA_PUBLIC_KEY = {sf.sql_string(body)} DEFAULT_ROLE = {ROLE}",
        f"GRANT ROLE {ROLE} TO USER {EP.service_user}",
    ]


def admin_connection():
    params = sf.connection_params(
        EP, phase="dev", account=os.environ["SNOWFLAKE_EXT_ACCOUNT"],
        private_key_file="in-memory-only", commit=sf.resolve_commit(),
        run_id=sf.make_run_id(EP.workload, "dev"),
        session_url=os.environ["DEVIN_SESSION_URL"], role="DEVIN_EXT_ROLE",
    )
    params.pop("private_key_file")
    key = serialization.load_pem_private_key(os.environ["SNOWFLAKE_EXT_PRIVATE_KEY"].encode(), password=None)
    params["private_key"] = key.private_bytes(
        serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption(),
    )
    params["user"] = os.environ["SNOWFLAKE_EXT_USER"]
    return snowflake.connector.connect(**params)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-key", required=True)
    args = parser.parse_args()
    with admin_connection() as conn, conn.cursor() as cur:
        for statement in provision_sql(Path(args.public_key).read_text()):
            cur.execute(statement)


if __name__ == "__main__":
    main()
