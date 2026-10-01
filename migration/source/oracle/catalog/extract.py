"""Read-only inventory of the Oracle archive estate (schemas ARCHIVE and MIGAUDIT).

Writes one file per object, <OWNER>.<OBJECT_TYPE>.<NAME>.sql, holding DBMS_METADATA.GET_DDL output verbatim
(session transform parameters left at their defaults), plus INVENTORY.json: every DBA_OBJECTS row of both
schemas with the reason it is or is not catalogued, the SHA-256 of each DDL file, PL/SQL line counts,
dependencies, the scheduler job definition and table row counts.

Only SELECT statements and DBMS_METADATA calls are issued; the session is set read-only first.

    ORACLE_USER=... ORACLE_PASSWORD=... python migration/source/oracle/catalog/extract.py --dsn localhost:1521/FREEPDB1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

import oracledb

OWNERS = ("ARCHIVE", "MIGAUDIT")
CATALOGUED_TYPES = ("TABLE", "VIEW", "PACKAGE", "PACKAGE BODY", "TRIGGER", "SEQUENCE", "JOB", "INDEX")
METADATA_TYPE = {"PACKAGE": "PACKAGE_SPEC", "PACKAGE BODY": "PACKAGE_BODY", "JOB": "PROCOBJ"}
CATALOG_FILE_RE = re.compile(r"^[A-Z0-9_$#]+\.[A-Z_]+\.[A-Z0-9_$#]+\.sql$")
CATALOG_DIR = Path(__file__).resolve().parent


def catalog_file_name(owner: str, object_type: str, name: str) -> str:
    return f"{owner}.{object_type.replace(' ', '_')}.{name}.sql"


def exclusion_reason(object_type: str, subobject: str | None, generated: str) -> str | None:
    if subobject is not None:
        return f"{object_type.lower()} of {object_type.split()[0].lower()} (in the parent's DDL)"
    if generated == "Y":
        return "system-generated (identity column sequence, in the owning table's DDL)"
    if object_type not in CATALOGUED_TYPES:
        return f"type {object_type} not catalogued"
    return None


def fetch_ddl(cur: oracledb.Cursor, metadata_type: str, name: str, owner: str | None) -> str:
    if owner is None:
        cur.execute("SELECT DBMS_METADATA.GET_DDL(:t, :n) FROM DUAL", t=metadata_type, n=name)
    else:
        cur.execute("SELECT DBMS_METADATA.GET_DDL(:t, :n, :o) FROM DUAL", t=metadata_type, n=name, o=owner)
    (lob,) = cur.fetchone()
    return lob.read() if hasattr(lob, "read") else lob


def rows(cur: oracledb.Cursor, sql: str, **binds) -> list[dict]:
    cur.execute(sql, **binds)
    cols = [d[0].lower() for d in cur.description]
    return [dict(zip(cols, r, strict=True)) for r in cur]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dsn", default="localhost:1521/FREEPDB1")
    parser.add_argument("--user-env", default="ORACLE_USER")
    parser.add_argument("--password-env", default="ORACLE_PASSWORD")
    parser.add_argument("--out", type=Path, default=CATALOG_DIR)
    parser.add_argument("--no-row-counts", action="store_true")
    args = parser.parse_args()

    conn = oracledb.connect(user=os.environ[args.user_env], password=os.environ[args.password_env], dsn=args.dsn)
    cur = conn.cursor()
    cur.execute("SET TRANSACTION READ ONLY")

    owner_binds = {"o1": OWNERS[0], "o2": OWNERS[1]}
    objects = rows(
        cur,
        "SELECT owner, object_type, object_name, subobject_name, generated, status FROM dba_objects"
        " WHERE owner IN (:o1, :o2) ORDER BY owner, object_type, object_name, subobject_name",
        **owner_binds,
    )

    args.out.mkdir(parents=True, exist_ok=True)
    for stale in args.out.iterdir():
        if CATALOG_FILE_RE.match(stale.name):
            stale.unlink()

    inventory: list[dict] = []
    for owner in OWNERS:
        ddl = fetch_ddl(cur, "USER", owner, None)
        file_name = catalog_file_name(owner, "USER", owner)
        (args.out / file_name).write_text(ddl, encoding="utf-8", newline="")
        inventory.append(
            {
                "owner": owner,
                "object_type": "USER",
                "object_name": owner,
                "status": None,
                "catalogued": True,
                "file": file_name,
                "sha256": hashlib.sha256(ddl.encode()).hexdigest(),
                "lines": ddl.count("\n") + 1,
            }
        )
    for obj in objects:
        entry = {
            "owner": obj["owner"],
            "object_type": obj["object_type"],
            "object_name": obj["object_name"],
            "subobject_name": obj["subobject_name"],
            "generated": obj["generated"],
            "status": obj["status"],
        }
        reason = exclusion_reason(obj["object_type"], obj["subobject_name"], obj["generated"])
        if reason is not None:
            entry.update(catalogued=False, reason=reason)
        else:
            metadata_type = METADATA_TYPE.get(obj["object_type"], obj["object_type"])
            ddl = fetch_ddl(cur, metadata_type, obj["object_name"], obj["owner"])
            file_name = catalog_file_name(obj["owner"], obj["object_type"], obj["object_name"])
            (args.out / file_name).write_text(ddl, encoding="utf-8", newline="")
            entry.update(
                catalogued=True,
                file=file_name,
                sha256=hashlib.sha256(ddl.encode()).hexdigest(),
                lines=ddl.count("\n") + 1,
            )
        inventory.append(entry)

    counts: dict[str, dict[str, int]] = {}
    for obj in objects:
        per_owner = counts.setdefault(obj["owner"], {})
        per_owner[obj["object_type"]] = per_owner.get(obj["object_type"], 0) + 1

    table_rows = {}
    if not args.no_row_counts:
        for obj in objects:
            if obj["object_type"] == "TABLE":
                fq = f'{obj["owner"]}."{obj["object_name"]}"'
                cur.execute(f"SELECT COUNT(*) FROM {fq}")
                table_rows[f"{obj['owner']}.{obj['object_name']}"] = cur.fetchone()[0]

    (banner,) = cur.execute("SELECT banner_full FROM v$version").fetchone()
    report = {
        "database": banner.splitlines()[0],
        "service": args.dsn.rsplit("/", 1)[-1],
        "owners": list(OWNERS),
        "dba_objects_by_type": counts,
        "catalogued_by_type": {
            t: sum(1 for e in inventory if e["catalogued"] and e["object_type"] == t)
            for t in sorted({e["object_type"] for e in inventory if e["catalogued"]})
        },
        "table_rows": table_rows,
        "plsql_source_lines": rows(
            cur,
            "SELECT owner, name, type, COUNT(*) AS line_count FROM dba_source WHERE owner IN (:o1, :o2)"
            " GROUP BY owner, name, type ORDER BY owner, name, type",
            **owner_binds,
        ),
        "dependencies": rows(
            cur,
            "SELECT owner, name, type, referenced_owner, referenced_name, referenced_type FROM dba_dependencies"
            " WHERE owner IN (:o1, :o2) AND referenced_owner <> 'SYS' OR (owner IN (:o1, :o2)"
            " AND referenced_owner = 'SYS' AND referenced_name NOT IN ('STANDARD', 'SYS_STUB_FOR_PURITY_ANALYSIS'))"
            " ORDER BY owner, name, type, referenced_owner, referenced_name, referenced_type",
            **owner_binds,
        ),
        "triggers": rows(
            cur,
            "SELECT owner, trigger_name, trigger_type, triggering_event, table_owner, table_name, column_name,"
            " when_clause, status FROM dba_triggers WHERE owner IN (:o1, :o2) ORDER BY owner, trigger_name",
            **owner_binds,
        ),
        "scheduler_jobs": rows(
            cur,
            "SELECT owner, job_name, job_type, job_action, repeat_interval, enabled, state, max_failures,"
            " restartable, auto_drop, comments FROM dba_scheduler_jobs WHERE owner IN (:o1, :o2)"
            " ORDER BY owner, job_name",
            **owner_binds,
        ),
        "objects": inventory,
    }
    (args.out / "INVENTORY.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    conn.rollback()
    conn.close()
    print(
        json.dumps(
            {
                "dba_objects_by_type": counts,
                "catalogued_by_type": report["catalogued_by_type"],
                "table_rows": table_rows,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
