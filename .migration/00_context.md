# 00_context — OtterWorks legacy billing (Oracle) → MongoDB

| Field | Value |
|---|---|
| Engagement | OtterWorks legacy billing estate, Oracle schema `OW_BILLING` → MongoDB |
| source_family | `oracle` |
| recon_mode | `offline` — DDL and PL/SQL scripts only; no source connectivity, no target cluster, no MCP servers |
| stop_mode | `hard` for STOP A, STOP B and STOP C (requested at intake). No timeouts, no default-accept. |
| Source artefacts | `services/legacy-billing/db/oracle/schema/*.sql` (5 scripts), `services/legacy-billing/db/oracle/packages/*.sql` (5 packages). Read-only (AGENTS.md rule 1). |
| Application readers/writers | `services/legacy-billing/app` (Flask facade + `reports.py`, `BILLING_BACKEND=oracle`), `services/legacy-billing/bridge` (usage bridge → facade), `etl/legacy-extra/tools/oracle_custbill_extract.py` (month-end extract), the PL/SQL packages, DBMS_SCHEDULER jobs in `schema/04_jobs.sql`. Detail in `07_dependency_register.md`. |
| Estate repo / branch | `Cognition-Partner-Workshops/otterworks`, before-state `tech-partnerships` (immutable), working branch `tp-run/mongodb-20260922T142645Z` (cut with `make tp-run-branch TRACK=mongodb`) |
| Plugin repo / branch | `Cognition-Partner-Workshops/mongo-migration-plugin`, branch `offline`, checkout `/home/ubuntu/repos/mongo-migration-plugin` |
| Target (this run) | Local MongoDB 7 in Docker (`skills/schema-modeling/docker-compose.local.yml`), URI in env var `MONGO_LOCAL_URI`, database `ow_billing_offline` only (`allowed_targets.json`) |
| Migration cluster (Atlas) | none in this run. `MONGODB_ATLAS_URI` is injected by the environment and is unset (`env -u MONGODB_ATLAS_URI`) for every offline command; `offline_guard.py` refuses when it is present. |
| Source fixture | Oracle Free container built from the DDL above (`--profile oracle`); never the source system |
| Driver languages | Python (loader and harness, `oracledb` + `pymongo`) |
| Children reach the source? | No. No fan-out workflow; units run sequentially in this session. Children could not run recon anyway (offline). |
| Stops posted where | This session, `message_user(block_on_user=true)`. Never the parent session. |
| Pings | Only STOP A, STOP B, STOP C, one wave-close brief per wave, and a halt (AGENTS.md rule 9). |
| Circuit breaker | 3 same-class failures across units → halt and message (rule 7). Re-run cap per unit: 3 full recon runs. |
| Secrets | By env-var name only: `MONGODB_ATLAS_URI` (present, deliberately unused), `MONGO_LOCAL_URI` (local target), `ORACLE_FIXTURE_PWD` (local fixture only). No values in any artefact. |
| Merge policy | Fixture PASS is loader/spec evidence only, never parity. `merge_eligible: false` on every unit until the customer runs LIVE or SNAPSHOT recon inside their network. PRs are held for the human's wave-close reply (hard mode). |
