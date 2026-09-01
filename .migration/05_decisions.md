# 05 — Decision log

| Date (UTC) | Phase | Decision | Owner | Status |
|---|---|---|---|---|
| 2026-09-01 | routing | Engagement entered at phase 1 (`!mongo_setup`): no prior `.migration/` state existed on the run branch | Devin (orchestrator) | recorded |
| 2026-09-01 | 1 | Source family = `oracle`; oracle profile loaded from the `mongo-migration` plugin | Devin | recorded |
| 2026-09-01 | 1 | Working branch `tp-run/mongodb-20260901T033326Z` cut from `tech-partnerships`; every unit PR targets it; `tech-partnerships` and `main` are never PR targets | Devin | recorded |
| 2026-09-01 | 1 | Recon mode = LIVE (both Oracle and Atlas reachable and probed from this VM) | Devin | recorded |
| 2026-09-01 | 1 | Tolerance record `v1` drafted (all rows PROPOSED); access checklist probed with evidence | Devin | recorded |
| 2026-09-01 | 1 | **STOP A** — batched approval of tolerances `v1`, target conventions, wave/unit plan, and access gaps R1/R2 | user | **awaiting approval** |

Approvals are never inferred from chat history and never carry across reruns; each is
recorded here with its date and owner before the chain continues.
