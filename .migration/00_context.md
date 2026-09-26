# 00 Context — mmp_rt online MongoDB → Atlas migration

Field marks: FACT (intake), DISCOVERED (probed), PROPOSED (defaulted, confirmed at STOP A).

## Engagement
| Field | Value | Mark |
|---|---|---|
| Playbook | `!mongo_migrate` (MONGO v1 orchestrator) | FACT |
| Source family | `mongodb-atlas` (profile `skills/mongo-migration/profiles/mongodb-atlas.md`) | FACT |
| Engagement type | ONLINE | FACT |
| Repo | `Cognition-Partner-Workshops/otterworks` | FACT |
| Run branch | `tp-run/mongodb-20260926T170458Z-rt-fanout` (cut from `origin/tech-partnerships`) | FACT |
| Orchestrator session | https://partner-workshops.devinenterprise.com/sessions/02901ba7764144a6a8fbc7d97f9edbd8 | FACT |

## Source
| Field | Value | Mark |
|---|---|---|
| System + version | MongoDB 8.0 (self-hosted equivalent), hosted on Atlas cluster `otterworks-demo` | FACT |
| Database | `mmp_rt_src` — read-only legacy | FACT |
| Collections (headline) | users(500), folders(300), documents(5000), comments(12000), shares(3000), audit_events(20000) | FACT |
| Stored logic | none | FACT |
| Known data-quality issues | orphan comments; null `folderId`s; case-variant duplicate emails; string timestamps in `audit_events` | FACT |
| App code reading this shape | `frontend/`, `services/collab-service/` (headline only) | FACT |
| Read-only credential | secret `MONGODB_MMP_RT_SOURCE_URI` (read@mmp_rt_src) | FACT |
| Network path | open (Atlas SRV); child sessions CAN reach the source | FACT |

## Target
| Field | Value | Mark |
|---|---|---|
| Atlas project / cluster | `otterworks-demos` / `otterworks-demo` (shared M0 free tier, keep workload small) | FACT |
| Migration database | `mmp_rt_billing_n` (the only allowlisted write target, see `allowed_targets.json`) | FACT |
| Migration credential | secret `MONGODB_MMP_RT_TARGET_N_URI` (Atlas user `mmp_rt_target_n`, readWrite@mmp_rt_billing_n only) | FACT (corrected intake) |
| Forbidden credentials | `MONGODB_MMP_RT_TARGET_URI` (other engagement, no access), `MONGODB_ATLAS_URI` (never use) | FACT |
| Driver language(s) | Node/TypeScript (`services/collab-service`, `frontend/*`) | DISCOVERED |

## Correctness contract (detail in 02_tolerances.md)
| Field | Value | Mark |
|---|---|---|
| Connectivity policy | `online` (probe, block on any failure, no fallback) | FACT |
| source_access | `live` | FACT / probe-confirmed in 08_connectivity.json |
| target_access | `migration_cluster` | FACT / probe-confirmed in 08_connectivity.json |
| Tolerances | exact | FACT |
| Row-diff threshold | 100000 | FACT |
| Source query concurrency | 2 | FACT |

## Process / interaction contract
| Field | Value | Mark |
|---|---|---|
| Stop routing | this web session only (no Slack, no Teams) | FACT |
| stop_mode | `soft` (60-second default-accept) for STOP A, STOP B, wave halts with a recommended fix; **STOP C always hard** | FACT |
| Only pings | STOP A / STOP B / STOP C, wave close, halt (AGENTS.md rule 9) | FACT |
| PR reviewer | none | FACT |
| Fan-out width | 3; at least one wave has >=3 batches and runs through `migration-fanout` (Cloud `run_workflow`) | FACT |
| Merge authority | soft mode -> `auto_merge: true` in every manifest; verified PASS PRs merge into the run branch | FACT |
| Cutover principal holder | customer app owner (not present) | FACT |
| Rollback owner | customer app owner (not present) | FACT |
| Production repoint | customer-held; Devin never executes it | FACT |
