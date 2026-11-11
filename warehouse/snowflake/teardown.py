"""Discover token-scoped resources, preview or execute ordered cleanup."""
import argparse
from dataclasses import dataclass
import re

from snowflake.connector.errors import ProgrammingError

from sfx_conn import WORKLOADS, connect

PROVISIONED = {
    ("ROLE", "SFX_D1110_ROLE"), ("USER", "SFX_D1110_SVC"),
    ("DATABASE", "SFX_D1110_AFTER"), ("RESOURCE MONITOR", "SFX_D1110_RM"),
    *(("WAREHOUSE", name) for name in WORKLOADS.values()),
}


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def tagged(name, comment, token):
    normalized = lambda value: re.sub(r"[^a-z0-9]", "", value.lower())
    return normalized(token) in normalized(name) or token.lower() in (comment or "").lower()


def name_scoped(name, token):
    prefix = re.sub(r'[^a-z0-9]', '_', token.lower()) + '_'
    return name.lower().startswith(prefix)


def removable(obj, token):
    if obj.kind == 'DATABASE' and obj.name.upper().startswith('DROPPED_USER$'):
        return tagged(obj.name, obj.comment, token)
    return name_scoped(obj.parts[0], token)


@dataclass(frozen=True)
class Object:
    kind: str
    parts: tuple
    comment: str = ""

    @property
    def name(self):
        return ".".join(self.parts)

    @property
    def sql_name(self):
        return ".".join(quote(part) for part in self.parts)

    @property
    def provisioned(self):
        return (self.kind, self.name) in PROVISIONED


def show(cursor, command, denied):
    try:
        cursor.execute(command)
        columns = [column[0].lower() for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except ProgrammingError as error:
        if (error.sqlstate == "42501" or error.errno == 3001
                or "insufficient privilege" in str(error).lower()
                or "not authorized" in str(error).lower()):
            denied.append(command.split(" IN ")[0])
            print(f"{command.split(' IN ')[0]}: not visible to role; insufficient privilege; inventory incomplete")
            return []
        raise


def discover(cursor, token, dropped_users=None):
    objects = set()
    denied = []
    dropped_users = dropped_users if dropped_users is not None else set()
    users = show(cursor, 'SHOW USERS', denied)
    for row in users:
        if name_scoped(row['name'], token):
            dropped_users.add(row['name'].upper())
    candidates = show(cursor, "SHOW DATABASES LIKE '%SFX_D1110%'", denied)
    candidates += show(cursor, "SHOW DATABASES", denied)
    for row in candidates:
        if row['name'].upper().startswith('DROPPED_USER$'):
            original = re.fullmatch(r'DROPPED_USER\$(.+)_\d+', row['name'], re.I)
            belongs = original is not None and original.group(1).upper() in dropped_users
            if belongs or tagged(row['name'], row.get('comment'), token):
                row['comment'] = (row.get('comment') or '') + ' ' + token + ' dropped token user database'
            else:
                print(f"REMAINS DATABASE {row['name']} (unattributed DROPPED_USER database; not removed)")
    databases = {row["name"]: row for row in candidates
                 if tagged(row["name"], row.get("comment"), token)}
    for name, database in sorted(databases.items()):
        objects.add(Object("DATABASE", (name,), database.get("comment") or ""))
        for schema in show(cursor, f"SHOW SCHEMAS IN DATABASE {quote(name)}", denied):
            schema_name = schema["name"]
            if schema_name == "INFORMATION_SCHEMA":
                continue
            parts = (name, schema_name)
            if tagged(schema_name, schema.get("comment"), token):
                objects.add(Object("SCHEMA", parts, schema.get("comment") or ""))
            scope = ".".join(quote(part) for part in parts)
            for kind, plural in (("TASK", "TASKS"), ("STAGE", "STAGES"), ('TAG', 'TAGS')):
                for row in show(cursor, f"SHOW {plural} IN SCHEMA {scope}", denied):
                    if tagged(row["name"], row.get("comment"), token):
                        objects.add(Object(kind, (*parts, row["name"]), row.get("comment") or ""))
    for kind, plural in (("WAREHOUSE", "WAREHOUSES"), ("ROLE", "ROLES"),
                         ("USER", "USERS"), ("RESOURCE MONITOR", "RESOURCE MONITORS"),
                         ('INTEGRATION', 'INTEGRATIONS'), ('APPLICATION', 'APPLICATIONS'),
                         ('COMPUTE POOL', 'COMPUTE POOLS'), ('SERVICE', 'SERVICES IN ACCOUNT')):
        rows = users if kind == 'USER' else show(cursor, f"SHOW {plural}", denied)
        for row in rows:
            if tagged(row["name"], row.get("comment"), token):
                parts = ((row['database_name'], row['schema_name'], row['name'])
                         if kind == 'SERVICE' else (row['name'],))
                objects.add(Object(kind, parts, row.get("comment") or ""))
    return sorted(objects, key=lambda obj: (obj.kind, obj.name)), denied


def plan(objects, include_provisioned=False, suspend_only=False, token='sfx-d1110'):
    commands = []
    objects = [obj for obj in objects if removable(obj, token)]
    tasks = [obj for obj in objects if obj.kind == "TASK"]
    warehouses = [obj for obj in objects if obj.kind == "WAREHOUSE"]
    pools = [obj for obj in objects if obj.kind == 'COMPUTE POOL']
    for obj in tasks + warehouses + pools:
        commands.append(f"ALTER {obj.kind} {obj.sql_name} SUSPEND")
    if suspend_only:
        return commands
    ordering = {'TASK': 0, 'SERVICE': 1, 'STAGE': 2, 'INTEGRATION': 3, 'TAG': 4,
                'SCHEMA': 5, 'APPLICATION': 6, 'DATABASE': 7, 'COMPUTE POOL': 8,
                'WAREHOUSE': 9, 'RESOURCE MONITOR': 10, 'USER': 11, 'ROLE': 12}
    for obj in sorted(objects, key=lambda item: (
            ordering[item.kind], item.name == "SFX_D1110_ROLE", item.name)):
        if obj.provisioned and not include_provisioned:
            continue
        cascade = " CASCADE" if obj.kind in ("SCHEMA", "DATABASE") else ""
        commands.append(f"DROP {obj.kind} IF EXISTS {obj.sql_name}{cascade}")
    return commands


def execute_plan(cursor, commands):
    for command in commands:
        try:
            cursor.execute(command)
        except ProgrammingError as error:
            if command.startswith("ALTER WAREHOUSE") and error.errno == 90064:
                name = command[len("ALTER WAREHOUSE "):-len(" SUSPEND")]
                cursor.execute("SHOW WAREHOUSES")
                columns = [col[0].lower() for col in cursor.description]
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
                if any(quote(row["name"]) == name and row["state"] == "SUSPENDED" for row in rows):
                    continue
            raise


def cleanup(cursor, token, dry_run=False, include_provisioned=False, suspend_only=False):
    dropped_users = set()
    objects, denied = discover(cursor, token, dropped_users)
    commands = plan(objects, include_provisioned, suspend_only, token)
    print("Inventory is limited to objects visible to the current role")
    for command in commands:
        print(("PLAN " if dry_run else "EXECUTE ") + command + ";")
    if not dry_run:
        execute_plan(cursor, commands)
    if suspend_only:
        print(f"Suspension complete: {len(commands)} commands; no objects dropped")
        return 1 if denied else 0
    remaining, remaining_denied = discover(cursor, token, dropped_users)
    if not dry_run:
        orphans = [obj for obj in remaining if obj.kind == 'DATABASE'
                   and obj.parts[0].upper().startswith('DROPPED_USER$') and not obj.provisioned
                   and removable(obj, token)]
        for obj in orphans:
            print(f'EXECUTE DROP DATABASE IF EXISTS {obj.sql_name} CASCADE;')
            # Discovered server object; sql_name quotes and escapes each identifier part.
            # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            cursor.execute(f'DROP DATABASE IF EXISTS {obj.sql_name} CASCADE')
        if orphans:
            remaining, more_denied = discover(cursor, token, dropped_users)
            remaining_denied += more_denied
    leftovers = [obj for obj in remaining if include_provisioned or not obj.provisioned]
    for obj in remaining:
        print(f"REMAINS {obj.kind} {obj.name}"
              + (" (provisioned)" if obj.provisioned else
                 " (not name-scoped; retained)" if not removable(obj, token) else ""))
    code = int(bool(leftovers or denied or remaining_denied))
    print(f"{'Dry-run' if dry_run else 'Teardown'} summary: {len(commands)} planned commands; "
          f"{len(leftovers)} non-exempt objects remain; exit code {code}")
    return code


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--include-provisioned", action="store_true")
    parser.add_argument("--suspend-only", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"sfx-d1110(?:-[a-z0-9]+)*", args.token):
        parser.error("--token must be sfx-d1110 or a scoped sfx-d1110-* token")
    with connect("ops", "teardown") as conn:
        with conn.cursor() as cur:
            code = cleanup(cur, args.token, args.dry_run, args.include_provisioned,
                           args.suspend_only)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
