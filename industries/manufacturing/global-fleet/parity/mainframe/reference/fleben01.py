#!/usr/bin/env python3
"""Straight Python reference port of the FLEBEN01 batch calculation."""

import argparse
import sys
from datetime import date
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from decode import decode_records


def parse_date(value):
    return date.fromisoformat(value) if value else None


def pack_decimal(value, precision=9, scale=2):
    value = Decimal(str(value))
    scaled = int((value * (10 ** scale)).to_integral_value(rounding=ROUND_DOWN))
    digits = str(abs(scaled)).zfill(precision)
    if len(digits) > precision:
        raise ValueError(f"COMP-3 overflow: {value}")
    nibbles = [int(char) for char in digits] + [0xD if scaled < 0 else 0xC]
    if len(nibbles) % 2:
        nibbles.insert(0, 0)
    packed = bytearray()
    for index in range(0, len(nibbles), 2):
        packed.append((nibbles[index] << 4) | nibbles[index + 1])
    return bytes(packed)


def edited(value, width):
    return f"{value:,.2f}".rjust(width)


def report_lines(period, rows, total_taxable, total_reimbursed):
    first = "1FLEBEN01  MONTHLY COMPANY CAR BENEFIT RUN".ljust(58) + "PERIOD "
    first += f"{period // 100:04d}-{period % 100:02d}"
    lines = [
        first,
        " EMP-ID   DBKEY      VEH-ID   DAYS   TAXABLE-BEN  MILES     MILE-REIM  F",
        " -------- ---------- -------- ---- ------------- ------ ------------- -",
    ]
    for row in rows:
        detail = (
            f" {row['empid']:<8} {row['employeeDbkey']:010d} {row['vehid']:<8} "
            f"{row['days']:>4} {edited(row['taxableBenefit'], 13)} {row['miles']:>6} "
            f"{edited(row['reimbursement'], 13)} {row['flag'] or ' '}"
        )
        lines.append(detail)
    total = (
        " RECORDS WRITTEN " + f"{len(rows):>6}" +
        "   TOTAL TAXABLE " + f"{total_taxable:,.2f}".rjust(15) +
        "   TOTAL REIMBURSED " + f"{total_reimbursed:,.2f}".rjust(13)
    )
    lines.append(total)
    return ("\n".join(lines) + "\n").encode("ascii")


def run(input_dir, output_dir, period):
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    employees = decode_records(input_dir / "EMPLOYEE.dat")
    vehicles = {row["vehid"]: row for row in decode_records(input_dir / "VEHICLE.dat")}
    assignments = decode_records(input_dir / "ASSIGNMENT.dat")
    claims = decode_records(input_dir / "MILECLM.dat")
    benefit_period = next(
        row for row in decode_records(input_dir / "BENPRD.dat") if int(row["period"]) == period
    )
    start = parse_date(benefit_period["startDate"])
    end = parse_date(benefit_period["endDate"])
    month_days = (end - start).days + 1
    mileage_rate = Decimal(benefit_period["mileageRate"])
    rows = []
    for employee in employees:
        hire = parse_date(employee["hireDate"])
        leave = parse_date(employee["leaveDate"])
        if hire > end or (leave is not None and leave < start):
            continue
        assigned = [
            item for item in assignments
            if int(item["employeeDbkey"]) == int(employee["dbkey"])
            and parse_date(item["startDate"]) <= end
        ]
        assigned.sort(key=lambda item: parse_date(item["startDate"]), reverse=True)
        vehicle_id = ""
        days = 0
        taxable = Decimal(0)
        if assigned:
            assignment = assigned[0]
            assignment_end = parse_date(assignment["endDate"])
            if assignment_end is None or assignment_end >= start:
                vehicle = vehicles[assignment["vehid"]]
                from_date = max(parse_date(assignment["startDate"]), start)
                to_date = min(end, assignment_end or end, leave or end)
                if to_date >= from_date:
                    days = (to_date - from_date).days + 1
                    vehicle_id = assignment["vehid"]
                    taxable = (
                        Decimal(vehicle["listPrice"]) * Decimal(vehicle["benefitPercent"]) / Decimal(1200)
                        - Decimal(employee["contribution"])
                    ) * Decimal(days) / Decimal(month_days)
                    if taxable < 0:
                        taxable = Decimal(0)
                    taxable = taxable.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        if days == 0:
            vehicle_id = ""
        claim_rows = [
            claim for claim in claims
            if int(claim["employeeDbkey"]) == int(employee["dbkey"])
            and claim["status"] == "A"
            and start <= parse_date(claim["claimDate"]) <= end
        ]
        miles = sum(int(claim["miles"]) for claim in claim_rows)
        reimbursement = sum(
            (Decimal(int(claim["miles"])) * mileage_rate).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            for claim in claim_rows
        )
        if days or miles:
            flag = "L" if leave is not None and start <= leave <= end else ""
            rows.append({
                "period": period, "empid": employee["empid"], "employeeDbkey": int(employee["dbkey"]),
                "vehid": vehicle_id, "days": days, "taxableBenefit": taxable,
                "miles": miles, "reimbursement": reimbursement, "flag": flag,
            })
    out_records = []
    for row in rows:
        out_records.append(
            f"{period:06d}".encode("ascii")
            + row["empid"].encode("ascii").ljust(8)
            + f"{row['employeeDbkey']:010d}".encode("ascii")
            + row["vehid"].encode("ascii").ljust(8)
            + f"{row['days']:02d}".encode("ascii")
            + pack_decimal(row["taxableBenefit"], 9, 2)
            + f"{row['miles']:06d}".encode("ascii")
            + pack_decimal(row["reimbursement"], 9, 2)
            + (row["flag"] or " ").encode("ascii")
            + b" " * 13
        )
    output = b"".join(out_records)
    total_taxable = sum((row["taxableBenefit"] for row in rows), Decimal(0))
    total_reimbursed = sum((row["reimbursement"] for row in rows), Decimal(0))
    (output_dir / "BENOUT.dat").write_bytes(output)
    (output_dir / "BENRPT.txt").write_bytes(
        report_lines(period, rows, total_taxable, total_reimbursed)
    )
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="input_dir", required=True)
    parser.add_argument("--out", dest="output_dir", required=True)
    parser.add_argument("--period", required=True, type=int)
    args = parser.parse_args()
    run(args.input_dir, args.output_dir, args.period)


if __name__ == "__main__":
    main()
