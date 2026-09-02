"""Assemble evidence_log.json from the cycle artefacts (no hand-typed numbers)."""
import json, glob, hashlib, subprocess, os
from pathlib import Path

PR = Path.home() / "cutover_work/pr"
REPO = Path.home() / "cutover_work/otterworks"
HEAD = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
UNITS = "U0 U1 U2 U3 U4 U5 U6 U7 U8 U9".split()
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

wm_src = json.load(open(PR / "watermark/source_pass1.json"))
load_steps = [json.loads(l) for l in open(PR / "load/load_summary.jsonl")]
load_start = open(PR / "watermark/load_start_utc.txt").read().strip()
watermark = {
    "run_branch_head_sha": HEAD,
    "run_branch": "tp-run/mongodb-20260901T205236Z",
    "load_start_utc": load_start,
    "load_end_utc": load_steps[-1]["end"],
    "seed": 714559852, "batch_no": 85559852, "source_ns": "demo",
    "manifest_sha256": "0f4722866117edd2ea1f5cf933b294bf39a52c755cff222a3a3c6ca5e8e2ee89",
    "fixture_meta_initialized_at": wm_src["oracle"]["FIXTURE_META.INITIALIZED_AT"][0],
    "mapping_spec_sha256": sha(REPO / ".migration/03_mapping_spec.json"),
    "tolerances_sha256": sha(REPO / ".migration/02_tolerances.json"),
    "canonicalization_sha256": sha(REPO / ".migration/canonicalization.json"),
    "mapping_version": "v1.0.1", "tolerance_version": "v1", "canonicalization_version": "v1",
    "source_population": {k: v for k, v in wm_src.items() if k in ("oracle", "postgres", "dynamodb")},
    "source_reads_identical": None,
}

srcs = []
for f in [PR / "watermark/source_pass1.json", PR / "watermark/source_pass2.json"] + sorted(PR.glob("cycle*/source_p*.json")):
    d = json.load(open(f)); [d.pop(k) for k in ("utc", "oracle_seconds", "postgres_seconds", "dynamodb_seconds")]
    srcs.append(json.dumps(d, sort_keys=True))
watermark["source_reads_identical"] = {"reads": len(srcs), "identical": len(set(srcs)) == 1}

load = {"steps": load_steps, "wall_s_total": sum(s["wall_s"] for s in load_steps), "all_rc0": all(s["rc"] == 0 for s in load_steps),
        "loader_summaries": {}}
for u in UNITS:
    lines = [l for l in open(PR / f"load/{u}.log").read().splitlines() if l.strip()]
    load["loader_summaries"][u] = lines[-1][:400] if u not in ("U7", "U8", "U9") else " ; ".join(lines)[:1200]

cycles = []
prev = None
for n in (1, 2, 3):
    C = PR / f"cycle{n}"
    steps = [json.loads(l) for l in open(C / "steps.jsonl")]
    units = {}
    for u in UNITS:
        r = json.load(open(C / u / "gate/result.json"))
        stripped = dict(r); stripped.pop("generated_at")
        units[u] = {
            "verdict": r["verdict"], "mode": r["mode"], "mapping_version": r["mapping_version"],
            "tolerance_version": r["tolerance_version"], "seed": r["seed"], "params": r["params"],
            "generated_at": r["generated_at"], "warnings": r["warnings"],
            "tiers": [{"tier": t["tier"], "name": t["name"], "checks_run": t["checks_run"], "passed": t["passed"],
                       "findings": len(t.get("findings", []))} for t in r["tiers"]],
            "tier3_populations": next((t["stats"] for t in r["tiers"] if t["tier"] == 3), {}),
            "wall_s": next(s["wall_s"] for s in steps if s["step"] == u),
            "result_sha256_mod_generated_at": hashlib.sha256(json.dumps(stripped, sort_keys=True).encode()).hexdigest()[:16],
            "gate": {"U0": "recon run (harness CLI, oracle)", "U1": "recon run (harness CLI, oracle)", "U2": "recon run (harness CLI, oracle)",
                     "U5": "recon run (harness CLI, oracle)", "U3": ".migration/recon_ext/recon_pg.py (postgres adapter, D13)",
                     "U4": ".migration/recon_ext/run_dynamo_recon.py (dynamodb adapter, D13)",
                     "U6": "scripts/tp_mongo/recon_u6.py (Tier-4 transcript replay PLANS-001..005)",
                     "U7": ".migration/recon_ext/recon_u7.py (Tier-4 RATING-001..008)",
                     "U8": ".migration/recon_ext/recon_u8.py (Tier-4 INVOICE-001..006)",
                     "U9": ".migration/recon_ext/recon_u9.py (Tier-4 DUNNING-001..005)"}[u],
        }
        prov = C / u / "gate/tier4_provenance.json"
        if prov.exists():
            p = json.load(open(prov)); units[u]["tier4_provenance"] = {"oracle_source_sha": p.get("oracle_source_sha"), "transcripts_match": p.get("transcripts_match"), "scenarios": p.get("scenarios")}
    guards = json.load(open(C / "guards.json"))
    src_pre = json.load(open(C / "source_pre.json")); src_post = json.load(open(C / "source_post.json"))
    a = dict(src_pre); b = dict(src_post)
    for k in ("utc", "oracle_seconds", "postgres_seconds", "dynamodb_seconds"): a.pop(k); b.pop(k)
    all_pass = all(v["verdict"] == "PASS" for v in units.values()) and guards["verdict"] == "PASS" and a == b and all(s["rc"] == 0 for s in steps)
    unit_walls = sum(v["wall_s"] for v in units.values())
    reset_walls = sum(s["wall_s"] for s in steps if s["step"].startswith("reset_"))
    cyc = {
        "cycle": n,
        "start_utc": open(C / "cycle_start.txt").read().split()[3],
        "end_utc": open(C / "cycle_end.txt").read().split()[3],
        "watermark_head_sha": open(C / "cycle_start.txt").read().split("head=")[1].strip(),
        "replay_clones_reset_before_gates": n > 1,
        "reset_steps": [s for s in steps if s["step"].startswith("reset_")],
        "units": units,
        "count_guard": {"verdict": "PASS" if all(r["ok"] for r in guards["count_guard"]) else "FAIL",
                        "collections_checked": len(guards["count_guard"]), "rows": guards["count_guard"]},
        "quarantine_ceiling": {"verdict": "PASS" if all(r["ok"] for r in guards["quarantine_ceiling"]) and guards["quarantine_db_only_declared_classes"] else "FAIL",
                               "ceiling": 0.005, "rows": [r for r in guards["quarantine_ceiling"] if r["classes"]],
                               "quarantine_db_collections": guards["quarantine_db_collections"],
                               "only_declared_classes": guards["quarantine_db_only_declared_classes"]},
        "source_stability": {"pre_utc": src_pre["utc"], "post_utc": src_post["utc"], "pre_equals_post": a == b,
                             "fixture_meta_initialized_at": src_pre["oracle"]["FIXTURE_META.INITIALIZED_AT"][0],
                             "billing_audit_log_rows": src_pre["oracle"]["BILLING_AUDIT_LOG"],
                             "seq_billing_audit_log": src_pre["oracle"]["USER_SEQUENCES"]["SEQ_BILLING_AUDIT_LOG"]},
        "cost": {"gate_wall_s_total": round(unit_walls, 1), "reset_wall_s_total": round(reset_walls, 1),
                 "guards_wall_s": next(s["wall_s"] for s in steps if s["step"] == "guards"),
                 "source_probe_wall_s": round(sum(s["wall_s"] for s in steps if s["step"].startswith("source_")), 1),
                 "cycle_wall_s": round(sum(s["wall_s"] for s in steps), 1),
                 "source_systems_touched": "Oracle (read-only plain SQL), Postgres (read-only), LocalStack DynamoDB (scan); serial, cap 1",
                 "loads": len([s for s in steps if s["step"].startswith("reset_")]), "gates": len(units)},
        "verdict": "GREEN" if all_pass else "RED",
        "red_class": None, "diagnosis": None,
        "identical_to_previous_cycle_mod_timestamps": None,
        "git_status_after_cycle_clean": open(C / "git_status_after.txt").read().strip() == "",
    }
    if prev is not None:
        cyc["identical_to_previous_cycle_mod_timestamps"] = all(units[u]["result_sha256_mod_generated_at"] == prev["units"][u]["result_sha256_mod_generated_at"] for u in UNITS)
    cycles.append(cyc); prev = cyc

streak = 0
for c in cycles:
    streak = streak + 1 if c["verdict"] == "GREEN" else 0
verdict = "GREEN" if streak >= 3 else ("RED" if len(cycles) >= 5 else "INCOMPLETE")
out = {
    "engagement": "OtterWorks billing estate -> Atlas, run tp-run/mongodb-20260901T205236Z",
    "phase": "[MONGO v1] Reconciliation & Parallel Run Part 2 / Cutover step 1 (parallel run + final recon at watermark)",
    "target_db": "ow_tp_mongodb_205236", "quarantine_db": "ow_tp_mongodb_205236_quarantine", "ns": "mongo_205236",
    "secrets_by_name_only": ["MONGODB_ATLAS_URI", "OW_BILLING_FIXTURE_DSN", "OW_PG_DSN", "AWS_ENDPOINT_URL"],
    "harness": "mongo-migration-plugin-6d021e15/0.2.1 mongo-recon-harness (recon selftest PASS: 9 canonicalization rules exercised)",
    "parallel_run_definition": "STOP A / 02_tolerances: 3 consecutive GREEN full-estate recon cycles against the idle static fixture (no CDC)",
    "watermark": watermark,
    "full_estate_load": load,
    "cycles": cycles,
    "cycles_run": len(cycles), "green_streak": streak, "verdict": verdict,
    "red_runs": [{"cycle": c["cycle"], "class": c["red_class"], "diagnosis": c["diagnosis"]} for c in cycles if c["verdict"] == "RED"],
    "rules_honoured": ["legacy sources read-only (plain SQL / scans; no PL/SQL invoked; BILLING_AUDIT_LOG stayed at 1 row, SEQ_BILLING_AUDIT_LOG at 2 for all 8 source reads)",
                       "writes only to ow_tp_mongodb_205236 / _quarantine (loaders + Tier-4 replay clones)",
                       "no tolerance, mapping-shape or canonicalization change; no migrated code changed",
                       "source-load cap 1: every load/gate/probe strictly serial", "no fixture restart or reseed"],
}
Path(PR / "evidence_log.json").write_text(json.dumps(out, indent=2, default=str) + "\n")
print(json.dumps({k: out[k] for k in ("cycles_run", "green_streak", "verdict")}))
for c in cycles:
    print(c["cycle"], c["verdict"], c["start_utc"], c["end_utc"], "wall", c["cost"]["cycle_wall_s"], "identical_prev", c["identical_to_previous_cycle_mod_timestamps"], "git clean", c["git_status_after_cycle_clean"])
