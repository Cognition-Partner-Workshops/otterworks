"""Run SQL against the run database on the shared RDS PostgreSQL instance.

The instance is reachable only inside its VPC, so scripts/billing-to-rds.py
invokes this function instead of opening a client connection. The event
carries the login credentials and either "exec" statements (applied in one
transaction) or "query" statements (rows returned). Credentials arrive in the
event and are never logged.
"""

import json
import os
import ssl

from pg8000.native import Connection, DatabaseError

CA_BUNDLE = os.path.join(os.path.dirname(__file__), "rds-ca.pem")


def _ssl():
    ctx = ssl.create_default_context(cafile=CA_BUNDLE)
    ctx.check_hostname = True
    return ctx


def _connect(db):
    return Connection(
        user=db["user"], password=db["password"], host=db["host"],
        port=int(db["port"]), database=db["dbname"],
        ssl_context=_ssl(), timeout=30,
    )


def _error(exc):
    detail = exc.args[0] if exc.args and isinstance(exc.args[0], dict) else {}
    return detail.get("C"), detail.get("M", "database error")


def _exec(db, statements):
    conn = _connect(db)
    try:
        conn.run("BEGIN")
        for index, statement in enumerate(statements):
            try:
                conn.run(statement)
            except DatabaseError as exc:
                conn.run("ROLLBACK")
                code, message = _error(exc)
                raise RuntimeError(
                    f"statement {index} failed: {code} {message} ({statement[:120]!r})"
                ) from None
        conn.run("COMMIT")
    finally:
        conn.close()
    return {"executed": len(statements)}


def _query(db, queries):
    results = {}
    conn = _connect(db)
    try:
        for query in queries:
            try:
                results[query["name"]] = [list(row) for row in conn.run(query["sql"])]
            except DatabaseError as exc:
                code, message = _error(exc)
                results[query["name"]] = {"error": f"{code} {message}"}
    finally:
        conn.close()
    return {"results": results}


def handler(event, _context):
    db = event["db"]
    op = event.get("op", "exec")
    try:
        if op == "exec":
            result = _exec(db, event["statements"])
        elif op == "query":
            result = _query(db, event["queries"])
        else:
            raise RuntimeError(f"unknown op: {op}")
    except DatabaseError as exc:
        code, message = _error(exc)
        print(json.dumps({"op": op, "error": message, "code": code}))
        raise RuntimeError(f"{op} failed: {code} {message}") from None
    logged = result if op == "exec" else {
        "rows": {name: len(rows) if isinstance(rows, list) else rows for name, rows in result["results"].items()}
    }
    print(json.dumps({"op": op, "database": db.get("dbname"), "result": logged}, default=str))
    return json.loads(json.dumps(result, default=str))
