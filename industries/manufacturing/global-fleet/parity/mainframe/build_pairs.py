#!/usr/bin/env python3
"""Build holdout metadata and compare each input snapshot with the current unload."""

import hashlib
import json
import re
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from decode import LAYOUTS, decode_records

HERE = Path(__file__).resolve().parent
FLEET = HERE.parent.parent
REPO = FLEET.parents[2]
HOLDOUT = FLEET / "mainframe" / "holdout"
UNLOAD = FLEET / "mainframe" / "unload"
KEY_FIELDS = {
    "EMPLOYEE.dat": "empid",
    "VEHICLE.dat": "vehid",
    "ASSIGNMENT.dat": "asgid",
    "MILECLM.dat": "clmid",
    "BENPRD.dat": "period",
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report_totals(path):
    text = path.read_text(encoding="ascii")
    match = re.search(
        r"RECORDS WRITTEN\s+([\d,]+)\s+TOTAL TAXABLE\s+([\d,]+\.\d{2})"
        r"\s+TOTAL REIMBURSED\s+([\d,]+\.\d{2})",
        text,
    )
    if not match:
        raise ValueError(f"BENRPT total line not found in {path}")
    details = re.findall(r"^\s[A-Z0-9]{8}\s+\d{10}\s+", text, flags=re.M)
    return {"recordsWritten": int(match.group(1).replace(",", "")),
            "totalTaxable": match.group(2).replace(",", ""),
            "totalReimbursed": match.group(3).replace(",", ""),
            "detailRows": len(details)}


def as_keyed_rows(path, filename):
    key_field = KEY_FIELDS[filename]
    records = decode_records(path)
    return {record[key_field]: (record, path.read_bytes()[i * LAYOUTS[filename][0]:(i + 1) * LAYOUTS[filename][0]])
            for i, record in enumerate(records)}


def relationship(pair_path, unload_path, filename):
    pair_rows = as_keyed_rows(pair_path, filename)
    unload_rows = as_keyed_rows(unload_path, filename)
    missing = sorted(key for key in pair_rows if key not in unload_rows)
    changed = sorted(key for key in pair_rows if key in unload_rows and pair_rows[key][1] != unload_rows[key][1])
    current_extra = sorted(key for key in unload_rows if key not in pair_rows)
    return {
        "pairRows": len(pair_rows),
        "currentUnloadRows": len(unload_rows),
        "exactRowsPresent": len(pair_rows) - len(missing) - len(changed),
        "onlyInPair": missing,
        "sameKeyChanged": changed,
        "onlyInCurrentUnload": current_extra,
        "relationToCurrentUnload": "exact subset" if not missing and not changed else "differs from current unload",
    }


def read_sha_manifest():
    manifest = {}
    for line in (HOLDOUT / "PAIRS.sha256").read_text(encoding="ascii").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        digest, relative = line.split(None, 1)
        manifest[relative.strip()] = digest
    return manifest


def build():
    checksums = read_sha_manifest()
    grouped = defaultdict(dict)
    for relative, digest in checksums.items():
        match = re.match(r"(HP-\d{6})/(IN|OUT)/([^/]+)$", relative)
        if match:
            pair_name, direction, filename = match.groups()
            grouped[pair_name][(direction, filename)] = digest
    pairs = []
    for pair_name in sorted(grouped):
        inputs = {}
        outputs = {}
        pair_relation = {}
        pair_rows = {}
        for direction, target in (("IN", inputs), ("OUT", outputs)):
            for (entry_direction, filename), digest in sorted(grouped[pair_name].items()):
                if entry_direction != direction:
                    continue
                path = HOLDOUT / pair_name / direction / filename
                entry = {"path": str(path.relative_to(REPO)), "sha256": sha256(path)}
                if filename.endswith(".dat"):
                    entry["recordCount"] = len(path.read_bytes()) // LAYOUTS[filename][0]
                    if direction == "IN":
                        pair_rows[filename] = path
                elif filename == "BENRPT.txt":
                    entry["detailRows"] = report_totals(path)["detailRows"]
                    entry["lineCount"] = len(path.read_text(encoding="ascii").splitlines())
                target[filename] = entry
        for filename, pair_path in pair_rows.items():
            current_path = UNLOAD / filename
            pair_relation[filename] = relationship(pair_path, current_path, filename)
        period_row = decode_records(HOLDOUT / pair_name / "IN" / "BENPRD.dat")[0]
        out_bin = HOLDOUT / pair_name / "OUT" / "BENOUT.dat"
        out_report = HOLDOUT / pair_name / "OUT" / "BENRPT.txt"
        output_records = decode_records(out_bin)
        totals = report_totals(out_report)
        output_taxable = sum((Decimal(row["taxableBenefit"]) for row in output_records), Decimal(0))
        output_reimbursed = sum((Decimal(row["reimbursement"]) for row in output_records), Decimal(0))
        pairs.append({
            "id": pair_name,
            "period": period_row["period"],
            "benefitPeriodRow": period_row,
            "input": inputs,
            "expectedOutput": outputs,
            "relationToCurrentUnload": pair_relation,
            "consistency": {
                "benoutRecords": len(output_records),
                "benoutTaxableTotal": f"{output_taxable:.2f}",
                "benoutReimbursedTotal": f"{output_reimbursed:.2f}",
                "benrpt": totals,
                "recordCountMatches": len(output_records) == totals["recordsWritten"],
                "taxableMatches": f"{output_taxable:.2f}" == totals["totalTaxable"],
                "reimbursedMatches": f"{output_reimbursed:.2f}" == totals["totalReimbursed"],
                "detailRowsMatch": len(output_records) == totals["detailRows"],
            },
        })
    open_periods = [row for row in decode_records(UNLOAD / "BENPRD.dat") if row["period"] == 202610]
    not_holdout = [{
        "period": 202610,
        "benefitPeriodRow": open_periods[0] if open_periods else None,
        "reason": "The period is open in unload/BENPRD.dat and was never run; there is no expected output.",
        "expectedOutput": None,
    }]
    result = {"sourceManifest": str((FLEET / "mainframe/holdout/PAIRS.sha256").relative_to(REPO)),
              "pairs": pairs, "notHoldout": not_holdout}
    (HERE / "pairs.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    built = build()
    print(f"wrote {len(built['pairs'])} holdout pairs to {HERE / 'pairs.json'}")
