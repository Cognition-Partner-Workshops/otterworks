"""Run one query on the churn_model RAW.AUTH_USERS table as the reader and as the analyst role, side by side.

Seeds three synthetic example.com rows as the builder, runs the query under each role with
secondary roles off, prints both results next to each other, then deletes the rows.

Env: SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_ROLE (the builder), SNOWFLAKE_PRIVATE_KEY_FILE,
optional SNOWFLAKE_PRIVATE_KEY_FILE_PWD, and SESSION_URL (the Devin session, for the dev QUERY_TAG).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "workloads" / "attribution"))

import sf_attribution as attr  # noqa: E402

TABLE = f"{attr.database_name('churn_model')}.RAW.AUTH_USERS"
QUERY = f"SELECT ID, EMAIL, DISPLAY_NAME FROM {TABLE} WHERE ID LIKE '00000000-0000-4000-8000-%' ORDER BY ID"
ROLES = (attr.role_name("reader"), attr.role_name("analyst"))
SEED = [
    ("00000000-0000-4000-8000-000000000101", "ada@example.com", "Ada"),
    ("00000000-0000-4000-8000-000000000102", "ben@example.com", "Ben"),
    ("00000000-0000-4000-8000-000000000103", "cy@example.com", "Cy"),
]


def _connect():
    import snowflake.connector

    ep = attr.Endpoint.from_csid("cs_churn_model_account_score", "churn_model")
    params = attr.connection_params(
        ep,
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_FILE"],
        private_key_file_pwd=os.environ.get("SNOWFLAKE_PRIVATE_KEY_FILE_PWD"),
        phase="dev",
        commit=attr.current_commit(str(ROOT)),
        run_id=attr.make_run_id("churn_model", "dev"),
        session_url=os.environ["SESSION_URL"],
        role=os.environ["SNOWFLAKE_ROLE"],
        schema="RAW",
    )
    params["user"] = os.environ["SNOWFLAKE_USER"]
    return snowflake.connector.connect(**params)


def _table(rows: list[tuple], width: int) -> list[str]:
    lines = [f"{'ID':<36}  {'EMAIL':<16}  NAME", "-" * width]
    lines += [f"{r[0]:<36}  {r[1]:<16}  {r[2]}" for r in rows]
    return [line.ljust(width) for line in lines]


def main() -> int:
    con = _connect()
    cur = con.cursor()
    try:
        cur.execute("USE SECONDARY ROLES NONE")
        cur.execute(f"DELETE FROM {TABLE} WHERE ID LIKE '00000000-0000-4000-8000-%'")
        cur.executemany(
            f"INSERT INTO {TABLE} (ID, EMAIL, DISPLAY_NAME, EMAIL_VERIFIED, MFA_ENABLED, CREATED_AT, UPDATED_AT) "
            "VALUES (%s, %s, %s, TRUE, FALSE, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP())",
            SEED,
        )
        con.commit()
        results = {}
        for role in ROLES:
            cur.execute(f"USE ROLE {role}")
            cur.execute("USE SECONDARY ROLES NONE")
            cur.execute("SELECT CURRENT_ROLE(), CURRENT_SECONDARY_ROLES()")
            active = cur.fetchone()
            rows = cur.execute(QUERY).fetchall()
            results[role] = (active, rows, cur.sfqid)
        width = 66
        left, right = (_table(results[r][1], width) for r in ROLES)
        print(f"query: {QUERY}\n")
        print(f"{'as ' + ROLES[0]:<{width}}  |  as {ROLES[1]}")
        for role_info in zip(*(results[r][0] for r in ROLES)):
            print(f"{str(role_info[0]):<{width}}  |  {role_info[1]}")
        print()
        for a, b in zip(left, right):
            print(f"{a}  |  {b}")
        print(f"\nquery ids: {ROLES[0]}={results[ROLES[0]][2]}  {ROLES[1]}={results[ROLES[1]][2]}")
    finally:
        cur.execute(f"USE ROLE {os.environ['SNOWFLAKE_ROLE']}")
        cur.execute(f"DELETE FROM {TABLE} WHERE ID LIKE '00000000-0000-4000-8000-%'")
        con.commit()
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
