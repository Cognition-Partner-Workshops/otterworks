# U9 pre-PR self-check (.agents/skills/tp-pre-pr-self-check)

- [x] NULL/missing attribution: missing tenant → `tenant_status` "UNKNOWN" (DECODE default); status codes outside the decode → "UNKNOWN"; no fail-open writes.
- [x] All writes scoped to `ow_tp_mongodb_205236` / `replay_u9_*` (loader `assert_owned`); golden collections read-only.
- [x] No DDL against shared collections; only `replay_u9_*` dropped/recreated.
- [x] Rerun-safe: loader drops + recreates only `replay_u9_*`; recon restores the clone to baseline after Tier 4.
- [x] Evidence retained: `load_report.run1.json`, `result.run1.json`, `recon.summary.run1.md` kept alongside the current run.
- [x] No secrets/emails in source, evidence or commits (secrets referenced by name: `MONGODB_ATLAS_URI`, fixture DSN env name).
- [x] Parity vs tolerance from `.migration/02_tolerances.json` v1 / mapping v1.0 (JSON `v1.0.1` grading-only amendment) — unchanged.
- [x] Idempotency proven by an actual second load (identical populations/indexes).
- [x] Recon values recomputed by the harness against Atlas (`result.json`), not copied.
- [x] Unverified paths listed in `u9.recon.json` and the 04_progress row.
- [x] `u9.recon.json` declares `"kind": "recon-report"`; `make tp-validate-recon` PASS.
- [x] Capability preflight: fixture manifest SHA verified; harness connected to source + target before load/recon.
- [x] `make tp-smoke` green.
