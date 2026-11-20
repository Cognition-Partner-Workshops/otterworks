"""Generate next-day vendor schema drift without changing the loader."""
import argparse
import csv

from break_upstream import generate
from load_daily import ROOT


def generate_drift(column="CUSTOMER_ID"):
    day = generate()
    path = ROOT / "landing" / f"{day}.csv"
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        header = reader.fieldnames
        records = list(reader)
    for row in records:
        if column == "CUSTOMER_ID":
            row[column] = f"CUST-{int(row[column]):04d}"
        else:
            row[column] = day.strftime("%m/%d/%Y")
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=header)
        writer.writeheader()
        writer.writerows(records)
    print(f"{path}: added DISCOUNT_CODE; changed {column} to vendor text format")
    return day


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--column", choices=["CUSTOMER_ID", "USAGE_DATE"], default="CUSTOMER_ID")
    generate_drift(parser.parse_args().column)
