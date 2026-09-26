# 07 Dependency register

States: FOUND, DECIDED (owner and plan named), DONE. Filled in playbook 2.

| ID | Class | Finding | Owner / plan | State |
|---|---|---|---|---|
| DEP-001 | D1 Other writers | Intake: no stored logic in `mmp_rt_src`. App writers to be confirmed by code census (`services/collab-service`, `frontend/`). | — | FOUND |
| DEP-002 | D2 Other readers | Intake headline: `frontend/` and `services/collab-service/` read this shape. Census in playbook 2. | — | FOUND |
| DEP-003 | D3 Scheduled logic | None declared (no stored logic; TTL/cron to be checked in census). | — | FOUND |
| DEP-004 | D4 Access | `RECON_REDACT_SALT` not set in the environment: live recon output is redacted with an unsalted hash (harness warning, still runs). Request: customer sets org secret `RECON_REDACT_SALT` (any random string). Not blocking. | customer app owner | FOUND |
| DEP-005 | D4 Access | `mongosync` binary absent on the VM; mongosync path (profile: eligible for source >= 6.0) would need it installed. Movement fallback: `mongodump`/`mongorestore` (present) or driver-based scoped loader. | orchestrator | FOUND |
