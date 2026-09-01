# Migration decision and routing log

Approvals are durable only when recorded here. Silence and approvals from another window
do not count.

| Date (UTC) | Type | Decision / route | Owner | Status | Evidence |
|---|---|---|---|---|---|
| 2026-09-01 | ROUTE | New engagement: `.migration/` absent on fresh `tp-run/mongodb-20260901T033738Z`; enter phase 1 `!mongo_setup` | Orchestrator | RECORDED | Branch created from `origin/tech-partnerships` commit `c8bf45e59717c2d0ed45670aa0845f481fa5a5cd` |
| 2026-09-01 | ROUTE | Phase 1 setup artifacts initialized; Atlas capability probe passed; Oracle read-only access and Atlas capacity remain explicit STOP A items | Orchestrator | RECORDED | `00_context.md` through `06_access_checklist.md`; `evidence/atlas-capabilities.json` |
| 2026-09-01 | STOP A | Tolerances, access posture, capacity, and interaction contract | User | PENDING | `02_tolerances.md`, `06_access_checklist.md` |

No STOP has been approved.
