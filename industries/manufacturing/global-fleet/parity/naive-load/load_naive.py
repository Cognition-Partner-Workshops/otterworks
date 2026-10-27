#!/usr/bin/env python3
"""Load Global Fleet unload and portal seed data into a deliberately naive schema."""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

import psycopg


HERE = Path(__file__).resolve().parent
FLEET = HERE.parents[1]
MAINFRAME_PARITY = FLEET / "parity" / "mainframe"
sys.path.insert(0, str(MAINFRAME_PARITY))
from decode import decode_records


UNLOAD = FLEET / "mainframe" / "unload"
SEED = FLEET / "seed" / "jsf"
TABLES = {
    "EMPLOYEE.dat": ("employee", [
        ("empid", "empid"), ("surname", "surname"), ("forename", "forename"),
        ("grade", "grade"), ("costCentre", "cost_centre"), ("hireDate", "hire_date"),
        ("leaveDate", "leave_date"), ("status", "status"),
        ("contribution", "monthly_contribution"), ("location", "location"),
    ]),
    "VEHICLE.dat": ("vehicle", [
        ("vehid", "vehid"), ("plate", "plate"), ("make", "make"), ("model", "model"),
        ("listPrice", "list_price"), ("co2", "co2"),
        ("benefitPercent", "benefit_percent"), ("fuel", "fuel"),
        ("registrationDate", "registration_date"), ("ownerEmpid", "owner_empid"),
    ]),
    "ASSIGNMENT.dat": ("assignment", [
        ("asgid", "asgid"), ("empid", "empid"), ("vehid", "vehicle_id"),
        ("startDate", "start_date"), ("endDate", "end_date"), ("reason", "reason"),
    ]),
    "MILECLM.dat": ("mileage_claim", [
        ("clmid", "clmid"), ("empid", "empid"), ("vehid", "vehicle_id"),
        ("claimDate", "claim_date"), ("miles", "miles"), ("status", "status"),
        ("purpose", "purpose"),
    ]),
    "BENPRD.dat": ("benefit_period", [
        ("period", "period"), ("startDate", "start_date"), ("endDate", "end_date"),
        ("mileageRate", "mileage_rate"), ("status", "status"), ("runDate", "run_date"),
    ]),
}
DATE_COLUMNS = {
    "hire_date", "leave_date", "registration_date", "start_date", "end_date",
    "claim_date", "run_date",
}
DECIMAL_COLUMNS = {"monthly_contribution", "list_price", "benefit_percent", "mileage_rate"}
TABLE_ORDER = ("EMPLOYEE.dat", "VEHICLE.dat", "ASSIGNMENT.dat", "MILECLM.dat", "BENPRD.dat")


def coerce(column, value):
    if value == "":
        value = None
    if value is not None and column in DATE_COLUMNS:
        return date.fromisoformat(value)
    if value is not None and column in DECIMAL_COLUMNS:
        return Decimal(value)
    return value


def reject(group, source, table, row, error):
    constraint = getattr(getattr(error, "diag", None), "constraint_name", None)
    constraint = constraint or type(error).__name__
    key = f"{table}.{constraint}"
    entry = group.setdefault(key, {"count": 0, "sampleRows": []})
    entry["count"] += 1
    event = {
        "source": source,
        "table": table,
        "constraint": constraint,
        "row": row,
        "error": str(error),
    }
    if len(entry["sampleRows"]) < 5:
        entry["sampleRows"].append(event)
    print("REJECTED " + json.dumps(event, default=str, sort_keys=True), flush=True)


def insert_idms_row(connection, filename, row):
    table, field_map = TABLES[filename]
    columns = [column for _, column in field_map]
    values = [coerce(column, row[source]) for source, column in field_map]
    if table == "vehicle" and values[-1] == "":
        values[-1] = None
    placeholders = ", ".join(["%s"] * len(columns))
    column_sql = ", ".join(columns)
    connection.execute(
        f"INSERT INTO idms_naive.{table} ({column_sql}) VALUES ({placeholders})",
        values,
    )
    return table


def load_idms(connection):
    loaded = defaultdict(int)
    rejected = {}
    for filename in TABLE_ORDER:
        table = TABLES[filename][0]
        for row in decode_records(UNLOAD / filename):
            try:
                insert_idms_row(connection, filename, row)
                loaded[table] += 1
            except psycopg.Error as error:
                reject(rejected, f"unload/{filename}", table, row, error)
    return dict(loaded), rejected


def execute_seed(connection):
    connection.execute("CREATE SCHEMA jsf_seed")
    connection.execute("SET search_path TO jsf_seed, public")
    for filename in ("001_schema.sql", "002_seed.sql"):
        connection.execute((SEED / filename).read_text(encoding="utf-8"), prepare=False)
    return {
        table: connection.execute(f"SELECT count(*) FROM jsf_seed.{table}").fetchone()[0]
        for table in ("employee", "vehicle", "assignment", "car_request", "car_return", "mileage_claim")
    }


def merge_employees(connection):
    rejected = {}
    inserted = defaultdict(int)
    idms_rows = connection.execute(
        """
        SELECT empid, forename || ' ' || surname AS name, grade, cost_centre,
               location, monthly_contribution
        FROM idms_naive.employee ORDER BY empid
        """
    ).fetchall()
    for employee_no, name, grade, cost_center, site, amount in idms_rows:
        row = {
            "employee_no": employee_no, "name": name, "grade": grade,
            "cost_center": cost_center, "site": site, "amount": amount,
        }
        try:
            connection.execute(
                """
                INSERT INTO global_merge.global_employee
                    (employee_no, name, grade, cost_center, site, amount)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (employee_no, name, grade, cost_center, site, amount),
            )
            inserted["idms"] += 1
        except psycopg.Error as error:
            reject(rejected, "idms_naive.employee", "global_employee", row, error)

    jsf_rows = connection.execute(
        """
        SELECT e.employee_no, e.first_name || ' ' || e.last_name AS name, e.grade,
               e.cost_center, e.site,
               coalesce(sum(m.amount) FILTER (WHERE m.status = 'APPROVED'), 0) AS amount
        FROM jsf_seed.employee AS e
        LEFT JOIN jsf_seed.mileage_claim AS m ON m.employee_id = e.id
        GROUP BY e.id ORDER BY e.employee_no
        """
    ).fetchall()
    for employee_no, name, grade, cost_center, site, amount in jsf_rows:
        row = {
            "employee_no": employee_no, "name": name, "grade": grade,
            "cost_center": cost_center, "site": site, "amount": amount,
        }
        try:
            connection.execute(
                """
                INSERT INTO global_merge.global_employee
                    (employee_no, name, grade, cost_center, site, amount)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (employee_no, name, grade, cost_center, site, amount),
            )
            inserted["jsf"] += 1
        except psycopg.Error as error:
            reject(rejected, "jsf_seed.employee", "global_employee", row, error)
    return dict(inserted), rejected


def rows_as_dicts(cursor):
    names = [column.name for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def run_queries(connection):
    current_cursor = connection.execute(
        """
        SELECT e.empid, e.forename, e.surname, v.plate, a.start_date
        FROM idms_naive.employee AS e
        JOIN idms_naive.assignment AS a ON a.empid = e.empid
        JOIN idms_naive.vehicle AS v ON v.vehid = a.vehicle_id
        WHERE a.end_date IS NULL
        ORDER BY e.empid
        """
    )
    current_cars = rows_as_dicts(current_cursor)
    current_result = {
        "sql": "Current open assignment per employee, joined to its vehicle plate.",
        "rowCount": len(current_cars),
        "sampleRows": current_cars[:20],
    }

    mileage = connection.execute(
        """
        SELECT count(*) AS approved_claims,
               coalesce(sum(m.miles), 0) AS approved_miles,
               coalesce(sum(round(m.miles * p.mileage_rate, 2)), 0) AS reimbursement
        FROM idms_naive.mileage_claim AS m
        JOIN idms_naive.benefit_period AS p
          ON m.claim_date BETWEEN p.start_date AND p.end_date
        WHERE p.period = 202609 AND m.status = 'A'
        """
    ).fetchone()
    output_path = FLEET / "mainframe" / "holdout" / "HP-202609" / "OUT" / "BENOUT.dat"
    expected = decode_records(output_path)
    expected_totals = {
        "records": len(expected),
        "approvedMiles": sum(int(row["miles"]) for row in expected),
        "reimbursement": sum((Decimal(row["reimbursement"]) for row in expected), Decimal(0)),
        "taxableBenefit": sum((Decimal(row["taxableBenefit"]) for row in expected), Decimal(0)),
    }
    naive_totals = {
        "approvedClaims": mileage[0],
        "approvedMiles": mileage[1],
        "reimbursement": mileage[2],
    }
    return {
        "currentCarPerEmployee": current_result,
        "approvedMileage202609": {
            "sql": "Approved claims dated inside benefit_period 202609; reimbursement rounded per claim.",
            "naiveLoad": naive_totals,
            "holdoutHP202609BENOUT": expected_totals,
            "differenceNaiveMinusHoldout": {
                "approvedMiles": naive_totals["approvedMiles"] - expected_totals["approvedMiles"],
                "reimbursement": naive_totals["reimbursement"] - expected_totals["reimbursement"],
            },
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dsn",
        default=os.environ.get(
            "DATABASE_URL", "host=127.0.0.1 port=5432 dbname=gf_parity user=postgres"
        ),
    )
    parser.add_argument("--results", type=Path, default=HERE / "results.json")
    args = parser.parse_args()

    with psycopg.connect(args.dsn, autocommit=True) as connection:
        connection.execute("DROP SCHEMA IF EXISTS idms_naive CASCADE")
        connection.execute("DROP SCHEMA IF EXISTS jsf_seed CASCADE")
        connection.execute("DROP SCHEMA IF EXISTS global_merge CASCADE")
        connection.execute((HERE / "naive_schema.sql").read_text(encoding="utf-8"), prepare=False)
        idms_loaded, idms_rejections = load_idms(connection)
        jsf_counts = execute_seed(connection)
        merge_inserted, merge_rejections = merge_employees(connection)
        queries = run_queries(connection)
        global_merge_count = connection.execute(
            "SELECT count(*) FROM global_merge.global_employee"
        ).fetchone()[0]

    result = {
        "database": {
            "engine": "PostgreSQL 16",
            "hostBinding": "127.0.0.1",
            "image": "mirror.gcr.io/library/postgres:16",
            "noDbkeyColumns": True,
        },
        "idmsUnloadLoad": {
            "loadedByTable": idms_loaded,
            "rejectedRows": sum(row["count"] for row in idms_rejections.values()),
            "rejectedByTableConstraint": idms_rejections,
        },
        "jsfSeedSecondSchema": {"schema": "jsf_seed", "rowCounts": jsf_counts},
        "globalEmployeeMerge": {
            "table": "global_merge.global_employee",
            "amountMapping": {
                "idms_naive.employee": "monthly contribution",
                "jsf_seed.employee": "sum of seeded APPROVED mileage_claim.amount",
            },
            "insertedBySource": merge_inserted,
            "rejectedRows": sum(row["count"] for row in merge_rejections.values()),
            "rejectedByTableConstraint": merge_rejections,
            "finalRows": global_merge_count,
        },
        "businessQueries": queries,
    }
    args.results.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"Wrote {args.results}")


if __name__ == "__main__":
    main()
