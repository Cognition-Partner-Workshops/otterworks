#!/usr/bin/env python3
"""Check captured VM sha256sum files and live Moto objects against fixtures."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from compare import normalise
from parity import FIXTURES


def vm_hashes(path):
    result = {}
    for line in path.read_text().splitlines():
        digest, filename = line.split(None, 1)
        key = normalise(filename.strip().removeprefix("/var/kyc/uploads/"))
        if key in result:
            raise ValueError("duplicate normalised object: " + key)
        result[key] = digest
    return result


def expected_hashes():
    result = {}
    for customer in ("HG611000001", "HG621000002"):
        for kind, extension, fixture in (
                ("passport", "pdf", "passport.pdf"), ("id-card", "jpg", "id-card.jpg"),
                ("proof-of-address", "png", "address.png"), ("payslip", "jpeg", "payslip.JPEG")):
            result[f"{customer}/{kind}-<millis>.{extension}"] = hashlib.sha256(FIXTURES[fixture]).hexdigest()
    for kind, fixture in (("passport", "notes.exe"), ("id-card", "no-extension")):
        result[f"HG611000001/{kind}-<millis>.bin"] = hashlib.sha256(FIXTURES[fixture]).hexdigest()
    return result


def verify(vm, branch, out):
    code = """
import boto3, hashlib, json
s3 = boto3.client("s3", endpoint_url="http://127.0.0.1:9000")
result = {}
for page in s3.get_paginator("list_objects_v2").paginate(Bucket="kyc-docs"):
    for obj in page.get("Contents", []):
        key = obj["Key"]
        data = s3.get_object(Bucket="kyc-docs", Key=key)["Body"].read()
        result[key] = hashlib.sha256(data).hexdigest()
print(json.dumps(result))
"""
    raw = json.loads(subprocess.check_output(
        ["kubectl", "exec", "-n", "deps", "deployment/s3", "--", "python", "-c", code]))
    s3 = {normalise(key): digest for key, digest in raw.items()}
    if len(s3) != len(raw):
        raise ValueError("duplicate normalised S3 objects")
    expected = expected_hashes()
    actual = {"vm": vm_hashes(vm), "vm-branch": vm_hashes(branch), "container": s3}
    passed = all(hashes == expected for hashes in actual.values())
    evidence = {"pass": passed, "expected": expected, "actual": actual, "s3_raw": raw}
    out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    for name, hashes in actual.items():
        print(f"{name}: {len(hashes)} objects; fixture SHA-256 {'PASS' if hashes == expected else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vm-sha", type=Path, required=True)
    parser.add_argument("--vm-branch-sha", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(verify(args.vm_sha, args.vm_branch_sha, args.out))
