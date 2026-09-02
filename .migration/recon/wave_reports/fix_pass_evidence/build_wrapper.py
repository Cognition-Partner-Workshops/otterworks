"""Assemble the schema-compliant fix-pass recon wrapper from the current-head evidence."""
import json, os, datetime
E = os.path.expanduser("~/cutover_work/fix_recon_evidence")
T = json.load(open(f"{E}/../fix_recon_evidence_ba3b9034/fix_pass.recon.json"))  # template for prose fields only
REL = ".migration/recon/wave_reports/fix_pass_evidence"

def tiers(path):
    r = json.load(open(path))
    out = []
    for t in r["tiers"]:
        out.append((t["tier"], t["name"], t["checks_run"], t["passed"], len(t.get("findings", []))))
    return r, out

checks = []
u8, u8t = tiers(f"{E}/U8/gate/result.json")
for tier, name, n, ok, nf in u8t:
    checks.append({"id": f"U8-T{tier}-{name}", "expected": "all checks pass",
                   "actual": f"{n} checks, passed={ok}, findings={nf}",
                   "source_of_truth": "Oracle OW_BILLING (live, plain SQL) via mapping v1.0.1; Tier-4 recorded transcripts procs/oracle/transcripts/invoicing",
                   "result": "pass" if ok and nf == 0 else "fail"})
for u in ("U5", "U6", "U7"):
    r, tt = tiers(f"{E}/{u}/gate/result.json")
    for tier, name, n, ok, nf in tt:
        checks.append({"id": f"{u}-regression-T{tier}-{name}", "expected": "all checks pass",
                       "actual": f"{n} checks, passed={ok}",
                       "source_of_truth": "Oracle OW_BILLING (live, plain SQL) via mapping v1.0.1",
                       "result": "pass" if ok and nf == 0 else "fail"})
P = json.load(open(f"{E}/probes_current_head.json"))
for p in P["results"]:
    checks.append({"id": f"probe:{p['group']}:{p['probe']}", "expected": "ok",
                   "actual": "ok" if p["ok"] else f"FAIL {p.get('detail')}",
                   "source_of_truth": "Oracle OW_BILLING plain SQL (USER_SEQUENCES.LAST_NUMBER, INVOICE_LINES, BILLING_AUDIT_LOG) + static read of PR head source",
                   "result": "pass" if p["ok"] else "fail"})
w = {
    "kind": "recon-report", "unit": "U8-fix-pass", "namespace": "mongo_205236",
    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "run_mode": "live",
    "harness": {"result": f"{REL}/U8/gate/result.json", "verdict": u8["verdict"], "seed": 714559852,
                "params": {"batch_no": "85559852", "source_ns": "demo"},
                "mapping_version": u8["mapping_version"], "tolerance_version": u8["tolerance_version"]},
    "checks": checks,
    "values_recomputed_from_target": True,
    "idempotency_rerun": {"performed": True, "result": "pass",
                          "evidence": f"load_u8.py re-run + gate re-run ({REL}/U8/gate_run2): result.json identical to gate/result.json modulo timestamps; load reports identical modulo timestamps (U8/idempotency.log)"},
    "planted_anomaly_detections": {"expected_set": [], "actual_set": [], "missing": [], "unexpected": []},
    "unverified_paths": T["unverified_paths"],
}
assert all(c["result"] == "pass" for c in checks), [c for c in checks if c["result"] != "pass"]
json.dump(w, open(f"{E}/fix_pass.recon.json", "w"), indent=1)
print(len(checks), "checks, all pass")
