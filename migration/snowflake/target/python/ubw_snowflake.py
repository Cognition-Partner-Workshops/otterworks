"""Shared connection helpers for the Snowflake migration target."""

from __future__ import annotations

import os
import re

import snowflake.connector
from cryptography.hazmat.primitives import serialization

RUN_PATTERN = re.compile(r"^sfm-\d{8}-[a-z0-9]{2,8}$")


def validate_run(run: str) -> str:
    if not RUN_PATTERN.fullmatch(run):
        raise ValueError(f"run token {run!r} does not look like sfm-<yyyymmdd>-<suffix>")
    return run


def object_prefix(run: str) -> str:
    validate_run(run)
    return "OW_UBW_" + run.upper().replace("-", "_")


def normalise_pem(pem: str) -> bytes:
    body = re.sub(r"-----(BEGIN|END) PRIVATE KEY-----", "", pem)
    body = "".join(body.split())
    lines = [body[index : index + 64] for index in range(0, len(body), 64)]
    header = "-----BEGIN PRIVATE KEY-----"  # gitleaks:allow
    footer = "-----END PRIVATE KEY-----"
    pem_text = "\n".join([header, *lines, footer])
    return (pem_text + "\n").encode()


def dbt_connection(run: str) -> snowflake.connector.SnowflakeConnection:
    prefix = object_prefix(run)
    private_pem = os.environ.get("SNOWFLAKE_PRIVATE_KEY") or os.environ.get(
        "UBW_DBT_PRIVATE_KEY", ""
    )
    if not private_pem:
        raise RuntimeError("SNOWFLAKE_PRIVATE_KEY is not set")
    key = serialization.load_pem_private_key(normalise_pem(private_pem), password=None)
    private_key = key.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    params: dict[str, object] = {
        "account": os.environ.get("SNOWFLAKE_ACCOUNT", ""),
        "user": os.environ.get("UBW_DBT_USER", f"{prefix}_DBT"),
        "private_key": private_key,
        "role": f"{prefix}_ENGINEER",
        "warehouse": f"{prefix}_WH",
        "database": prefix,
        "schema": "OPS",
    }
    if not params["account"]:
        raise RuntimeError("SNOWFLAKE_ACCOUNT is not set")
    if os.environ.get("SNOWFLAKE_HOST"):
        params["host"] = os.environ["SNOWFLAKE_HOST"]
    return snowflake.connector.connect(**params)
