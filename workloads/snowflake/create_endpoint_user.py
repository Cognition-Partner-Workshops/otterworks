"""Create or rotate the key-pair service user for the doc search insights endpoint."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workloads/attribution"))
import sf_attribution as attr  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-key-file", type=Path, required=True)
    args = parser.parse_args(argv)

    endpoint = attr.Endpoint.from_csid("cs_doc_search_api_top_items", "doc_search_api")
    os.environ.pop("SNOWFLAKE_HOST", None)
    params = attr.connection_params(
        endpoint,
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_FILE"],
        phase="dev",
        commit=attr.current_commit(str(ROOT)),
        run_id=attr.make_run_id("doc_search_api", "dev"),
        session_url=os.environ["SESSION_URL"],
        role=os.environ["SNOWFLAKE_ROLE"],
    )
    params["user"] = os.environ["SNOWFLAKE_USER"]

    import snowflake.connector

    public_key = args.public_key_file.read_text(encoding="utf-8")
    key_body = "".join(
        line.strip()
        for line in public_key.strip().splitlines()
        if not line.startswith("-----")
    )
    with snowflake.connector.connect(**params) as connection:
        cursor = connection.cursor()
        try:
            cursor.execute("USE SECONDARY ROLES NONE")
            cursor.execute(
                attr.service_user_ddl(
                    endpoint,
                    rsa_public_key=public_key,
                    role=attr.role_name("reader"),
                )
            )
            cursor.execute(
                f"ALTER USER {endpoint.service_user} SET RSA_PUBLIC_KEY = "
                f"{attr.sql_string(key_body)}"
            )
            cursor.execute(f"ALTER USER {endpoint.service_user} SET DEFAULT_SECONDARY_ROLES = ()")
            cursor.execute(f"GRANT ROLE {attr.role_name('reader')} TO USER {endpoint.service_user}")
            cursor.execute(f"SHOW USERS LIKE {attr.sql_string(endpoint.service_user)}")
            columns = []
            for column in cursor.description:
                name = getattr(column, "name", None)
                columns.append((name if name is not None else column[0]).lower())
            for row in cursor.fetchall():
                user = dict(zip(columns, row))
                print(
                    {
                        field: user.get(field)
                        for field in (
                            "name",
                            "type",
                            "default_role",
                            "default_warehouse",
                            "has_rsa_public_key",
                            "has_password",
                        )
                    }
                )
        finally:
            cursor.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
