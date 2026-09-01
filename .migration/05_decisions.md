# 05 — Decision log

| Date (UTC) | Phase | Decision | Owner | Status |
|---|---|---|---|---|
| 2026-09-01 | routing | Engagement entered at phase 1 (`!mongo_setup`): no prior `.migration/` state existed on the run branch | Devin (orchestrator) | recorded |
| 2026-09-01 | 1 | Source family = `oracle`; oracle profile loaded from the `mongo-migration` plugin | Devin | recorded |
| 2026-09-01 | 1 | Working branch `tp-run/mongodb-20260901T033326Z` cut from `tech-partnerships`; every unit PR targets it; `tech-partnerships` and `main` are never PR targets | Devin | recorded |
| 2026-09-01 | 1 | Recon mode = LIVE (both Oracle and Atlas reachable and probed from this VM) | Devin | recorded |
| 2026-09-01 | 1 | Tolerance record `v1` drafted (all rows PROPOSED); access checklist probed with evidence | Devin | recorded |
| 2026-09-01 | 1 | **STOP A** — batched approval of tolerances `v1`, target conventions, wave/unit plan, and access gaps R1/R2 | user | **APPROVED 2026-09-01** ("Approve all defaults — proceed to phase 2") |
| 2026-09-01 | 1 | R1 accepted: no dedicated read-only Oracle principal exists; source access proceeds under SELECT-only discipline through the schema-owner account. Recorded as a deviation; no source DDL/DML is issued | user | approved |
| 2026-09-01 | 1 | R2 accepted: Atlas M0 stays as-is (~315 MB headroom). Load is staged wave-by-wave with a headroom re-check at each wave boundary; a wave halts rather than evicting any existing database | user | approved |
| 2026-09-01 | 2 | Tolerance record promoted from PROPOSED to `v1` ACCEPTED at STOP A; further changes are amendments with re-verification scope | Devin | recorded |
| 2026-09-01 | 2 | Census run read-only against the live estate (`tools/census_oracle.py`, `tools/probe_access_patterns.py`); coverage table generated at `census/coverage.md`. 20 tables / 432 columns / 17 PL/SQL objects / 7 triggers / 2 jobs / 5 sequences, all bucketed | Devin | recorded |
| 2026-09-01 | 2 | Census finding: `OW_BILLING` is **two disjoint lineages** (converted legacy estate vs normalized PL/SQL application) with no FK or shared key. Wave plan corrected accordingly — `INVOICES`/`INVOICE_LINES` are the app's own invoices, not a v2 of `INVOICE_HEADER` to retire | Devin | recorded |
| 2026-09-01 | 2 | Mapping `m1` proposed: 13 collections, 44,750 root documents, natural `_id` throughout, all 5 sequences retired. Generated and coverage-checked by `tools/build_mapping_spec.py` | Devin | PROPOSED |
| 2026-09-01 | 2 | Fan-out width 3 with the STOP A source-load cap of 1 enforced by an extract lease in `04_progress.md`, rather than collapsing waves to width-1 | Devin | PROPOSED |
| 2026-09-01 | 2 | **STOP B** — approval of mapping `m1`, the unit/wave plan, fan-out width 3, and the 5 open modeling decisions | user | **awaiting approval** |

Approvals are never inferred from chat history and never carry across reruns; each is
recorded here with its date and owner before the chain continues.
