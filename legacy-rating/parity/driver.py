#!/usr/bin/env python3
"""Three-way parity driver for the rating estate.

Reads the batch output (RATEOUT fixed width), the quote screen output and the
modern output (both canonical pipe lines), normalises every policy to the same
canonical fields, and compares a keyed SHA-256 per policy and per field.

  driver.py --cobol rated.dat --pharo quoted.txt --java modern.txt --out build/parity.json

Exit 0 when every policy matches on every compared field (or mismatches are
allowed), 1 for mismatches otherwise.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

POS, NEG = "{ABCDEFGHI", "}JKLMNOPQR"

# Fields every channel produces. Endorsements exist only on the quote paths,
# so the batch is compared on rating fields and the quote paths on all of them.
RATING_FIELDS = ["status", "reason", "base", "modified", "minimum", "source"]
QUOTE_FIELDS = RATING_FIELDS + ["endorsements"]


def overpunch(text: str) -> int:
    last = text[-1]
    if last.isdigit():
        return int(text)
    if last in POS:
        return int(text[:-1] + str(POS.index(last)))
    return -int(text[:-1] + str(NEG.index(last)))


def read_cobol(path: Path) -> dict:
    out = {}
    for raw in path.read_text().splitlines():
        r = raw.ljust(80)
        out[r[0:8].strip()] = {
            "status": r[8:11].strip(),
            "reason": r[11:15].strip(),
            "base": overpunch(r[29:40]),
            "modified": overpunch(r[40:51]),
            "minimum": r[51],
            "source": r[28].strip(),
            "total": overpunch(r[56:67]),
        }
    return out


def read_canonical(path: Path) -> dict:
    out = {}
    for raw in path.read_text().splitlines():
        if not raw.strip():
            continue
        f = raw.split("|")
        out[f[0]] = {
            "status": f[1],
            "reason": f[2],
            "base": int(f[3]),
            "modified": int(f[4]),
            "minimum": f[5],
            "endorsements": int(f[6]),
            "total": int(f[8]),
            "source": f[9] if len(f) > 9 else "",
        }
    return out


def keyed_hash(policy: str, row: dict, fields: list) -> str:
    canon = policy + "|" + "|".join(str(row.get(k, "")) for k in fields)
    return hashlib.sha256(canon.encode()).hexdigest()


def compare(left: dict, right: dict, fields: list, names: tuple) -> dict:
    mismatches = []
    for policy in sorted(set(left) | set(right)):
        a, b = left.get(policy), right.get(policy)
        if a is None or b is None:
            mismatches.append({"policy": policy, "missing_in": names[0] if a is None else names[1]})
            continue
        if keyed_hash(policy, a, fields) == keyed_hash(policy, b, fields):
            continue
        diffs = {k: {names[0]: a.get(k), names[1]: b.get(k)} for k in fields if a.get(k) != b.get(k)}
        mismatches.append({"policy": policy, "fields": diffs})
    return {
        "pair": f"{names[0]}~{names[1]}",
        "fields": fields,
        "policies": len(set(left) | set(right)),
        "matched": len(set(left) | set(right)) - len(mismatches),
        "mismatched": len(mismatches),
        "mismatches": mismatches,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cobol", type=Path, required=True)
    ap.add_argument("--pharo", type=Path, required=True)
    ap.add_argument("--java", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--allow-mismatches", action="store_true", help="Report mismatches without failing")
    args = ap.parse_args()

    cobol, pharo, java = read_cobol(args.cobol), read_canonical(args.pharo), read_canonical(args.java)
    pairs = [
        compare(cobol, java, RATING_FIELDS, ("cobol", "java")),
        compare(pharo, java, QUOTE_FIELDS, ("pharo", "java")),
        compare(cobol, pharo, RATING_FIELDS, ("cobol", "pharo")),
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"pairs": pairs}, indent=2) + "\n")
    for p in pairs:
        print(f"PARITY {p['pair']} policies={p['policies']} matched={p['matched']} mismatched={p['mismatched']}")
    return 0 if args.allow_mismatches or all(p["mismatched"] == 0 for p in pairs) else 1


if __name__ == "__main__":
    sys.exit(main())
