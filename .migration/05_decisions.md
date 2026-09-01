# 05 — Decision Log

Append-only. Every STOP outcome, tolerance version, grading-only amendment, halt, and
orchestrator phase transition is a dated entry with an owner.

| # | Date (UTC) | Owner | Entry |
|---|---|---|---|
| 1 | 2026-09-01 20:52 | orchestrator | Phase 1 (`!mongo_setup`) started. `.migration/` absent on `tp-run/mongodb-20260901T205236Z` → new engagement. Prior run `tp-run/mongodb-20260901T032752Z` used as structural reference only; none of its approvals carry over. |
| 2 | 2026-09-01 21:05 | orchestrator | Environment probed: Atlas preflight 8/8 verified; Oracle/Postgres/DynamoDB fixtures booted and seeded (`NS=demo`), read probes WORKS (see 06). Workspace committed. Routing → STOP A (awaiting approval; tolerance record v1 PROPOSED). |
