#!/usr/bin/env python3
"""Run 20260927b, unit lakebase_scaffold: read-only extract of the four OW_BILLING reference tables.

Reads Oracle through python-oracledb (thin) with the read-only principal named by the env var
OW_BILLING_RO_DSN (oracle://user:pw@host:port/service) and prints one JSON line per row to stdout:
{"t": "<lakebase table>", "r": [values...]} with NUMBER as decimal strings and TIMESTAMP as ISO-8601.
Exactly one SELECT per table, whole table, `ns::` demo tenants included. Pipe it into load_reference.py.
Optional argv[1]: the NAME of another env var holding the fixture copy's oracle:// URL (fixture-first runs).
"""
import datetime as dt
import decimal
import json
import os
import sys
import urllib.parse as u

import oracledb

oracledb.defaults.fetch_decimals = True


def _plain(v):
    if isinstance(v, decimal.Decimal):
        return str(v)
    if isinstance(v, dt.datetime):
        return v.isoformat(sep=" ", timespec="microseconds")
    return v


def _emit(cur, table, counts):
    n = 0
    for row in cur:
        print(json.dumps({"t": table, "r": [_plain(v) for v in row]}))
        n += 1
    counts[table] = n


def main(argv):
    name = argv[1] if len(argv) > 1 else "OW_BILLING_RO_DSN"
    url = os.environ[name] if name != "OW_BILLING_RO_DSN" else os.environ["OW_BILLING_RO_DSN"]
    p = u.urlsplit(url)
    if p.scheme != "oracle":
        raise SystemExit(name + " must be an oracle:// URL")
    conn = oracledb.connect(user=u.unquote(p.username or ""), password=u.unquote(p.password or ""),
                            dsn=f"{p.hostname}:{p.port or 1521}/{p.path.lstrip('/')}")
    counts = {}
    with conn:
        cur = conn.cursor()
        cur.arraysize = 5000
        cur.execute("SELECT CODE_TYPE, CODE_VAL, CODE_DESC FROM OW_BILLING.CODES ORDER BY CODE_TYPE, CODE_VAL")
        _emit(cur, "codes", counts)
        cur.execute("SELECT ID, CODE, TIER_CD, MONTHLY_FEE, INCLUDED_UNITS, OVERAGE_RATE, ACTIVE_YN FROM OW_BILLING.PLANS ORDER BY ID")
        _emit(cur, "plans", counts)
        cur.execute("SELECT ID, NAME, TAX_EXEMPT_YN, STATUS_CD FROM OW_BILLING.TENANTS ORDER BY ID")
        _emit(cur, "tenants", counts)
        cur.execute("SELECT ID, TENANT_ID, OCCURRED_AT, UNITS, KIND_CD FROM OW_BILLING.USAGE_EVENTS ORDER BY ID")
        _emit(cur, "usage_events", counts)
    print(json.dumps({"source_rows": counts, "statements": 4}), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
