import argparse
import sys
from pathlib import Path
from xml.etree import ElementTree


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize JUnit evidence and reject empty runs.")
    parser.add_argument("reports", nargs="+", type=Path)
    args = parser.parse_args()
    print("| Suite | Passed | Failed | Errors | Skipped |")
    print("| --- | ---: | ---: | ---: | ---: |")
    valid = True
    for report in args.reports:
        try:
            cases = ElementTree.parse(report).findall(".//testcase")
        except (OSError, ElementTree.ParseError) as exc:
            print(f"| {report.stem} | — | — | — | — |")
            print(f"{report}: {exc}", file=sys.stderr)
            valid = False
            continue
        counts = [sum(case.find(tag) is not None for case in cases) for tag in ("failure", "error", "skipped")]
        failures, errors, skipped = counts
        passed = len(cases) - sum(counts)
        print(f"| {report.stem} | {passed} | {failures} | {errors} | {skipped} |")
        if passed + failures == 0:
            print(f"{report}: no test bodies executed", file=sys.stderr)
        valid &= (passed + failures > 0 and failures == 0 and errors == 0)
    return 0 if valid else 1


if __name__ == "__main__":
    sys.exit(main())
