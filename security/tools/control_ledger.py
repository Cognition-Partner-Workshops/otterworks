import argparse
import collections
import sys

from control_report import load, report


STATUSES = ("closed", "held", "amber")
FIELDS = ("control", "owner", "before", "after", "approved_path", "status")


def ledger(documents):
    rows = []
    seen = set()
    counts = collections.Counter()
    for row in documents:
        control, owner, before, after, approved_path, status = (row[key] for key in FIELDS)
        if not control or control in seen or status not in STATUSES:
            raise ValueError(f"missing/duplicate control or invalid status: {control!r}")
        evidence = row["evidence"]
        if not evidence or set(evidence) - {"commit", "plan", "read"} or not all(evidence.values()):
            raise ValueError(f"{control}: provide commit, plan, or read evidence")
        for name, check in (("before", before), ("after", after), ("approved_path", approved_path)):
            if check["result"] not in ("pass", "fail", "not-run") or not check["reference"]:
                raise ValueError(f"{control}: invalid {name} check")
        if status == "closed" and (not owner or after["result"] != "pass" or approved_path["result"] != "pass"):
            raise ValueError(f"{control}: closing requires an owner, a passing after check, and a passing approved path")
        seen.add(control)
        counts[status] += 1
        rows.append({key: row[key] for key in (*FIELDS, "evidence")})
    return sorted(rows, key=lambda row: row["control"]), {status: counts[status] for status in STATUSES}


def main():
    parser = argparse.ArgumentParser(description="Generate a control ledger from individual evidence files")
    parser.add_argument("evidence", nargs="+", help="One YAML or JSON file per control")
    parser.add_argument("--output", required=True, help="Path stem for JSON and Markdown")
    args = parser.parse_args()
    try:
        rows, counts = ledger([load(path) for path in args.evidence])
        columns = [("control", "Control"), ("owner", "Owner"), ("evidence", "Evidence"),
                   ("before", "Before"), ("after", "After"), ("approved_path", "Approved path"), ("status", "Status")]
        report(args.output, "Cloud control ledger", rows, columns, counts)
        return 0
    except (KeyError, ValueError, OSError) as error:
        print(f"Ledger did not run: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
