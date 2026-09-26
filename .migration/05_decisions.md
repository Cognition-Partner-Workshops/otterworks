# 05 Decisions

Provenance: `user:<message/event id>` only when a human replied; `default-accepted (soft, 60s, no reply)` when a soft window elapsed. STOP C is always hard.

| ID | Date (UTC) | Decision | Approver | Provenance | Status |
|---|---|---|---|---|---|
| D-001 | 2026-09-26 | Intake FACTs recorded in `00_context.md` (online, mongodb-atlas, source `mmp_rt_src`, target `mmp_rt_billing_n`, exact tolerances, threshold 100000, concurrency 2, width 3, stop_mode soft, STOP C hard, reviewer none, run branch from `origin/tech-partnerships`). | Devin Bot (intake) | user:intake-message | RECORDED |
| D-002 | 2026-09-26 | Target credential corrected to `MONGODB_MMP_RT_TARGET_N_URI`; `MONGODB_MMP_RT_TARGET_URI` and `MONGODB_ATLAS_URI` are never used. | Devin Bot | user:intake-correction-message | RECORDED |
| D-003 | 2026-09-26 17:12 UTC | **STOP A approved.** P1 tolerances `tol-v1` exact (count+checksum parity per collection, index equivalence, threshold 100000, sample 1000, source concurrency 2); P2 `null_missing_equiv`; P3 grading-only fixes pre-authorized; P4 proceed without `RECON_REDACT_SALT` (DEP-004 open); P5 movement via scoped driver loader / mongodump-restore, mongosync not installed. Access: source live WORKS, target migration_cluster WORKS, no BLOCKED items (`06_access_checklist.md`, `08_connectivity.json`). | — | default-accepted (soft, 60s, no reply) | APPROVED |
