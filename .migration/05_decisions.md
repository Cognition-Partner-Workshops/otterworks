# 05_decisions — decision log

Every row: dated, who approved, provenance (`user:<id>`, `derived` with `file:line`, or `default-accepted` — the last never occurs in hard mode). Machine copy for `model_patch.py`: `05_decisions.json` (created in playbook 2).

| ID | Date | Decision | Evidence | Approved by | Status |
|---|---|---|---|---|---|
| D-000 | 2026-09-22 | `recon_mode: offline`, `stop_mode: hard`; source is DDL/PL-SQL only; target is local MongoDB `ow_billing_offline`; no Atlas, no MCP. | intake message in this session | user (intake) | DECIDED |
| D-001 | 2026-09-22 | Tolerance contract `tol-1` as tabled in `02_tolerances.md` (T1–T13, harness values 100000/1000/0/0/1). | Oracle profile `skills/mongo-migration/profiles/oracle.md` §type_mappings, §recon_canonicalization | pending STOP A | PROPOSED |
| D-002 | 2026-09-22 | Empty string target policy = missing field (T7); NULL and missing compare equal (T8). | Oracle `'' IS NULL` semantics; profile §known_incompatibilities row 1 | pending STOP A | PROPOSED |
| D-003 | 2026-09-22 | Text dates parse as `DD-MON-YY` English (T9) and `DD-MON-YY HH24:MI:SS` for `hist_dt` (T10); unparseable → missing + quarantine. | `services/legacy-billing/db/oracle/packages/01_pkg_util.sql:50-62`, `schema/01_tables.sql:218`, `etl/legacy-extra/tools/oracle_custbill_extract.py:19` | pending STOP A | PROPOSED |
| D-004 | 2026-09-22 | Oracle `DATE`/`TIMESTAMP` are treated as UTC wall-clock on load (T3/T4). | no session TZ evidence in DDL; `schema/03_seed_static.sql` sets only NLS date formats | pending STOP A | PROPOSED |
| D-005 | 2026-09-22 | `allowed_targets.json` carries `"catalogs": ["ow_billing_offline"]` next to `databases`. Intake asked for `"catalogs": []`, but the co-installed dbx-migration hook rejects an empty list ("must contain a non-empty 'catalogs' list") and blocked every file write in the repo until the key was non-empty; the same single local database name is carried so the allowlist stays one target. No Databricks catalog exists or is used. | intake message; hook source `hooks/dbx_guard.py:249-251`; tool rejections observed 2026-09-22 | recorded, to confirm at STOP A | DECIDED (deviation) |
| D-006 | 2026-09-22 | Access probes for source RO principal, egress and query cap are recorded OPEN / NOT PROBED, not passed, because nothing is reachable offline. | playbook `1-setup.md` step 5 | user (intake) | DECIDED |
