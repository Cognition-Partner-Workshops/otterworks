import argparse
import json
from pathlib import Path


def summarize(path: Path, expect_empty=False):
    rows = json.loads(path.read_text())["flows"]
    for row in rows:
        print(f'{row["flow"]}: {row["status"]} replayed={row["replayed"]} matched={row["matched"]} differing={row["differing"]}')
    print(f'{len(rows)} flows; {sum(r["status"] == "matched" for r in rows)} matched; '
          f'{sum(r["status"] == "differing" for r in rows)} differing; '
          f'{sum(r["status"] == "error" for r in rows)} errors')
    if expect_empty and (len(rows) != 24 or any(r["status"] != "differing" or r["matched"] for r in rows)):
        raise SystemExit("Empty-target baseline must show 24 differing flows and no transport errors")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--expect-empty", action="store_true")
    args = parser.parse_args()
    summarize(args.path, args.expect_empty)
