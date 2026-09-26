# 05 Decisions

Provenance: `user:<message/event id>` only when a human replied; `default-accepted (soft, 60s, no reply)` when a soft window elapsed. STOP C is always hard.

| ID | Date (UTC) | Decision | Approver | Provenance | Status |
|---|---|---|---|---|---|
| D-001 | 2026-09-26 | Intake FACTs recorded in `00_context.md` (online, mongodb-atlas, source `mmp_rt_src`, target `mmp_rt_billing_n`, exact tolerances, threshold 100000, concurrency 2, width 3, stop_mode soft, STOP C hard, reviewer none, run branch from `origin/tech-partnerships`). | Devin Bot (intake) | user:intake-message | RECORDED |
| D-002 | 2026-09-26 | Target credential corrected to `MONGODB_MMP_RT_TARGET_N_URI`; `MONGODB_MMP_RT_TARGET_URI` and `MONGODB_ATLAS_URI` are never used. | Devin Bot | user:intake-correction-message | RECORDED |
