"""Validate seed inputs before invoking the unmodified PowerCenter runner.

Run with etl/informatica/.venv/bin/python and the documented dbx/TD environment.
Local rows and API responses stay in ignored local-evidence/.
"""
import csv
import datetime
import hashlib
import json
import os
import subprocess
import sys

import psycopg

from dbx import EVIDENCE, ROOT, rows, sql

REPO = ROOT.parents[3]
USER = ["user_id", "display_name", "email", "status_cd", "created_dt"]
DOC = ["document_id", "folder_id", "owner_user_id", "customer_id", "document_name", "created_dt", "status_cd", "file_type"]
SHARE = ["share_id", "document_id", "user_id", "access_level", "shared_dt"]
ROLE = ["grant_id", "user_id", "role_cd", "granted_dt"]
MAPS = {
    "m_SFX_STG_APP_USER": ("users__stg_app_user", USER),
    "m_SFX_APP_USER": ("users__app_user", USER),
    "m_SFX_STG_DOCUMENT": ("documents__stg_document", DOC),
    "m_SFX_DOCUMENT": ("documents__document", DOC),
    "m_SFX_DOC_SHARE": ("documents__doc_share", SHARE),
}


def canonical(v):
    if v is None:
        return "<NULL>"
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()
    return str(v)


def signature(data):
    data = [[canonical(v) for v in r] for r in data]
    return {"count": len(data), "hash": str(sum(int(hashlib.md5("|".join(r).encode()).hexdigest()[:15], 16) for r in data))}


def projection(table, cols):
    # PostgreSQL CHAR(n) becomes a padded STRING in the live Delta baseline.
    # Only the original CHAR columns are stripped, just as _rtrim_char does.
    chars = {"users__app_user": {"status_cd"}, "users__role_grant": {"role_cd"},
             "documents__document": {"status_cd", "file_type"}, "documents__doc_share": {"access_level"}}
    return [f"rtrim({c})" if c in chars.get(table.split('.')[-1], set()) else c for c in cols]


def aggregate(table, cols):
    canon = ",".join(f"coalesce(cast({c} as string),'<NULL>')" for c in projection(table, cols))
    return f"SELECT count(*) AS count, coalesce(sum(cast(conv(substr(md5(concat_ws('|',{canon})),1,15),16,10) AS DECIMAL(38,0))),0) AS hash FROM {table}"


def pg_rows(conn, target, cols):
    area, name = target.split("__")
    with conn.cursor() as c:
        c.execute(f"SELECT {','.join(cols)} FROM sfx_{area}.{name}")
        pad = [i for i, d in enumerate(c.description) if d.type_code == 1042]
        out = c.fetchall()
    return [[v.rstrip(' ') if i in pad and v is not None else v for i, v in enumerate(r)] for r in out]


def input_checks(conn):
    checks = {}
    tables = [("users__stg_app_user", USER), ("users__app_user", USER),
              ("users__role_grant", ROLE), ("documents__stg_document", DOC),
              ("documents__document", DOC), ("documents__stg_doc_share", SHARE),
              ("documents__doc_share", SHARE)]
    for table, cols in tables:
        local = pg_rows(conn, table, cols)
        r = sql(aggregate("cpw.dbx_d1111_before." + table, cols), "SFX_CONTENT", "input-equality", table)
        live = rows(r)[0]
        expected = signature(local)
        equal = str(expected["count"]) == live["count"] and expected["hash"] == live["hash"]
        checks[table] = {"local": expected, "live": live, "equal": equal, "statement_id": r["statement_id"]}
        print(table, checks[table], flush=True)
    # Flat files are the true source for staging and DOC_SHARE. Compare exactly the
    # columns the XML reads (DOCUMENT's eighth FILE_TYPE field is unconnected).
    for table, cols, area, feed in [
        ("users__stg_app_user", USER, "users", "APP_USER"),
        ("documents__stg_document", DOC, "documents", "DOCUMENT"),
        ("documents__stg_doc_share", SHARE, "documents", "DOC_SHARE")]:
        with (REPO / f"warehouse/landing/{area}/{feed}/20261109.psv").open() as f:
            local = [[None if v == '' else v for v in r[:len(cols)]] for r in csv.reader(f, delimiter='|', quoting=csv.QUOTE_NONE)]
        expected = signature(local)
        checks[feed + "_flatfile"] = {"local": expected, "live": checks[table]["live"],
            "equal": expected["hash"] == checks[table]["live"]["hash"] and str(expected["count"]) == checks[table]["live"]["count"],
            "statement_id": checks[table]["statement_id"]}
        print(feed, checks[feed + "_flatfile"], flush=True)
    (EVIDENCE / "inputs.json").write_text(json.dumps(checks, indent=2))
    return checks


def oracle(conn):
    env = {**os.environ, "LANDING_DIR": str(REPO / "warehouse/landing"),
           "PMROOTDIR": str(REPO / "etl/informatica/infa_shared/dbx-d1111-documents")}
    outcomes = {}
    for mapping, (target, cols) in MAPS.items():
        # Validate each mapping against the frozen live inputs, independently of
        # upstream staging transformations. Workflow chaining is tested separately.
        restore_inputs(conn)
        proc = subprocess.run([str(REPO / "etl/informatica/.venv/bin/python"), "-m", "runner",
            "startsession", "-f", "SFX_CONTENT", "-w", "wf_SFX_CONTENT_DAILY", "s_" + mapping],
            cwd=REPO / "etl/informatica", env=env, capture_output=True, text=True)
        (EVIDENCE / (mapping + ".log")).write_text(proc.stdout + proc.stderr)
        data = pg_rows(conn, target, cols)
        outcomes[mapping] = {"returncode": proc.returncode, "target": target,
            "signature": signature(data), "last_line": proc.stdout.strip().splitlines()[-1:]}
        (EVIDENCE / (mapping + "_rows.json")).write_text(json.dumps(data, default=canonical))
        print(mapping, outcomes[mapping], flush=True)
    (EVIDENCE / "oracle.json").write_text(json.dumps(outcomes, indent=2))


def restore_inputs(conn):
    for area, feed, table in [("users", "APP_USER", "stg_app_user"),
                              ("documents", "DOCUMENT", "stg_document")]:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM sfx_{area}.{table}")
            with cur.copy(f"COPY sfx_{area}.{table} FROM STDIN WITH (FORMAT csv, DELIMITER '|', QUOTE E'\\x01', NULL '')") as cp:
                cp.write((REPO / f"warehouse/landing/{area}/{feed}/20261109.psv").read_text())
    with conn.cursor() as cur:
        cur.execute("DELETE FROM sfx_documents.doc_share")
        cur.execute("INSERT INTO sfx_documents.doc_share SELECT * FROM sfx_documents.stg_doc_share")


if __name__ == "__main__":
    EVIDENCE.mkdir(exist_ok=True)
    with psycopg.connect(host="127.0.0.1", port=os.environ["TD_PORT"], dbname="teradata", user="postgres", autocommit=True) as conn:
        restore_inputs(conn)
        checks = input_checks(conn)
        if not all(x["equal"] for x in checks.values()):
            sys.exit("Input equality failed; runner has not been invoked.")
        oracle(conn)
