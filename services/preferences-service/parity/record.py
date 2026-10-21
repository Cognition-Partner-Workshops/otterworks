#!/usr/bin/env python3
"""Record the legacy-portal request corpus against a running target into a transcript.

Uses the same request sender as services/legacy-portal/parity/replay.py, and writes the
java-reference.json shape, so the output can be passed back to replay.py with --java-capture.

  python3 record.py --base http://localhost:8095 --out transcripts/monolith-main.json

The corpus is ordered and stateful: point it at a target whose schemas are empty.
"""
import argparse
import json
import sys
from pathlib import Path

PARITY = Path(__file__).resolve().parents[2] / "legacy-portal" / "parity"
sys.path.insert(0, str(PARITY))
import replay  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--requests", default=str(PARITY / "requests.json"))
    ap.add_argument("--context", action="append", help="common|announcements|preferences|feedback|all")
    ap.add_argument("--timeout", type=float, default=30.0)
    args = ap.parse_args()

    failures = replay.verify_checksums(Path(args.requests).resolve().parent)
    if failures:
        print("corpus checksum mismatch, refusing to record:", *failures, sep="\n  ", file=sys.stderr)
        return 3

    contexts = replay.parse_contexts(args.context)
    cases = [c for c in json.loads(Path(args.requests).read_text())["cases"] if c["context"] in contexts]
    recorded = []
    for ctx in contexts:
        for case in (c for c in cases if c["context"] == ctx):
            response, _ = replay.send(args.base, case, args.timeout)
            recorded.append({"id": case["id"], "context": ctx, "method": case["method"],
                             "path": case["path"], "response": response})
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"base": args.base, "cases": recorded}, indent=2, ensure_ascii=False) + "\n")
    print(f"recorded {len(recorded)} cases from {args.base} into {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
