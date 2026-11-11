#!/usr/bin/env python3
"""Export the nightly report with key-pair authentication."""
from datetime import date
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
QUERY_TAG = '{"run":"sfx-d1110","act":"consumers","consumer":"partner-extract"}'


def connect():
    required = ("ACCOUNT", "USER", "ROLE", "PRIVATE_KEY")
    for key in required:
        if not os.environ.get("SNOWFLAKE_" + key):
            raise ValueError("missing SNOWFLAKE_" + key)
    import snowflake.connector
    from cryptography.hazmat.primitives import serialization

    key = serialization.load_pem_private_key(
        os.environ["SNOWFLAKE_PRIVATE_KEY"].encode(), password=None
    )
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        role=os.environ["SNOWFLAKE_ROLE"],
        warehouse="SFX_D1110_PARITY_WH",
        private_key=key.private_bytes(
            serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
        database="SFX_D1110_AFTER", schema="COMPAT",
        authenticator="SNOWFLAKE_JWT", paramstyle="pyformat",
        session_parameters={"QUERY_TAG": QUERY_TAG, "TIMEZONE": "UTC"},
    )


def query(cursor, sql, params=None):
    try:
        cursor.execute(sql, params)
    finally:
        if cursor.sfqid:
            print(f"snowflake query_id={cursor.sfqid}", file=sys.stderr)


def main():
    if len(sys.argv) != 3:
        raise ValueError("usage: snowflake_export.py YYYY-MM-DD export_file")
    extract_date = sys.argv[1]
    if date.fromisoformat(extract_date).isoformat() != extract_date:
        raise ValueError("extract date must be YYYY-MM-DD")
    with connect() as connection, connection.cursor() as cursor:
        query(cursor, (ROOT / "sql/partner_invoice_extract.sql").read_text(),
              {"extract_date": extract_date})
        if [column[0] for column in cursor.description] != ["REPORT_ROW"]:
            raise ValueError("expected exactly one column REPORT_ROW")
        with open(sys.argv[2], "w", encoding="utf-8", newline="") as destination:
            for row in cursor:
                if len(row) != 1 or not isinstance(row[0], str) or "\n" in row[0] or "\r" in row[0]:
                    raise ValueError("invalid REPORT_ROW")
                destination.write(row[0] + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"warehouse export failed: {error}", file=sys.stderr)
        sys.exit(1)
