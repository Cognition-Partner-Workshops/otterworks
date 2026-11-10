"""Validate and preview the scoped role plan before any privileged apply."""
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
        content = path.read_text()
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
        schemas.update(re.findall(r'CREATE SCHEMA IF NOT EXISTS (\w+)', path.read_text()))
    roles = {"SFX_D1110_" + role for role in
             ("ROLE", "LOADER", "TRANSFORMER", "PARITY", "SNOWPARK", "OPS", "ANALYST")}
    for filename, line, sql in plan:
        upper = sql.upper()
        if re.search(r"\bON\s+ACCOUNT\b", upper):
            raise ValueError("ON ACCOUNT grants are forbidden")
        if not (upper.startswith("CREATE ROLE ") or upper.startswith("GRANT ")):
            raise ValueError(f"Unsupported statement: {filename}:{line}")
        referenced_roles = re.findall(r"(?:CREATE ROLE(?: IF NOT EXISTS)?|TO ROLE|GRANT ROLE)\s+(\w+)", upper)
        if not referenced_roles or any(role not in roles for role in referenced_roles):
            raise ValueError("Role outside the allowed functional hierarchy")
        if upper.startswith("CREATE ROLE "):
            if not re.fullmatch(r"CREATE ROLE IF NOT EXISTS SFX_D1110_\w+ COMMENT='sfx-d1110 [a-z]+';", sql):
                raise ValueError("Role creation requires a token comment")
            continue
        if upper.startswith("GRANT ROLE "):
            if not re.fullmatch(r"GRANT ROLE SFX_D1110_\w+ TO ROLE SFX_D1110_\w+;", upper):
                raise ValueError("Invalid hierarchy grant")
            continue
        match = re.fullmatch(
            r"GRANT ([A-Z, ]+) ON (WAREHOUSE|DATABASE|SCHEMA|(?:ALL|FUTURE) (?:STAGES|TABLES|VIEWS|PROCEDURES|FILE FORMATS) IN SCHEMA|FUTURE SCHEMAS IN DATABASE) ([A-Z0-9_.]+) TO ROLE (SFX_D1110_\w+);",
            upper,
        )
        if not match:
            raise ValueError(f"Unsupported grant: {filename}:{line}")
        _, kind, obj, _ = match.groups()
        if kind == "WAREHOUSE":
            valid = obj in WORKLOADS.values()
        elif kind in ("DATABASE", "FUTURE SCHEMAS IN DATABASE"):
            valid = obj == "SFX_D1110_AFTER"
        else:
            valid = obj.startswith("SFX_D1110_AFTER.") and obj.split(".")[1] in schemas and obj.count(".") == 1
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
