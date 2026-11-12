"""Record every legacy inquiry response for every contract as the frozen parity set.

Usage: python3 parity/capture.py <namespace>
Writes parity/frozen/<operation>/<contract>.json and parity/frozen/manifest.json.
"""
import hashlib
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request
import zlib

OPERATIONS = ("summary", "values", "funds")


def fetch(url):
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def main():
    namespace = sys.argv[1] if len(sys.argv) > 1 else "iri"
    base = f"http://127.0.0.1:{18080 + zlib.crc32(namespace.encode()) % 1000}/pinq/v1"
    out = Path(__file__).resolve().parent / "frozen"
    status, raw = fetch(f"{base}/contracts")
    listing = json.loads(raw)
    if status != 200 or listing.get("RTN_CD") != "00":
        raise SystemExit(f"contract listing failed: HTTP {status} {listing}")
    contracts = [listing[k] for k in sorted(k for k in listing if k.startswith("CNTR_NO_"))]
    if len(contracts) != int(listing["CNTR_CNT"]):
        raise SystemExit("CNTR_CNT does not match the listed contracts")
    manifest = {"source": "legacy /pinq/v1", "contracts": contracts, "operations": {}}
    for op in OPERATIONS:
        (out / op).mkdir(parents=True, exist_ok=True)
        counts = {}
        for contract in contracts:
            status, raw = fetch(f"{base}/{op}/{contract}")
            record = {"operation": op, "contract": contract, "request": f"GET /pinq/v1/{op}/{contract}",
                      "status": status, "rawSha256": hashlib.sha256(raw).hexdigest(),
                      "body": json.loads(raw)}
            (out / op / f"{contract}.json").write_text(json.dumps(record, indent=2) + "\n")
            counts[str(status)] = counts.get(str(status), 0) + 1
        manifest["operations"][op] = {"responses": len(contracts), "byStatus": counts}
        print(f"{op:8s} {len(contracts)} responses {counts}")
    manifest["total"] = sum(o["responses"] for o in manifest["operations"].values())
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"frozen parity set: {manifest['total']} responses for {len(contracts)} contracts -> {out}")


if __name__ == "__main__":
    main()
