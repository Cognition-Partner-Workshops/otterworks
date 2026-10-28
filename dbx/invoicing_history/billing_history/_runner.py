#!/usr/bin/env python3
"""billing_history ddl+load executor (imported by run.py).

Connects through databricks-sql-connector on the session identity (oauth-m2m SP):
the connector mints no client_credentials token itself on this version, so the
service-principal token comes from the SDK — the same path the recon harness's
_databricks_bearer() takes. Warehouse: the engagement's serverless warehouse
565cd2fd713738c4 (plan.yaml target-sql); --http-path overrides.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent


def connect(http_path: str | None = None):
    import databricks.sdk.core as sdk_core
    from databricks import sql

    host = os.environ["DATABRICKS_HOST"].removeprefix("https://").removeprefix("http://").rstrip("/")
    cfg = sdk_core.Config()
    token = cfg.authenticate()["Authorization"].split(" ", 1)[1]
    return sql.connect(server_hostname=host,
                       http_path=http_path or os.environ["DATABRICKS_HTTP_PATH"],
                       access_token=token)


def statements(path: Path) -> list[str]:
    text = "\n".join(line for line in path.read_text().splitlines() if not line.lstrip().startswith("--"))
    return [chunk.strip() for chunk in text.split(";") if chunk.strip()]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--http-path", default="/sql/1.0/warehouses/565cd2fd713738c4")
    p.add_argument("--ddl-only", action="store_true", help="run sql/ddl.sql only (no load)")
    p.add_argument("--exec-schema", help="run against schema <name>_exec (routine-parity run)")
    p.add_argument("--probe-grants", action="store_true", help="read-only grant visibility probe")
    p.add_argument("--routine-runs", metavar="DIR",
                   help="write routine-parity run records (fixture golden vs exec-schema observed)")
    args = p.parse_args()
    conn = connect(args.http_path)
    if args.routine_runs:
        import base64
        import json

        import pandas as pd

        def cell(v):
            import datetime
            import decimal
            if v is None or (not isinstance(v, (str, bytes)) and pd.isna(v)):
                return None
            if isinstance(v, decimal.Decimal):
                return str(v)
            if isinstance(v, (datetime.datetime, datetime.date)):
                if isinstance(v, datetime.datetime):
                    v = v.replace(microsecond=(v.microsecond // 1000) * 1000)
                return v.isoformat()
            if isinstance(v, bytes):
                return base64.b64encode(v).decode()
            if isinstance(v, float):
                return int(v) if v.is_integer() else repr(v)
            if isinstance(v, str):
                return v.rstrip()
            return v

        out = Path(args.routine_runs)
        out.mkdir(parents=True, exist_ok=True)
        for t in ("customer_master", "customer_master_hist", "entity_attr_value",
                  "invoice_header", "invoice_line"):
            routine = f"snapshot.{t}"
            golden = [
                {c: cell(r[c]) for c in df.columns}
                for df in [pd.read_parquet(HERE / "extract" / "fixture" / f"{t}.parquet")]
                for r in df.to_dict("records")
            ]
            with conn.cursor() as cur:
                cur.execute(f"SELECT * FROM ow_tp.billing_history_exec.{t}")
                cols = [d[0] for d in cur.description]
                observed = [{c: cell(v) for c, v in zip(cols, row)} for row in cur.fetchall()]
            # observed rows are keyed lower-case by UC; golden columns are parquet's case —
            # lower-case both so one record compares row sets, not casing.
            canon = lambda rows: [{k.lower(): v for k, v in r.items()} for r in rows]  # noqa: E731
            record = {
                "routine": routine,
                "target_family": "databricks",
                "target_branch": "ow_tp.billing_history_exec",
                "snapshot": f"fixture:dbx/invoicing_history/billing_history/extract/fixture/{t}.parquet",
                "evidence": f"{out.as_posix()}/{routine.replace('.', '_')}.run.json",
                "golden": {f"ow_billing.{t}": canon(golden)},
                "observed": {f"ow_billing.{t}": canon(observed)},
            }
            dest = out / f"{routine.replace('.', '_')}.run.json"
            dest.write_text(json.dumps(record))
            print(f"{routine}: golden={len(golden)} observed={len(observed)} -> {dest}", flush=True)
        conn.close()
        return 0
    if args.probe_grants:
        with conn.cursor() as cur:
            for stmt in (Path(HERE / "sql" / "probe_grants.sql").read_text().split(";")):
                stmt = stmt.strip()
                if stmt:
                    try:
                        cur.execute(stmt)
                        print(stmt.splitlines()[0][:60], "->", cur.fetchall()[:3], flush=True)
                    except Exception as exc:  # noqa: BLE001 - probe reports the error
                        print(stmt.splitlines()[0][:60], "->", type(exc).__name__, str(exc)[:160])
        conn.close()
        return 0
    files = ["sql/ddl.sql"] if args.ddl_only else ["sql/ddl.sql", "sql/load.sql"]
    target_schema = "ow_tp.ow_tp_invoicing_history"
    if args.exec_schema:
        target_schema = f"ow_tp.{args.exec_schema}"
    with conn.cursor() as cur:
        for name in files:
            for stmt in statements(HERE / name):
                if args.exec_schema:
                    stmt = stmt.replace("ow_tp.ow_tp_invoicing_history", target_schema)
                cur.execute(stmt)
                print(f"{name}: {' '.join(stmt.split()[:4])} -> ok", flush=True)
        for t in ("customer_master", "customer_master_hist", "entity_attr_value",
                  "invoice_header", "invoice_line"):
            cur.execute(f"SELECT count(*) FROM {target_schema}.{t}")
            print(f"rows in {target_schema}.{t}: {cur.fetchone()[0]}", flush=True)
    conn.close()
    return 0
