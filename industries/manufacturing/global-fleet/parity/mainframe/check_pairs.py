#!/usr/bin/env python3
"""Validate committed holdout metadata and optionally compare a candidate run."""

import argparse
import hashlib
import json
import shlex
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path

from build_pairs import HOLDOUT, REPO, read_sha_manifest, relationship, report_totals
from decode import LAYOUTS, decode_records

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_metadata():
    failures = []
    pairs = json.loads((HERE / "pairs.json").read_text(encoding="utf-8"))
    manifest = read_sha_manifest()
    manifest_failures = []
    for relative, expected in manifest.items():
        path = HOLDOUT / relative
        actual = digest(path) if path.is_file() else None
        if actual != expected:
            manifest_failures.append(f"{relative}: expected {expected}, got {actual}")
    metadata_entries = {}
    for pair in pairs["pairs"]:
        for direction in ("input", "expectedOutput"):
            for filename, entry in pair[direction].items():
                relative = entry["path"]
                manifest_path = Path(relative).relative_to(HOLDOUT.relative_to(REPO)).as_posix()
                metadata_entries[manifest_path] = (entry, pair, direction, filename)
                actual = digest(REPO / relative)
                if actual != entry["sha256"]:
                    failures.append(f"{relative}: pairs.json checksum mismatch")
                if manifest_path in manifest and manifest[manifest_path] != entry["sha256"]:
                    failures.append(f"{manifest_path}: pairs.json and PAIRS.sha256 disagree")
                if filename.endswith(".dat"):
                    count = len((REPO / relative).read_bytes()) // LAYOUTS[filename][0]
                    if count != entry.get("recordCount"):
                        failures.append(f"{relative}: record count mismatch")
        for filename, relation in pair["relationToCurrentUnload"].items():
            actual = relationship(
                HOLDOUT / pair["id"] / "IN" / filename,
                HOLDOUT.parents[0] / "unload" / filename,
                filename,
            )
            if actual != relation:
                failures.append(f"{pair['id']} {filename}: unload relation mismatch")
        benout_path = REPO / pair["expectedOutput"]["BENOUT.dat"]["path"]
        report_path = REPO / pair["expectedOutput"]["BENRPT.txt"]["path"]
        output_rows = decode_records(benout_path)
        output_taxable = sum((Decimal(row["taxableBenefit"]) for row in output_rows), Decimal(0))
        output_reimbursed = sum((Decimal(row["reimbursement"]) for row in output_rows), Decimal(0))
        totals = report_totals(report_path)
        if len(output_rows) != totals["recordsWritten"] or len(output_rows) != totals["detailRows"]:
            failures.append(f"{pair['id']}: BENOUT and BENRPT row counts disagree")
        if f"{output_taxable:.2f}" != totals["totalTaxable"]:
            failures.append(f"{pair['id']}: BENOUT and BENRPT taxable totals disagree")
        if f"{output_reimbursed:.2f}" != totals["totalReimbursed"]:
            failures.append(f"{pair['id']}: BENOUT and BENRPT reimbursement totals disagree")
        consistency = pair["consistency"]
        if not all(consistency[name] for name in (
            "recordCountMatches", "taxableMatches", "reimbursedMatches", "detailRowsMatch"
        )):
            failures.append(f"{pair['id']}: internal consistency failed")
    not_holdout = pairs.get("notHoldout", [])
    if len(not_holdout) != 1 or not_holdout[0].get("period") != 202610 \
            or not_holdout[0].get("expectedOutput") is not None:
        failures.append("202610 must be listed as notHoldout with no expected output")
    if set(metadata_entries) != set(manifest):
        failures.append("pairs.json and PAIRS.sha256 list different file sets")
    print("| What compared | Before value | After value | Result |")
    print("|---|---|---|---|")
    print(f"| PAIRS.sha256 files | {len(manifest)} listed | {len(manifest) - len(manifest_failures)} verified | "
          f"{'identical' if not manifest_failures else 'failed'} |")
    print(f"| pairs.json entries | {len(metadata_entries)} | checksums/counts/consistency checked | "
          f"{'identical' if not failures else 'failed'} |")
    return pairs, failures + manifest_failures


def run_candidate(template, pairs):
    failures = []
    print("| What compared | Before value | After value | Result |")
    print("|---|---|---|---|")
    for pair in pairs["pairs"]:
        period = pair["period"]
        with tempfile.TemporaryDirectory(prefix=f"gf-{period}-") as temporary:
            output_dir = Path(temporary) / "OUT"
            output_dir.mkdir()
            input_dir = REPO / pair["input"]["BENPRD.dat"]["path"]
            input_dir = input_dir.parent
            command = shlex.split(template.format(**{
                "in": str(input_dir), "out": str(output_dir), "period": period
            }))
            completed = subprocess.run(command, cwd=REPO, text=True, capture_output=True)
            if completed.returncode:
                failures.append(f"{pair['id']}: candidate exit {completed.returncode}: {completed.stderr.strip()}")
            for filename in ("BENOUT.dat", "BENRPT.txt"):
                expected = REPO / pair["expectedOutput"][filename]["path"]
                actual = output_dir / filename
                before = digest(expected)
                after = digest(actual) if actual.is_file() else "missing"
                result = "identical" if before == after else "failed"
                print(f"| {pair['id']} {filename} | `{before[:12]}` | `{after[:12]}` | {result} |")
                if result != "identical":
                    if actual.is_file():
                        expected_data = expected.read_bytes()
                        actual_data = actual.read_bytes()
                        difference = next(
                            (index for index, values in enumerate(zip(expected_data, actual_data))
                             if values[0] != values[1]),
                            min(len(expected_data), len(actual_data)),
                        )
                        if filename == "BENOUT.dat":
                            record_length = LAYOUTS[filename][0]
                            record_number = difference // record_length
                            before_rows = decode_records(expected)
                            after_rows = decode_records(actual)
                            before_row = before_rows[record_number] if record_number < len(before_rows) else None
                            after_row = after_rows[record_number] if record_number < len(after_rows) else None
                            detail = (
                                f"first differing record {record_number + 1}: "
                                f"before={before_row}, after={after_row}"
                            )
                        else:
                            before_lines = expected_data.decode("ascii", errors="replace").splitlines()
                            after_lines = actual_data.decode("ascii", errors="replace").splitlines()
                            line_number = difference // 133 + 1
                            before_line = before_lines[line_number - 1] if line_number <= len(before_lines) else None
                            after_line = after_lines[line_number - 1] if line_number <= len(after_lines) else None
                            detail = (
                                f"first differing report line {line_number}: "
                                f"before={before_line!r}, after={after_line!r}"
                            )
                    else:
                        detail = "candidate output file is missing"
                    failures.append(f"{pair['id']} {filename}: expected {before}, got {after}; {detail}")
            if completed.returncode:
                print(f"| {pair['id']} candidate exit | 0 | {completed.returncode} | failed |")
    return failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", help='command template containing {in}, {out}, and {period}')
    args = parser.parse_args()
    pairs, failures = verify_metadata()
    if args.candidate:
        failures.extend(run_candidate(args.candidate, pairs))
    for failure in failures:
        print(f"failed: {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
