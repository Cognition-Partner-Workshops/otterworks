"""Recon evidence for the CUSTBILL Spark chain.

Runs the parity harness with the Spark chain as the candidate, reruns the chain
on one candidate estate to prove idempotency, reads the parse ledger of the
edges case for the planted anomalies, and writes a recon report that validates
against docs/tech-partnerships/contracts/schema/recon-report.schema.json.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
HARNESS_DIR = REPO / "etl/legacy-extra/parity"
DEFAULT_OUT = REPO / "docs/tech-partnerships/recon/custbill-spark-chain.recon.json"
CANDIDATE = f"{HERE / 'bin/custbill-spark'} chain"
EXPECTED_ANOMALIES = ["trailer-mismatch", "unknown-record-type", "awk-numeric-coercion", "xls-copy"]

sys.path.insert(0, str(HARNESS_DIR))
import harness  # noqa: E402


def tree_digest(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*"))
            if p.is_file() and "control" not in p.relative_to(root).parts}


def rerun_chain(root):
    before = tree_digest(root)
    result = subprocess.run(["/bin/sh", "-c", CANDIDATE], cwd=REPO, capture_output=True, text=True,
                            env=dict(os.environ, OTTERWORKS_LEGACY_ROOT=str(root), LC_ALL="C", TZ="UTC"))
    after = tree_digest(root)
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    return result.returncode, changed


def anomalies(edges_root):
    ledger = json.loads((edges_root / "control/parse/latest.json").read_text())["files"]["CUSTBILL_EDGES.dat"]
    found = []
    if not ledger["trailer_reconciled"]:
        found.append("trailer-mismatch")
    reasons = ",".join(s["reasons"] for s in ledger["invalid_sample"])
    if "bad-record-type" in reasons:
        found.append("unknown-record-type")
    if "bad-amount" in reasons or ledger["invalid_records"]:
        found.append("awk-numeric-coercion")
    reports = sorted((edges_root / "reports").glob("finance_billing_*"))
    if len(reports) == 2 and reports[0].read_bytes() == reports[1].read_bytes():
        found.append("xls-copy")
    return found, ledger


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    output = harness.ESTATE / "reports/parity"
    parity_exit = harness.run(CANDIDATE, output, timeout=args.timeout)
    parity = json.loads((output / "parity.json").read_text())
    work = Path(parity["work"])
    checks = [{"id": f"parity/{row['case']}/{row['stage']}".replace("/", "-", 1),
               "expected": "byte-identical to legacy", "actual": "byte-identical" if row["byte_identical"]
               else "DIFFERENT", "source_of_truth": "legacy chain run by etl/legacy-extra/parity/harness.py",
               "result": "pass" if row["byte_identical"] else "fail"} for row in parity["rows"]]
    rerun_exit, changed = rerun_chain(work / "dev/candidate")
    found, ledger = anomalies(work / "edges/candidate")
    checks.append({"id": "edges-trailer-reconciliation", "expected": {"trailer_count": 99, "records": 4},
                   "actual": {"trailer_count": ledger["trailer_count"], "records": ledger["records"]},
                   "source_of_truth": "etl/legacy-extra/parity/fixtures/CUSTBILL_EDGES.dat",
                   "result": "pass" if (ledger["trailer_count"], ledger["records"]) == (99, 4) else "fail"})
    report = {
        "kind": "recon-report",
        "unit": "custbill-spark-chain",
        "namespace": "parity-harness(dev,qa,edges,empty)",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "run_mode": "fixture",
        "checks": checks,
        "values_recomputed_from_target": True,
        "idempotency_rerun": {"performed": True,
                              "result": "pass" if rerun_exit == 0 and not changed else "fail",
                              "evidence": "second `custbill-spark chain` on the dev candidate estate: "
                                          f"exit {rerun_exit}, files changed outside control/: {changed or 'none'}"},
        "planted_anomaly_detections": {"expected_set": EXPECTED_ANOMALIES, "actual_set": found,
                                       "missing": [a for a in EXPECTED_ANOMALIES if a not in found],
                                       "unexpected": [a for a in found if a not in EXPECTED_ANOMALIES]},
        "unverified_paths": [
            "Delivery to a real finance mailbox: the report stage copies to CUSTBILL_DELIVERY_DIR and "
            "records CUSTBILL_DISTRIBUTION; no mail relay is exercised.",
            "A live SFTP server: the harness and nightly job use the file-system drop directory.",
        ],
        "parity_table": str((output / "parity.md").relative_to(REPO)),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    failed = (parity_exit or report["idempotency_rerun"]["result"] != "pass"
              or report["planted_anomaly_detections"]["missing"])
    print(f"recon: {'FAIL' if failed else 'PASS'}; report: {args.out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
