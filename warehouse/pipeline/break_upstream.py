"""Emit the vendor's next-day currency-formatted, expanded feed."""
import csv
from datetime import timedelta

from load_daily import GOOD_DATE, ROOT, load


def generate():
    day = GOOD_DATE + timedelta(days=1)
    with (ROOT / "landing" / f"{GOOD_DATE}.csv").open(newline="") as source:
        rows = list(csv.reader(source))
    header, *records = rows
    header.insert(8, "DISCOUNT_CODE")
    for index, row in enumerate(records):
        row[0] = str(int(row[0]) + 1000)
        row[3] = f"INV-2026-{int(row[0]):06d}"
        row[4] = day.isoformat()
        row[7] = f"${float(row[7]):,.2f}"
        row[9] = f"{day}T23:00:00"
        row.insert(8, "LOYALTY10" if index % 8 == 0 else "")
    with (ROOT / "landing" / f"{day}.csv").open("w", newline="") as target:
        csv.writer(target).writerows([header, *records])
    return day


if __name__ == "__main__":
    load(generate(), "load_break")
