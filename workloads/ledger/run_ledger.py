"""Run consumption_ledger.sql against SNOWFLAKE.ACCOUNT_USAGE and write the results to output/.

Environment: SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_ROLE, SNOWFLAKE_PRIVATE_KEY_FILE (PKCS8, key-pair
auth), optional SNOWFLAKE_WAREHOUSE (default DEVIN_WH, never a workload warehouse) and SESSION_URL.

    uv run --with snowflake-connector-python==4.8.1 python workloads/ledger/run_ledger.py
"""

import csv
import json
import os
import subprocess
from pathlib import Path

import snowflake.connector
from cryptography.hazmat.primitives import serialization

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
OUTPUTS = ["ledger", "watermarks", "labeling_gaps", "off_warehouse"]
MD_COLUMNS = [
    "CSID",
    "WORKLOAD",
    "STAGE",
    "REGISTRY",
    "DEV_CREDITS",
    "RUNTIME_CREDITS",
    "CORTEX_AI_CREDITS",
    "WAREHOUSE_METERED_CREDITS",
    "DEV_COMMITS",
    "RUNTIME_COMMITS",
]


def head_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True, check=True
    ).stdout.strip()


def connect():
    os.environ.pop("SNOWFLAKE_HOST", None)
    key = serialization.load_pem_private_key(Path(os.environ["SNOWFLAKE_PRIVATE_KEY_FILE"]).read_bytes(), password=None)
    tag = {"purpose": "consumption_ledger", "commit": head_commit()}
    if os.environ.get("SESSION_URL"):
        tag["session_url"] = os.environ["SESSION_URL"]
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        role=os.environ["SNOWFLAKE_ROLE"],
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "DEVIN_WH"),
        private_key=key.private_bytes(
            serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        ),
        authenticator="SNOWFLAKE_JWT",
        application="Devin_Demo",
        session_parameters={"QUERY_TAG": json.dumps(tag, separators=(",", ":"))},
    )


def short(commits) -> str:
    return " ".join(c[:9] for c in (commits or "").split()) or "-"


def write_markdown(ledger, marks) -> None:
    m = dict(zip(marks[0], marks[1][0]))
    lines = [
        "# Consumption ledger",
        "",
        f"Generated {m['GENERATED_AT']} from SNOWFLAKE.ACCOUNT_USAGE, queries since {m['LEDGER_FROM']}.",
        "",
        "| View | Landed through |",
        "|---|---|",
        f"| QUERY_HISTORY | {m['QUERY_HISTORY_THROUGH']} |",
        f"| QUERY_ATTRIBUTION_HISTORY | {m['ATTRIBUTION_THROUGH']} |",
        f"| CORTEX_AI_FUNCTIONS_USAGE_HISTORY (hourly) | {m['CORTEX_AI_THROUGH']} |",
        f"| WAREHOUSE_METERING_HISTORY (closed hours) | {m['METERING_THROUGH']} |",
        f"| SESSIONS | {m['SESSIONS_THROUGH']} |",
        "",
        "| " + " | ".join(c.lower() for c in MD_COLUMNS) + " |",
        "|" + "---|" * len(MD_COLUMNS),
    ]
    cols, rows = ledger
    for row in rows:
        r = dict(zip(cols, row))
        r["DEV_COMMITS"], r["RUNTIME_COMMITS"] = short(r["DEV_COMMITS"]), short(r["RUNTIME_COMMITS"])
        lines.append("| " + " | ".join(str(r[c] if r[c] is not None else "-") for c in MD_COLUMNS) + " |")
    (OUT / "ledger.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    with connect() as conn:
        cursors = conn.execute_string((HERE / "consumption_ledger.sql").read_text())
    results = [([d[0] for d in c.description], c.fetchall()) for c in cursors if c.description][1:]
    for name, (cols, rows) in zip(OUTPUTS, results, strict=True):
        with open(OUT / f"{name}.csv", "w", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow([c.lower() for c in cols])
            w.writerows(rows)
    write_markdown(results[0], results[1])
    print((OUT / "ledger.md").read_text())


if __name__ == "__main__":
    main()
