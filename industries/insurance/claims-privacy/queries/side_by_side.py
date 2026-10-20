#!/usr/bin/env python3
"""Print the claims_reader and claims_adjuster results of the same query side by side.

    side_by_side.py reader.csv adjuster.csv            # terminal table
    side_by_side.py reader.csv adjuster.csv --markdown # PR body table
"""
import csv
import sys


def rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def main():
    reader, adjuster = rows(sys.argv[1]), rows(sys.argv[2])
    markdown = "--markdown" in sys.argv
    assert [r["claim_number"] for r in reader] == [a["claim_number"] for a in adjuster], "row sets differ"
    fields = [k for k in reader[0] if k != "claim_number"]
    table = [("claim_number", "column", "claims_reader", "claims_adjuster")]
    for r, a in zip(reader, adjuster):
        for f in fields:
            table.append((r["claim_number"], f, r[f], a[f]))
    if markdown:
        print("| " + " | ".join(table[0]) + " |")
        print("|" + "---|" * 4)
        for row in table[1:]:
            print("| " + " | ".join(f"`{c}`" if i >= 2 and c else c for i, c in enumerate(row)) + " |")
    else:
        widths = [max(len(row[i]) for row in table) for i in range(4)]
        for n, row in enumerate(table):
            print("  ".join(c.ljust(w) for c, w in zip(row, widths)))
            if n == 0:
                print("  ".join("-" * w for w in widths))
    print(f"\n{len(reader)} rows per role, {len(fields)} PII columns each; "
          f"{sum(1 for r, a in zip(reader, adjuster) for f in fields if r[f] != a[f])} cells differ.")


if __name__ == "__main__":
    main()
