"""In-memory endpoint credentials and least-privilege provisioning."""

import argparse
import os
import sys
from contextlib import contextmanager
from pathlib import Path

import snowflake.connector
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "attribution"))
import sf_attribution as sf  # noqa: E402

EP = sf.endpoint("cs_churn_model_account_score")
ROLE = "SFEXT_20261105A_CHURN_MODEL_ENDPOINT"
SESSION_URL = "https://partner-workshops.devinenterprise.com/sessions/22bbda4bc8b843b79118a3ea20cf7854"
RAW = {"AUTH_USERS": "ID", "AUTH_USER_STATE_HISTORY": "ID", "ADMIN_USER_STATE_HISTORY": "ID",
       "ADMIN_STORAGE_QUOTAS": "USER_ID", "DOCUMENT_DOCUMENT_VERSIONS": "ID",
       "ANALYTICS_ANALYTICS_EVENTS": "EVENT_ID"}
OUTPUTS = ("CHURN_MODEL_RUNS", "CHURN_MODEL_EVALUATION", "CHURN_MODEL_SCORES",
           "CHURN_RISK_REASONS", "CHURN_LEAKAGE_CHECK", "CHURN_DOCUMENT_LABELS")


def params(key, run_id, commit, role=ROLE):
    result = sf.connection_params(EP, phase="dev", account=os.environ["SNOWFLAKE_EXT_ACCOUNT"],
                                  private_key_file="in-memory-only", commit=commit, run_id=run_id,
                                  session_url=SESSION_URL, role=role)
    result.pop("private_key_file")
    result["private_key"] = key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                                             serialization.NoEncryption())
    return result


def admin_connection(run_id=None, commit=None):
    key = serialization.load_pem_private_key(os.environ["SNOWFLAKE_EXT_PRIVATE_KEY"].encode(), password=None)
    result = params(key, run_id or sf.make_run_id(EP.workload, "dev"), commit or sf.resolve_commit(), "DEVIN_EXT_ROLE")
    result["user"] = os.environ["SNOWFLAKE_EXT_USER"]
    return snowflake.connector.connect(**result)


def provision_sql(public_key):
    comment = sf.sql_string(sf.external_comment(workload=EP.workload, csid=EP.csid))
    statements = [f"CREATE ROLE IF NOT EXISTS {ROLE} COMMENT = {comment}",
                  f"GRANT USAGE ON WAREHOUSE {EP.warehouse} TO ROLE {ROLE}",
                  f"GRANT USAGE ON DATABASE {EP.database} TO ROLE {ROLE}"]
    for schema in ("RAW", "APP"):
        statements.append(f"GRANT USAGE ON SCHEMA {EP.database}.{schema} TO ROLE {ROLE}")
    for table in (*RAW, "PIPELINE_EXPORTS", "SUPPORT_NOTES", "DOCUMENT_DOCUMENTS"):
        statements.append(f"GRANT SELECT ON TABLE {EP.database}.RAW.{table} TO ROLE {ROLE}")
    for table in OUTPUTS:
        statements.append(f"GRANT SELECT, INSERT ON TABLE {EP.database}.APP.{table} TO ROLE {ROLE}")
    statements += [f"GRANT CREATE PROCEDURE, CREATE TABLE, CREATE STAGE ON SCHEMA {EP.database}.APP TO ROLE {ROLE}",
                   f"GRANT CREATE SNOWFLAKE.ML.CLASSIFICATION ON SCHEMA {EP.database}.APP TO ROLE {ROLE}",
                   f"GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE {ROLE}",
                   sf.service_user_ddl(EP, rsa_public_key=public_key, role=ROLE),
                   f"ALTER USER {EP.service_user} SET RSA_PUBLIC_KEY = {sf.sql_string(public_key)} DEFAULT_ROLE = {ROLE}",
                   f"GRANT ROLE {ROLE} TO USER {EP.service_user}"]
    return statements


def unset(conn):
    with conn.cursor() as cursor:
        cursor.execute(f"ALTER USER {EP.service_user} UNSET RSA_PUBLIC_KEY")


@contextmanager
def service_connection(run_id, commit):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    public = "".join(line for line in public.splitlines() if not line.startswith("-----"))
    with admin_connection(run_id, commit) as admin:
        try:
            with admin.cursor() as cursor:
                for statement in provision_sql(public):
                    cursor.execute(statement)
            with snowflake.connector.connect(**params(key, run_id, commit)) as connection:
                yield connection
        finally:
            unset(admin)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unset-key", action="store_true")
    args = parser.parse_args()
    if args.unset_key:
        with admin_connection() as connection:
            unset(connection)
    else:
        with service_connection(sf.make_run_id(EP.workload, "dev"), sf.resolve_commit()):
            print("Endpoint provisioned; ephemeral RSA key removed.")


if __name__ == "__main__":
    main()
