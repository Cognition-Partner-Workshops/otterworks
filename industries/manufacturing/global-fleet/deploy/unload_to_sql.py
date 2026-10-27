#!/usr/bin/env python3
"""Turn the mainframe unloads into SQL for schema legacy_uk, following copybooks/LAYOUT.md."""
import sys
from pathlib import Path


def text(rec, off, n):
    return rec[off:off + n].decode("ascii").strip()


def num(rec, off, n, scale=0):
    v = int(rec[off:off + n].decode("ascii"))
    return v / 10 ** scale if scale else v


def comp3(rec, off, n, scale=2):
    raw = rec[off:off + n]
    digits = "".join("%02x" % b for b in raw)
    sign = -1 if digits[-1] in "bd" else 1
    return sign * int(digits[:-1]) / 10 ** scale


def date(rec, off):
    v = rec[off:off + 8].decode("ascii")
    return None if v == "00000000" else "%s-%s-%s" % (v[:4], v[4:6], v[6:])


def records(path, lrecl):
    data = Path(path).read_bytes()
    return [data[i:i + lrecl] for i in range(0, len(data) - lrecl + 1, lrecl)]


def lit(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def insert(table, cols, rows):
    out = []
    for r in rows:
        out.append("INSERT INTO legacy_uk.%s (%s) VALUES (%s);" % (table, ", ".join(cols), ", ".join(lit(v) for v in r)))
    return out


def main(unload_dir):
    d = Path(unload_dir)
    sql = ["BEGIN;",
           "CREATE TABLE legacy_uk.employee (dbkey BIGINT PRIMARY KEY, empid VARCHAR(8), surname VARCHAR(20), forename VARCHAR(15),"
           " grade INTEGER, cost_centre VARCHAR(6), hire_date DATE, leave_date DATE, status CHAR(1), contribution NUMERIC(9,2), location VARCHAR(4));",
           "CREATE TABLE legacy_uk.vehicle (vehid VARCHAR(8) PRIMARY KEY, plate VARCHAR(8), make VARCHAR(12), model VARCHAR(16), list_price NUMERIC(11,2),"
           " co2 INTEGER, benefit_percent NUMERIC(5,2), fuel CHAR(1), registered DATE, owner_empid VARCHAR(8), owner_dbkey BIGINT);",
           "CREATE TABLE legacy_uk.assignment (asgid VARCHAR(10) PRIMARY KEY, empid VARCHAR(8), emp_dbkey BIGINT, vehid VARCHAR(8),"
           " start_date DATE, end_date DATE, reason VARCHAR(2));",
           "CREATE TABLE legacy_uk.mileage_claim (clmid VARCHAR(10) PRIMARY KEY, empid VARCHAR(8), emp_dbkey BIGINT, vehid VARCHAR(8),"
           " claim_date DATE, miles INTEGER, status CHAR(1), purpose VARCHAR(10));",
           "CREATE TABLE legacy_uk.benefit_period (period CHAR(6) PRIMARY KEY, start_date DATE, end_date DATE, mileage_rate NUMERIC(6,3),"
           " status CHAR(1), run_date DATE);"]
    sql += insert("employee", ["dbkey", "empid", "surname", "forename", "grade", "cost_centre", "hire_date", "leave_date", "status", "contribution", "location"],
                  [(num(r, 0, 10), text(r, 10, 8), text(r, 18, 20), text(r, 38, 15), num(r, 53, 2), text(r, 55, 6),
                    date(r, 61), date(r, 69), text(r, 77, 1), comp3(r, 78, 4), text(r, 82, 4)) for r in records(d / "EMPLOYEE.dat", 100)])
    sql += insert("vehicle", ["vehid", "plate", "make", "model", "list_price", "co2", "benefit_percent", "fuel", "registered", "owner_empid", "owner_dbkey"],
                  [(text(r, 10, 8), text(r, 18, 8), text(r, 26, 12), text(r, 38, 16), comp3(r, 54, 5), num(r, 59, 3), num(r, 62, 4, 2),
                    text(r, 66, 1), date(r, 67), text(r, 75, 8) or None, num(r, 83, 10) or None) for r in records(d / "VEHICLE.dat", 100)])
    sql += insert("assignment", ["asgid", "empid", "emp_dbkey", "vehid", "start_date", "end_date", "reason"],
                  [(text(r, 0, 10), text(r, 10, 8), num(r, 18, 10), text(r, 28, 8), date(r, 36), date(r, 44), text(r, 52, 2))
                   for r in records(d / "ASSIGNMENT.dat", 64)])
    sql += insert("mileage_claim", ["clmid", "empid", "emp_dbkey", "vehid", "claim_date", "miles", "status", "purpose"],
                  [(text(r, 0, 10), text(r, 10, 8), num(r, 18, 10), text(r, 28, 8) or None, date(r, 36), num(r, 44, 5), text(r, 49, 1), text(r, 50, 10))
                   for r in records(d / "MILECLM.dat", 64)])
    sql += insert("benefit_period", ["period", "start_date", "end_date", "mileage_rate", "status", "run_date"],
                  [(text(r, 0, 6), date(r, 6), date(r, 14), num(r, 22, 4, 3), text(r, 26, 1), date(r, 27))
                   for r in records(d / "BENPRD.dat", 40)])
    sql.append("COMMIT;")
    print("\n".join(sql))


if __name__ == "__main__":
    main(sys.argv[1])
