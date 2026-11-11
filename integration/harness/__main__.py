from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .faults import TESTS
from .fingerprints import LOCK, record_lock, verify_lock
from .report import write_report
from .runner import replay


def main(argv=None):
    parser = argparse.ArgumentParser(description="Locked integration corpus replay")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("replay", "fault", "verify-lock", "record-lock"):
        command = commands.add_parser(name)
        command.add_argument("--corpus", type=Path, required=True)
        if name in ("replay", "fault"):
            command.add_argument("--flow", action="append", default=[])
            command.add_argument("--report-dir", type=Path, required=True)
        if name == "fault":
            command.add_argument("--test", choices=TESTS, required=True)
        if name == "record-lock":
            command.add_argument("--reason", required=True)
    report = commands.add_parser("report")
    report.add_argument("--input", type=Path, required=True)
    report.add_argument("--report-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "record-lock":
            record_lock(args.corpus, args.reason)
        elif args.command == "verify-lock":
            verify_lock(args.corpus)
            print("Corpus lock verified")
        else:
            if args.command == "report":
                target = args.report_dir.resolve()
                if any((parent / LOCK).exists() for parent in (target, *target.parents)):
                    raise ValueError("Reports must be outside the frozen corpus")
                result = json.loads(args.input.read_text())
            else:
                if args.report_dir.resolve().is_relative_to(args.corpus.resolve()):
                    raise ValueError("Reports must be outside the frozen corpus")
                result = replay(args.corpus, args.flow, getattr(args, "test", None))
            write_report(result, args.report_dir)
            print(f"Wrote parity.json, parity.html and parity.md to {args.report_dir}")
            return int(any(row["status"] != "matched" for row in result["flows"]))
    except (ValueError, OSError, KeyError) as exc:
        print(f"Harness refused operation ({type(exc).__name__}); check corpus and configuration", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
