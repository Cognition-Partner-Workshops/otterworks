import argparse
import csv
import io
import os
import re
import subprocess
import sys
from urllib.parse import parse_qsl, unquote, urlsplit

from control_report import assertion_report, load


IDENT = re.compile(r"[a-z_][a-z0-9_]*")


def literal(value):
    return "'" + value.replace("'", "''") + "'"


def connection_env(dsn):
    options = {
        "sslmode": "PGSSLMODE", "sslrootcert": "PGSSLROOTCERT", "sslcert": "PGSSLCERT",
        "sslkey": "PGSSLKEY", "connect_timeout": "PGCONNECT_TIMEOUT",
    }
    try:
        uri = urlsplit(dsn)
        if (uri.scheme not in ("postgresql", "postgres") or not uri.hostname or not uri.username
                or not uri.path.strip("/") or uri.fragment):
            raise ValueError
        result = {
            "PGHOST": unquote(uri.hostname), "PGPORT": str(uri.port or 5432),
            "PGUSER": unquote(uri.username), "PGDATABASE": unquote(uri.path[1:]),
        }
        if uri.password is not None:
            result["PGPASSWORD"] = unquote(uri.password)
        for key, value in parse_qsl(uri.query, strict_parsing=True):
            result[options[key]] = value
        return result
    except (KeyError, ValueError) as error:
        raise ValueError("expected a PostgreSQL URL with host, user and database; unsupported connection option") from error


def scalar(dsn, sql):
    result = subprocess.run(
        ["psql", "--no-psqlrc", "--csv", "--tuples-only", "--no-password", "-v", "ON_ERROR_STOP=1"],
        input="BEGIN READ ONLY;\n" + sql + ";\nROLLBACK;\n",
        env={**os.environ, **connection_env(dsn)},
        text=True, capture_output=True, timeout=30,
    )
    if result.returncode:
        raise ValueError("psql could not run a read-only assertion (connection or SQL failed)")
    rows = list(csv.reader(io.StringIO(result.stdout)))
    rows = [row for row in rows if row not in (["BEGIN"], ["ROLLBACK"])]
    if len(rows) != 1 or len(rows[0]) != 1:
        raise ValueError("assertion must return one scalar")
    return rows[0][0]


def verify_role(dsn, role, table, query=scalar):
    if not IDENT.fullmatch(role) or not all(IDENT.fullmatch(part) for part in table.split(".")) or table.count(".") != 1:
        raise ValueError("expected an ordinary role and a schema-qualified table")
    sql = f"""
SELECT CASE
    WHEN session_user <> {literal(role)} OR current_user <> {literal(role)} THEN 'wrong login'
    WHEN pg_has_role(c.relowner, 'MEMBER') THEN 'owns table or can assume its owner'
    WHEN r.rolsuper OR r.rolbypassrls THEN 'bypasses RLS'
    ELSE 'ok' END
FROM pg_class c JOIN pg_roles r ON r.rolname = current_user
WHERE c.oid = {literal(table)}::regclass
"""
    result = query(dsn, sql)
    if result != "ok":
        raise ValueError(f"refusing {role}: {result}")


def run(spec, connections, query=scalar):
    assertions = spec["assertions"]
    if not assertions or {check["role"] for check in assertions} != set(spec["roles"]):
        raise ValueError("each ordinary role must have at least one assertion")
    for role in spec["roles"]:
        verify_role(connections[role], role, spec["table"], query)
    rows = []
    for check in assertions:
        expected = check["expected_count"]
        access = check["access"]
        if type(expected) is not int or not (
            (access == "allow" and expected > 0) or (access == "deny" and expected == 0)
        ):
            raise ValueError("allow assertions need a positive expected_count; deny requires zero")
        sql = check["sql"].strip()
        if not re.match(r"SELECT\b", sql, re.I) or any(c in sql for c in (";", "\\")):
            raise ValueError("expected a single SELECT without psql commands")
        actual = int(query(connections[check["role"]], sql))
        rows.append({
            "role": check["role"], "check": check["name"], "access": access,
            "expected": expected, "actual": actual, "passed": actual == expected,
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description="Check tenant row visibility as ordinary Postgres login roles")
    parser.add_argument("spec", help="YAML or JSON containing table, role-to-PostgreSQL-URL environment variables, and assertions")
    parser.add_argument("--output", required=True, help="Path stem for JSON and Markdown")
    args = parser.parse_args()
    try:
        spec = load(args.spec)
        rows = run(spec, {role: os.environ[var] for role, var in spec["roles"].items()})
        return assertion_report(args.output, "Row isolation assertions", rows, [
            ("role", "Role"), ("check", "Check"), ("access", "Access"),
            ("expected", "Expected rows"), ("actual", "Actual rows"), ("passed", "Passed"),
        ])
    except (KeyError, ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(f"RLS check did not run: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
