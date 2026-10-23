"""Create, tear down or check the Snowflake objects for one fixture run.

The builder credentials (a programmatic access token for an ACCOUNTADMIN user) are used
here and in the teardown only; dbt, the loader and the gate log in as the run's DBT user.
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import os
import re
import secrets
import string
import sys
from pathlib import Path

import snowflake.connector
from cryptography.hazmat.primitives import serialization
from snowflake.connector.util_text import split_statements

HERE = Path(__file__).resolve().parent
RUN_PATTERN = re.compile(r"^sfm-(\d{8})-[a-z0-9]{2,8}$")
DEFAULT_TTL_DAYS = 14
CREATE_PATTERN = re.compile(
    r"^CREATE\s+(?:OR\s+REPLACE\s+)?"
    r"(DATABASE|SCHEMA|WAREHOUSE|RESOURCE\s+MONITOR|AUTHENTICATION\s+POLICY|ROLE|USER|TAG)\s+"
    r"(?:IF\s+NOT\s+EXISTS\s+)?([\w.$]+)",
    re.IGNORECASE,
)


def object_prefix(run: str) -> str:
    return "OW_UBW_" + run.upper().replace("-", "_")


def default_expiry(run: str) -> str:
    match = RUN_PATTERN.match(run)
    if not match:
        raise SystemExit(f"run token {run!r} does not look like sfm-<yyyymmdd>-<suffix>")
    started = dt.datetime.strptime(match.group(1), "%Y%m%d").date()
    return (started + dt.timedelta(days=DEFAULT_TTL_DAYS)).isoformat()


def normalise_pem(pem: str) -> bytes:
    # Secret stores often flatten the PEM onto one line with spaces where newlines were.
    body = re.sub(r"-----(BEGIN|END) PRIVATE KEY-----", "", pem)
    body = "".join(body.split())
    lines = [body[i : i + 64] for i in range(0, len(body), 64)]
    header = "-----BEGIN PRIVATE KEY-----"  # gitleaks:allow
    footer = "-----END PRIVATE KEY-----"
    pem_text = "\n".join([header, *lines, footer])
    return (pem_text + "\n").encode()


def public_key_body(private_pem: str) -> str:
    key = serialization.load_pem_private_key(normalise_pem(private_pem), password=None)
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return "".join(line for line in public.decode().splitlines() if "-----" not in line)


def random_password() -> str:
    alphabet = string.ascii_letters + string.digits
    core = "".join(secrets.choice(alphabet) for _ in range(28))
    return "Ow7" + core


def require_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"{name} is not set")
    return value


def admin_connection() -> snowflake.connector.SnowflakeConnection:
    params = {
        "account": require_env("SNOWFLAKE_ACCOUNT"),
        "user": require_env("SNOWFLAKE_USER"),
        "authenticator": "PROGRAMMATIC_ACCESS_TOKEN",
        "token": require_env("SNOWFLAKE_PAT"),
        "role": "ACCOUNTADMIN",
    }
    if os.environ.get("SNOWFLAKE_HOST"):
        params["host"] = os.environ["SNOWFLAKE_HOST"]
    return snowflake.connector.connect(**params)


def render(sql_file: str, values: dict[str, str]) -> list[str]:
    text = string.Template((HERE / sql_file).read_text()).substitute(values)
    statements = []
    for statement, _ in split_statements(io.StringIO(text), remove_comments=True):
        statement = statement.strip().rstrip(";").strip()
        if statement:
            statements.append(statement)
    return statements


def token_values(run: str, expires: str) -> dict[str, str]:
    return {"RUN": run, "PREFIX": object_prefix(run), "EXPIRES": expires}


def is_unchanged_password_error(error: snowflake.connector.errors.ProgrammingError) -> bool:
    return error.errno == 3002 and "same password" in str(error).lower()


def current_authentication_policy(
    cur: snowflake.connector.cursor.SnowflakeCursor, user: str
) -> str:
    cur.execute(
        "SELECT POLICY_DB, POLICY_SCHEMA, POLICY_NAME, REF_ENTITY_NAME, "
        "REF_ENTITY_DOMAIN, POLICY_STATUS "
        "FROM TABLE(OW_UBW.INFORMATION_SCHEMA.POLICY_REFERENCES("
        "REF_ENTITY_NAME => %s, REF_ENTITY_DOMAIN => 'USER'))",
        (user,),
    )
    columns = [column[0].lower() for column in cur.description or []]
    for row in cur.fetchall():
        reference = dict(zip(columns, row, strict=True))
        if (
            str(reference.get("ref_entity_name", "")).upper() == user.upper()
            and str(reference.get("ref_entity_domain", "")).upper() == "USER"
            and str(reference.get("policy_status", "")).upper() == "ACTIVE"
        ):
            return ".".join(
                str(reference[column]) for column in ("policy_db", "policy_schema", "policy_name")
            )
    return ""


def run_up(run: str, expires: str, credit_quota: int) -> None:
    requested_viewer_password = os.environ.get("UBW_VIEWER_PASSWORD")
    viewer_password = requested_viewer_password or random_password()
    values = token_values(run, expires) | {
        "CREDIT_QUOTA": str(credit_quota),
        "DBT_PUBLIC_KEY": public_key_body(require_env("SNOWFLAKE_PRIVATE_KEY")),
        "VIEWER_PASSWORD": viewer_password.replace("'", "''"),
    }
    prefix = values["PREFIX"]
    with admin_connection() as conn, conn.cursor() as cur:
        viewer_created = False
        for statement in render("account.sql", values):
            cur.execute(statement)
            match = CREATE_PATTERN.match(statement)
            if match:
                kind = " ".join(match.group(1).upper().split())
                result = cur.fetchone()
                status = str(result[0]) if result else "created"
                print(f"{kind:<23} {match.group(2)}  ({status})")
                if (
                    kind == "USER"
                    and match.group(2).upper() == f"{prefix}_VIEWER"
                    and "created" in status.lower()
                    and "already exists" not in status.lower()
                ):
                    viewer_created = True
        if requested_viewer_password:
            if viewer_created:
                print(f"{'PASSWORD':<23} {prefix}_VIEWER  (set during CREATE)")
            else:
                try:
                    cur.execute(
                        f"ALTER USER {prefix}_VIEWER SET PASSWORD = %s "
                        "MUST_CHANGE_PASSWORD = FALSE",
                        (viewer_password,),
                    )
                except snowflake.connector.errors.ProgrammingError as error:
                    if not is_unchanged_password_error(error):
                        raise
                    print(f"{'PASSWORD':<23} {prefix}_VIEWER  (already set)")
                else:
                    print(f"{'PASSWORD':<23} {prefix}_VIEWER  (set from UBW_VIEWER_PASSWORD)")

        policy_name = "OW_UBW.TAGS.OW_UBW_VIEWER_AUTH"
        current_policy = current_authentication_policy(cur, f"{prefix}_VIEWER")
        if current_policy.upper() == policy_name:
            print(f"{'AUTHENTICATION POLICY':<23} {prefix}_VIEWER  (already attached)")
        else:
            if current_policy:
                cur.execute(f"ALTER USER {prefix}_VIEWER UNSET AUTHENTICATION POLICY")  # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
            cur.execute(f"ALTER USER {prefix}_VIEWER SET AUTHENTICATION POLICY {policy_name}")  # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
            print(f"{'AUTHENTICATION POLICY':<23} {prefix}_VIEWER  (attached {policy_name})")
    print(f"Bootstrap done for {run}: database {prefix}, warehouse {prefix}_WH, expires {expires}")


def run_teardown(run: str) -> None:
    with admin_connection() as conn, conn.cursor() as cur:
        for statement in render("teardown.sql", token_values(run, "")):
            cur.execute(statement)
            print(f"{statement}  ({cur.fetchone()[0]})")


def run_verify_clean(run: str) -> int:
    prefix = object_prefix(run)
    found: list[str] = []
    with admin_connection() as conn, conn.cursor() as cur:
        for statement in render("verify_clean.sql", token_values(run, "")):
            cur.execute(statement)
            columns = [c[0].lower() for c in cur.description]
            for row in cur.fetchall():
                record = dict(zip(columns, row, strict=True))
                if statement.upper().startswith("SHOW"):
                    kind = statement.split()[1].rstrip("S").replace("RESOURCE", "RESOURCE MONITOR")
                    if not str(record["name"]).upper().startswith(prefix):
                        continue
                    found.append(f"{kind:<17} {record['name']}  (by name)")
                else:
                    target = ".".join(
                        str(record[k])
                        for k in ("object_database", "object_schema", "object_name")
                        if record.get(k)
                    )
                    tag = f"tag RUN={record['tag_value']}"
                    found.append(f"{record['domain']:<17} {target}  ({tag})")
    for line in found:
        print(line)
    print(f"verify-clean {run}: {len(found)} object(s) still carry the token")
    return 1 if found else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["up", "teardown", "verify-clean"])
    parser.add_argument("--run", required=True, help="run token, e.g. sfm-20261012-bd")
    parser.add_argument("--expires", help="yyyy-mm-dd; defaults to 14 days after the token date")
    parser.add_argument("--credit-quota", type=int, default=5)
    args = parser.parse_args()
    expires = args.expires or default_expiry(args.run)
    if args.action == "up":
        run_up(args.run, expires, args.credit_quota)
        return 0
    if args.action == "teardown":
        run_teardown(args.run)
        return 0
    return run_verify_clean(args.run)


if __name__ == "__main__":
    sys.exit(main())
