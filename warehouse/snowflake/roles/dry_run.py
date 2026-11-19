"""Validate and preview the scoped role plan before any privileged apply."""

import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[3]))
from warehouse.run_config import render as _run_render

import argparse
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sfx_conn import ROOT, WORKLOADS, connect

ROLE_DIR = Path(__file__).resolve().parent


def statements(folder=ROLE_DIR):
    result = []
    for path in sorted(Path(folder).glob("[0-9]*.sql")):
        content = _run_render(path.read_text())
        for match in re.finditer(r"[^;]+;", content):
            sql = match.group().strip()
            if sql:
                line = content.count("\n", 0, match.start() + len(match.group()) - len(match.group().lstrip())) + 1
                result.append((path.name, line, sql))
        if content.rsplit(";", 1)[-1].strip():
            raise ValueError(f"Unterminated SQL in {path.name}")
    return result


def validate(plan):
    schemas = set()
    for path in (ROOT / 'migrations').glob('V*.sql'):
        schemas.update(re.findall(r'CREATE SCHEMA IF NOT EXISTS (\w+)', _run_render(path.read_text())))
    roles = {_run_render("__RUN_DATABASE___") + role for role in
             ("ROLE", "LOADER", "TRANSFORMER", "PARITY", "SNOWPARK", "OPS", "ANALYST")}
    for filename, line, sql in plan:
        upper = sql.upper()
        if re.search(r"\bON\s+ACCOUNT\b", upper):
            raise ValueError("ON ACCOUNT grants are forbidden")
        if upper.startswith("REVOKE "):
            match = re.fullmatch(
                _run_render(r"REVOKE ALL PRIVILEGES ON (DATABASE|(?:ALL|FUTURE) (?:SCHEMAS|TABLES|VIEWS) IN DATABASE|FUTURE (?:TABLES|VIEWS) IN SCHEMA) (__RUN_DATABASE__(?:\.[A-Z0-9_]+)?) FROM ROLE __RUN_DATABASE___ANALYST;"),
                upper,
            )
            if not match:
                raise ValueError(f"Unsupported analyst reset: {filename}:{line}")
            kind, obj = match.groups()
            if ((kind.endswith("IN SCHEMA") and obj.split(".")[-1] not in schemas) or
                    (not kind.endswith("IN SCHEMA") and obj != _run_render("__RUN_DATABASE__"))):
                raise ValueError(f"Object outside scaffold: {filename}:{line}")
            continue
        if not (upper.startswith("CREATE ROLE ") or upper.startswith("GRANT ")):
            raise ValueError(f"Unsupported statement: {filename}:{line}")
        referenced_roles = re.findall(r"(?:CREATE ROLE(?: IF NOT EXISTS)?|TO ROLE|GRANT ROLE)\s+(\w+)", upper)
        if not referenced_roles or any(role not in roles for role in referenced_roles):
            raise ValueError("Role outside the allowed functional hierarchy")
        if upper.startswith("CREATE ROLE "):
            if not re.fullmatch(_run_render(r"CREATE ROLE IF NOT EXISTS __RUN_DATABASE___\w+ COMMENT='__RUN_TOKEN__ [a-z]+';"), sql):
                raise ValueError("Role creation requires a token comment")
            continue
        if upper.startswith("GRANT ROLE "):
            if not re.fullmatch(_run_render(r"GRANT ROLE __RUN_DATABASE___\w+ TO ROLE __RUN_DATABASE___\w+;"), upper):
                raise ValueError("Invalid hierarchy grant")
            if upper.endswith(_run_render(" TO ROLE __RUN_DATABASE___ANALYST;")):
                raise ValueError("Analyst cannot inherit functional roles")
            continue
        match = re.fullmatch(
            _run_render(r"GRANT ([A-Z, ]+) ON (WAREHOUSE|DATABASE|SCHEMA|TAG|(?:ALL|FUTURE) (?:STAGES|TABLES|VIEWS|PROCEDURES|FILE FORMATS) IN SCHEMA|FUTURE SCHEMAS IN DATABASE) ([A-Z0-9_.]+) TO ROLE (__RUN_DATABASE___\w+);"),
            upper,
        )
        if not match:
            raise ValueError(f"Unsupported grant: {filename}:{line}")
        privileges, kind, obj, role = match.groups()
        if role == _run_render("__RUN_DATABASE___ANALYST"):
            if kind in ("DATABASE", "WAREHOUSE"):
                allowed = privileges == "USAGE"
            else:
                schema = obj.split(".")[-1]
                curated = schema in {"MART", "MART_SPARK", "COMPAT"}
                allowed = curated and (
                    (kind == "SCHEMA" and privileges == "USAGE") or
                    (kind in ("ALL TABLES IN SCHEMA", "FUTURE TABLES IN SCHEMA",
                              "ALL VIEWS IN SCHEMA", "FUTURE VIEWS IN SCHEMA") and
                     privileges == "SELECT")
                )
            if not allowed:
                raise ValueError(f"Analyst grants must be read-only and curated: {filename}:{line}")
        if kind == "WAREHOUSE":
            valid = obj in WORKLOADS.values()
        elif kind in ("DATABASE", "FUTURE SCHEMAS IN DATABASE"):
            valid = obj == _run_render("__RUN_DATABASE__")
        elif kind == "TAG":
            valid = (obj == _run_render("__RUN_DATABASE__.GOVERNANCE.SFX_RUN") and privileges == "APPLY"
                     and role in {_run_render("__RUN_DATABASE___TRANSFORMER"), _run_render("__RUN_DATABASE___SNOWPARK")})
        else:
            valid = obj.startswith(_run_render("__RUN_DATABASE__.")) and obj.split(".")[1] in schemas and obj.count(".") == 1
        if not valid:
            raise ValueError(f"Object outside scaffold: {filename}:{line}")
    return plan


def has_create_role(cursor):
    cursor.execute("SELECT CURRENT_ROLE()")
    current = cursor.fetchone()[0]
    visited = set()
    pending = [current]
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        # Server-returned role name is quoted as a Snowflake identifier.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        cursor.execute('SHOW GRANTS TO ROLE "' + current.replace('"', '""') + '"')
        columns = [col[0].lower() for col in cursor.description]
        grants = [dict(zip(columns, row)) for row in cursor.fetchall()]
        if any(row.get("privilege", "").upper() == "CREATE ROLE"
               and row.get("granted_on", "").upper() == "ACCOUNT" for row in grants):
            return True
        inherited = [row["name"] for row in grants if row.get("granted_on", "").upper() == "ROLE"]
        pending.extend(role for role in inherited if role not in visited)
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-live", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    plan = validate(statements())
    for filename, line, sql in plan:
        print(f"{filename}:{line}: {sql}")
    print(f"validated {len(plan)} statements")
    if args.check_live or args.apply:
        with connect("ops", "roles-dry-run") as conn:
            with conn.cursor() as cur:
                allowed = has_create_role(cur)
                if not allowed:
                    print("apply skipped: role lacks CREATE ROLE")
                    if args.apply:
                        raise SystemExit(1)
                elif args.apply:
                    for _, _, sql in plan:
                        cur.execute(sql)
                    print("role plan applied")
                else:
                    print("CREATE ROLE held; dry-run only, no DDL executed")


if __name__ == "__main__":
    main()
