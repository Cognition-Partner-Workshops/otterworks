#!/usr/bin/env python3
"""Compare parity captures using only the two permitted normalisations."""
import argparse
import json
from pathlib import Path
import re


def normalise(body):
    body = re.sub(r"(passport|id-card|proof-of-address|payslip)-[0-9]{13}\.",
                  r"\1-<millis>.", body)
    return re.sub(r'("timestamp":")([^"]*)(")',
                  lambda m: m[1] + re.sub(r"[0-9]", "0", m[2]) + m[3], body)


def compare(a, b):
    left = json.loads((a / "cases.json").read_text())
    right = json.loads((b / "cases.json").read_text())
    failed = 0
    print("case | A status | B status | content-type A / B | equal")
    for filename in dict.fromkeys(left + right):
        if filename not in left or filename not in right:
            print(f"{filename} | MISSING CASE")
            failed += 1
            continue
        x = json.loads((a / filename).read_text())
        y = json.loads((b / filename).read_text())
        equal = (all(x[k] == y[k] for k in ("case", "method", "path", "status", "content_type"))
                 and normalise(x["body"]).encode("utf-8") == normalise(y["body"]).encode("utf-8"))
        print(f"{x['case']} | {x['status']} | {y['status']} | {x['content_type']} / {y['content_type']} | {'PASS' if equal else 'FAIL'}")
        if not equal:
            failed += 1
            print("  A body: " + normalise(x["body"]))
            print("  B body: " + normalise(y["body"]))
    if left != right:
        print("Case indexes differ (including order)")
        failed += 1
    print(f"Result: {len(left) - failed}/{len(left)} equal; {failed} differences")
    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("a", type=Path)
    parser.add_argument("b", type=Path)
    args = parser.parse_args()
    raise SystemExit(compare(args.a, args.b))
