import argparse
import json
import sys
from pathlib import Path
from xml.etree import ElementTree


def read_counts(format_name: str, path: Path) -> tuple[int, int]:
    if format_name == "cobertura":
        root = ElementTree.parse(path).getroot()
        return int(root.attrib["lines-covered"]), int(root.attrib["lines-valid"])
    if format_name == "jacoco":
        line = ElementTree.parse(path).find("./counter[@type='LINE']")
        if line is None:
            raise ValueError("JaCoCo report has no aggregate line counter")
        covered = int(line.attrib["covered"])
        return covered, covered + int(line.attrib["missed"])
    if format_name == "lcov":
        counts = {"LH": 0, "LF": 0}
        for line in path.read_text().splitlines():
            key, _, value = line.partition(":")
            if key in counts:
                counts[key] += int(value)
        return counts["LH"], counts["LF"]
    if format_name == "go":
        header, *lines = path.read_text().splitlines()
        if not header.startswith("mode: "):
            raise ValueError("invalid Go coverage profile")
        covered = total = 0
        for line in lines:
            _, statements, hits = line.rsplit(maxsplit=2)
            total += int(statements)
            if int(hits) > 0:
                covered += int(statements)
        return covered, total
    raise ValueError(f"unsupported coverage format: {format_name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Write one coverage summary row and enforce its floor.")
    parser.add_argument("service")
    parser.add_argument("report", type=Path)
    parser.add_argument("--tests", required=True, choices=("success", "failure", "skipped", "cancelled"))
    args = parser.parse_args()
    floors = json.loads(Path(__file__).with_name("coverage-floors.json").read_text())
    config = floors[args.service]
    floor = config["minimum"]
    target = f"{floor:g}%"
    note = " (non-blocking baseline)" if args.service in {"admin-dashboard", "document-service"} else ""
    try:
        covered, total = read_counts(config["format"], args.report)
        if not 0 <= covered <= total or total == 0:
            raise ValueError(f"invalid coverage counts: {covered}/{total}")
        percentage = 100 * covered / total
    except (OSError, ValueError, KeyError, ElementTree.ParseError) as exc:
        print(f"| {args.service} | {config['metric']} | — | {target} | Report unavailable{note} |")
        print(f"{args.report}: {exc}", file=sys.stderr)
        return 1
    meets_floor = 100 * covered >= floor * total
    status = args.tests + note + ("" if meets_floor else "; below floor")
    print(f"| {args.service} | {config['metric']} | {percentage:.2f}% | {target} | {status} |")
    return 0 if meets_floor and args.tests == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
