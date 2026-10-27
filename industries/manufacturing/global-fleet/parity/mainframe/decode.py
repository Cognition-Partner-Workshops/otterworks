#!/usr/bin/env python3
"""Decode fixed-width Global Fleet unload and BENOUT records."""

import argparse
import json
from datetime import date
from pathlib import Path


LAYOUTS = {
    "EMPLOYEE.dat": (100, [
        ("dbkey", "digits", 10), ("empid", "text", 8), ("surname", "text", 20),
        ("forename", "text", 15), ("grade", "digits", 2), ("costCentre", "text", 6),
        ("hireDate", "date", 8), ("leaveDate", "date", 8), ("status", "text", 1),
        ("contribution", "packed", 4, 7, 2), ("location", "text", 4),
    ]),
    "VEHICLE.dat": (100, [
        ("dbkey", "digits", 10), ("vehid", "text", 8), ("plate", "text", 8),
        ("make", "text", 12), ("model", "text", 16), ("listPrice", "packed", 5, 9, 2),
        ("co2", "digits", 3), ("benefitPercent", "implied", 4, 2), ("fuel", "text", 1),
        ("registrationDate", "date", 8), ("ownerEmpid", "text", 8), ("ownerDbkey", "digits", 10),
    ]),
    "ASSIGNMENT.dat": (64, [
        ("asgid", "text", 10), ("empid", "text", 8), ("employeeDbkey", "digits", 10),
        ("vehid", "text", 8), ("startDate", "date", 8), ("endDate", "date", 8),
        ("reason", "text", 2),
    ]),
    "MILECLM.dat": (64, [
        ("clmid", "text", 10), ("empid", "text", 8), ("employeeDbkey", "digits", 10),
        ("vehid", "text", 8), ("claimDate", "date", 8), ("miles", "digits", 5),
        ("status", "text", 1), ("purpose", "text", 10),
    ]),
    "BENPRD.dat": (40, [
        ("period", "digits", 6), ("startDate", "date", 8), ("endDate", "date", 8),
        ("mileageRate", "implied", 4, 3), ("status", "text", 1), ("runDate", "date", 8),
    ]),
    "BENOUT.dat": (64, [
        ("period", "digits", 6), ("empid", "text", 8), ("employeeDbkey", "digits", 10),
        ("vehid", "text", 8), ("days", "digits", 2), ("taxableBenefit", "packed", 5, 9, 2),
        ("miles", "digits", 6), ("reimbursement", "packed", 5, 9, 2), ("flag", "text", 1),
    ]),
}


def packed_decimal(raw, precision, scale):
    nibbles = []
    for byte in raw:
        nibbles.extend((byte >> 4, byte & 0x0F))
    sign = nibbles.pop()
    digits = nibbles[-precision:]
    if any(nibble > 9 for nibble in digits):
        raise ValueError("invalid COMP-3 digit")
    value = int("".join(str(nibble) for nibble in digits) or "0")
    if sign == 0xD:
        value = -value
    elif sign not in (0xA, 0xC, 0xE, 0xF):
        raise ValueError(f"invalid COMP-3 sign nibble {sign:X}")
    sign_prefix = "-" if value < 0 else ""
    absolute = str(abs(value)).zfill(scale + 1)
    return f"{sign_prefix}{absolute[:-scale]}.{absolute[-scale:]}" if scale else f"{sign_prefix}{absolute}"


def decode_records(path):
    path = Path(path)
    if path.name not in LAYOUTS:
        raise ValueError(f"unknown layout for {path.name}")
    record_length, fields = LAYOUTS[path.name]
    raw = path.read_bytes()
    if len(raw) % record_length:
        raise ValueError(f"{path}: {len(raw)} bytes is not a multiple of LRECL {record_length}")
    records = []
    for record_offset in range(0, len(raw), record_length):
        record = raw[record_offset:record_offset + record_length]
        offset = 0
        decoded = {}
        for field in fields:
            name, kind, width = field[:3]
            chunk = record[offset:offset + width]
            offset += width
            if kind == "text":
                decoded[name] = chunk.decode("ascii").rstrip()
            elif kind == "digits":
                value = chunk.decode("ascii")
                decoded[name] = int(value) if value.strip("0 ") else 0
            elif kind == "date":
                value = chunk.decode("ascii")
                if value == "00000000":
                    decoded[name] = None
                else:
                    decoded[name] = date(int(value[:4]), int(value[4:6]), int(value[6:])).isoformat()
            elif kind == "packed":
                decoded[name] = packed_decimal(chunk, field[3], field[4])
            elif kind == "implied":
                value = chunk.decode("ascii")
                scale = field[3]
                decoded[name] = f"{int(value):0{width}d}"[:-scale] + "." + f"{int(value):0{width}d}"[-scale:]
        records.append(decoded)
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("--out")
    args = parser.parse_args()
    result = {"file": str(args.file), "recordLength": LAYOUTS[Path(args.file).name][0],
              "records": decode_records(args.file)}
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
