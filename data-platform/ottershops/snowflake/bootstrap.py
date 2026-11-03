"""Apply bootstrap.sql with an admin PAT and register the service user's public key.

Usage: SNOWFLAKE_ACCOUNT=... SNOWFLAKE_ADMIN_USER=... SNOWFLAKE_PAT=... \
       python bootstrap.py path/to/svc_key.pub
"""
import os
import pathlib
import sys

import snowflake.connector

here = pathlib.Path(__file__).parent
pub = "".join(l for l in pathlib.Path(sys.argv[1]).read_text().splitlines() if "-----" not in l)

conn = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_ADMIN_USER"],
    authenticator="PROGRAMMATIC_ACCESS_TOKEN",
    token=os.environ["SNOWFLAKE_PAT"],
)
for cur in conn.execute_string((here / "bootstrap.sql").read_text()):
    pass
conn.cursor().execute(f"ALTER USER OTTERSHOPS_SVC SET RSA_PUBLIC_KEY = '{pub}'")
print("bootstrap complete")
