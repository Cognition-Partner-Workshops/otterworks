# 05 — Decision Log

Append-only. Every STOP outcome, tolerance version, grading-only amendment, halt, and
orchestrator phase transition is a dated entry with an owner.

| # | Date (UTC) | Owner | Entry |
|---|---|---|---|
| 1 | 2026-09-01 20:52 | orchestrator | Phase 1 (`!mongo_setup`) started. `.migration/` absent on `tp-run/mongodb-20260901T205236Z` → new engagement. Prior run `tp-run/mongodb-20260901T032752Z` used as structural reference only; none of its approvals carry over. |
| 2 | 2026-09-01 21:05 | orchestrator | Environment probed: Atlas preflight 8/8 verified; Oracle/Postgres/DynamoDB fixtures booted and seeded (`NS=demo`), read probes WORKS (see 06). Workspace committed. Routing → STOP A (awaiting approval; tolerance record v1 PROPOSED). |
| 3 | 2026-09-01 21:12 | dhrov.subramanian (requester) | **STOP A APPROVED** as proposed ("Approved", Slack thread p1788296321439879 in #ow-migrations). Tolerance record **v1 = FACT**; target `ow_tp_mongodb_205236` / ns `mongo_205236` = FACT; recon LIVE, source-load cap 1, rerun cap 3, 3-cycle parallel-run window; source topology VM-local. Grading-only amendments pre-authorized. |
| 4 | 2026-09-01 21:12 | orchestrator | Routing → Phase 2 (`!mongo_inventory_and_model`). |
| 5 | 2026-09-01 21:42 | orchestrator | Phase 2 census complete (read-only): Oracle 20 tables/432 cols/17 PL/SQL objects/7 triggers/5 seqs/2 jobs, Postgres 3 tables, DynamoDB 1 table, 24 recorded PL/SQL transcripts. Mapping spec **v1.0-proposed** authored (18 collections, 419 root + 48 embedded field mappings, 5 graded embeds; `03_mapping_spec.json` loads in the recon harness); coverage table 44/44 objects bucketed (1 excluded: `FIXTURE_META`); decisions D1–D13 PROPOSED; units U0–U9, waves 0–3; write targets declared PLANNED in 04. Width recommendation: full fan-out (Option 1). Committed. Routing → **STOP B** (chat + #ow-migrations). |
| 6 | 2026-09-01 21:55 | dhrov.subramanian (requester) | **STOP B APPROVED** as proposed ("approved", Slack thread p1788296971419259 in #ow-migrations). Mapping spec **v1.0-proposed → v1.0 (FACT, frozen)**; decisions D1–D13 = FACT; units U0–U9, waves 0–3 = FACT; width = **Option 1 (recommended default): full fan-out via the dynamic workflow**, one child per unit, children re-boot the deterministic `NS=demo` fixture and self-verify `run_mode: fixture`; parent runs the single LIVE independent wave recon (cap 1). Not width-1-inline. |
| 7 | 2026-09-01 21:55 | orchestrator | Routing → Phase 3 (fan-out dynamic workflow). Write targets flip PLANNED→REGISTERED per unit at contract time. |
