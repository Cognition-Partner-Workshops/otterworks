import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.request
import zlib


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
OPERATIONS = ("summary", "values", "funds")


def get_json(url):
    try:
        response = urllib.request.urlopen(url, timeout=30)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read().decode("utf-8")
        return response.status, json.loads(raw), raw


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def record(args):
    out = args.out
    if out.exists() and any(out.iterdir()) and not args.force:
        raise ValueError(f"refusing to overwrite existing frozen set: {out}; use --force")
    url = (args.legacy_url or
           f"http://127.0.0.1:{18080 + zlib.crc32(args.namespace.encode()) % 1000}").rstrip("/")
    status, listing, _ = get_json(url + "/pinq/v1/contracts")
    if status != 200 or listing.get("RTN_CD") != "00":
        raise ValueError(f"contract listing failed: HTTP {status}, {listing}")
    contracts = [str(listing[f"CNTR_NO_{i:03d}"])
                 for i in range(1, int(listing["CNTR_CNT"]) + 1)]
    if not contracts:
        raise ValueError("contract listing is empty; cannot record the zero-padded case")
    if any(not re.fullmatch(r"[0-9]+", number) for number in contracts):
        raise ValueError("contract listing contains a non-digit contract number")
    cases = [(f"contract-{number}", number) for number in contracts]
    cases += [("unknown", "9999999999"), ("non-numeric", "ABC123"),
              ("zero-padded", contracts[0].zfill(max(10, len(contracts[0]) + 1)))]
    files = {}
    counts = {}
    for operation in OPERATIONS:
        records = []
        for case_id, number in cases:
            path = f"/pinq/v1/{operation}/{number}"
            status, body, raw = get_json(url + path)
            records.append(dict(case_id=f"{operation}-{case_id}", operation=operation,
                                policy_number=number, path=path, status=status,
                                body=body, raw=raw))
        files[f"{operation}.json"] = encode(records)
        counts[operation] = {"cases": len(records), "statuses": dict(sorted(
            Counter(str(case["status"]) for case in records).items()))}
    source_paths = [f"services/industry-solutions/insurance/db/annuity/{name}"
                    for name in ("01_tables.sql", "02_seed.sql")]
    manifest = {
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "legacy_source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "sha256": {name: sha256(data) for name, data in files.items()},
        "source_sha256": {path: sha256((REPO / path).read_bytes()) for path in source_paths},
        "contract_count": len(contracts),
        "operations": counts,
    }
    out.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (out / name).write_bytes(data)
    (out / "MANIFEST.json").write_bytes(encode(manifest))
    print(f"Recorded {len(contracts)} contracts from {url}")
    for operation, count in counts.items():
        print(f"{operation}: {count['cases']} cases; statuses {json.dumps(count['statuses'])}")
    print(f"Frozen set: {out}")


def main():
    parser = argparse.ArgumentParser(description="Freeze legacy policy inquiry responses")
    parser.add_argument("namespace")
    parser.add_argument("--legacy-url")
    parser.add_argument("--out", type=Path, default=ROOT / "parity" / "frozen")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.namespace):
        parser.error("namespace must contain only letters, digits, underscores or hyphens")
    try:
        record(args)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Recording failed: {error}\n")


if __name__ == "__main__":
    main()
