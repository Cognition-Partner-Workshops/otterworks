"""Create or drop one run's database and login role on the shared RDS PostgreSQL instance.

Invoked by aws_lambda_invocation (lifecycle_scope CRUD); event["tf"]["action"] is
create, update or delete. Credentials arrive in the event and are never logged.
"""

import json
import os
import ssl

from pg8000.native import Connection, DatabaseError, identifier, literal

CA_BUNDLE = os.path.join(os.path.dirname(__file__), "rds-ca.pem")


def _ssl():
    ctx = ssl.create_default_context(cafile=CA_BUNDLE)
    ctx.check_hostname = True
    return ctx


def _connect(host, port, user, password, database):
    return Connection(
        user=user, password=password, host=host, port=int(port), database=database,
        ssl_context=_ssl(), timeout=30,
    )


def _ensure(event):
    m = event["master"]
    db, role, pw = event["database"], event["role"], event["role_password"]
    limit = int(event.get("connection_limit", 20))
    conn = _connect(m["host"], m["port"], m["user"], m["password"], m["dbname"])
    try:
        opts = f"LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION CONNECTION LIMIT {limit}"
        if conn.run("SELECT 1 FROM pg_roles WHERE rolname = :r", r=role):
            conn.run(f"ALTER ROLE {identifier(role)} WITH {opts} PASSWORD {literal(pw)}")
        else:
            conn.run(f"CREATE ROLE {identifier(role)} WITH {opts} PASSWORD {literal(pw)}")
        if not conn.run("SELECT 1 FROM pg_database WHERE datname = :d", d=db):
            conn.run(f"CREATE DATABASE {identifier(db)} ENCODING 'UTF8' TEMPLATE template0")
        conn.run(f"REVOKE ALL ON DATABASE {identifier(db)} FROM PUBLIC")
        conn.run(f"GRANT CONNECT, CREATE, TEMPORARY ON DATABASE {identifier(db)} TO {identifier(role)}")
    finally:
        conn.close()

    conn = _connect(m["host"], m["port"], m["user"], m["password"], db)
    try:
        conn.run(f"REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        conn.run(f"GRANT USAGE, CREATE ON SCHEMA public TO {identifier(role)}")
    finally:
        conn.close()
    return _evidence(event)


def _evidence(event):
    m = event["master"]
    db, role = event["database"], event["role"]
    conn = _connect(m["host"], m["port"], m["user"], m["password"], m["dbname"])
    try:
        cols = ["name", "owner", "encoding", "collate", "ctype", "access_privileges"]
        row = conn.run(
            "SELECT d.datname, pg_get_userbyid(d.datdba), pg_encoding_to_char(d.encoding),"
            " d.datcollate, d.datctype, coalesce(array_to_string(d.datacl, E'\\n'), '')"
            " FROM pg_database d WHERE d.datname = :d", d=db)
        rcols = ["rolname", "rolcanlogin", "rolsuper", "rolcreatedb", "rolcreaterole", "rolinherit", "rolconnlimit"]
        rrow = conn.run(
            "SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolinherit, rolconnlimit"
            " FROM pg_roles WHERE rolname = :r", r=role)
        member_of = [r[0] for r in conn.run(
            "SELECT b.rolname FROM pg_auth_members a JOIN pg_roles b ON b.oid = a.roleid"
            " JOIN pg_roles u ON u.oid = a.member WHERE u.rolname = :r", r=role)]
        create_on = [r[0] for r in conn.run(
            "SELECT datname FROM pg_database WHERE datallowconn"
            " AND has_database_privilege(:r, datname, 'CREATE') ORDER BY 1", r=role)]
    finally:
        conn.close()

    conn = _connect(m["host"], m["port"], role, event["role_password"], db)
    try:
        who = conn.run("SELECT current_user, current_database(), split_part(version(), ' ', 2),"
                       " (SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid())")[0]
    finally:
        conn.close()

    return {
        "database": dict(zip(cols, row[0])) if row else None,
        "role": dict(zip(rcols, rrow[0])) if rrow else None,
        "role_member_of": member_of,
        "role_has_create_on": create_on,
        "login_as_role": {"current_user": who[0], "current_database": who[1],
                          "server_version": who[2], "ssl": who[3]},
    }


def _drop(event):
    m = event["master"]
    db, role = event["database"], event["role"]
    conn = _connect(m["host"], m["port"], m["user"], m["password"], m["dbname"])
    try:
        conn.run(f"DROP DATABASE IF EXISTS {identifier(db)} WITH (FORCE)")
        conn.run(f"DROP ROLE IF EXISTS {identifier(role)}")
    finally:
        conn.close()
    return {"dropped": {"database": db, "role": role}}


def handler(event, _context):
    action = (event.get("tf") or {}).get("action", "create")
    try:
        result = _drop(event) if action == "delete" else _ensure(event)
    except DatabaseError as exc:
        detail = exc.args[0] if exc.args and isinstance(exc.args[0], dict) else {}
        print(json.dumps({"action": action, "error": detail.get("M", "database error"), "code": detail.get("C")}))
        raise RuntimeError(f"{action} failed: {detail.get('C')} {detail.get('M', 'database error')}") from None
    print(json.dumps({"action": action, "database": event.get("database"), "role": event.get("role"), "result": result}, default=str))
    return json.loads(json.dumps(result, default=str))
