UNIT lakebase_scaffold (wave 0, serial, width 1). Stand up the Lakebase target schema and load the reference tables.
1. On Lakebase branch mig-20261027-w0 create schema `billing` (idempotent) and typed DDL for CODES, PLANS, TENANTS,
   USAGE_EVENTS exactly as .migration/units/lakebase_scaffold/mapping_spec.json declares (PKs from the Oracle
   dictionary .migration/inventory/oracle_dictionary_20261027.json). DDL lives in the repo under
   databricks/mig_20261027/lakebase/00_scaffold.sql plus a small idempotent apply script.
2. Load those four tables from Oracle via the session bridge (python-oracledb read, psycopg COPY), whole tables,
   `ns::` prefixed demo tenants included. Touch no other billing table; wave 1 units own theirs.
3. Recon: dbx-recon run --family oracle --mode live --depth full ... PASS on all four objects. Also run
   dbx-recon fixture-shape against the fixture copy and dbx-recon type-map-audit on the mapping spec.
4. Gates you must satisfy: w0-structural (schema + tables exist with the declared types and PKs),
   w0-reference-parity (row_parity, depth full, PASS), w0-fixture-shape (fixture column shape equals the Oracle
   dictionary; fixture-shape exit 0).
Write targets: ow_tp.billing.codes, ow_tp.billing.plans, ow_tp.billing.tenants, ow_tp.billing.usage_events
(Lakebase branch mig-20261027-w0 only). Deploy objects: none.

NOTES:
- Expected harness outcome: the harness PASS is the merge authority (plugin 0.4.3 treats first-hop
  platform-role grants as the platform's).
- Confirm your dbx-recon is >= 0.4.3 (tests dir has test_grants_inherited_through_a_platform_role_are_not_the_units)
  before the live recon; otherwise report FAIL "plugin_stale" without running.
- Guard rules learned in prior runs: literal -f for SQL files (no shell-expanded SQL args); split Oracle extract
  and psycopg load into two programs (extract | load); never `rm` a path starting with databricks/ (use git rm
  or python); no heredocs mentioning apply.sh or psql-like tokens; load OW_BILLING_RO_DSN from Secrets Manager
  in-process (a ~/bin helper outside the repo) instead of command-substitution exports.
- Use a de-qualified copy of the mapping spec (mapping_spec.bare.json under .migration/recon/lakebase_scaffold/):
  the Lakebase adapter needs schema-relative object names; fixture-shape --source-statement-cap 40.

RUN CONTRACT (read .migration/00_context.md, 01_conventions.md, 03_recon_tolerances.*, allowed_targets.json first).
- Run 20261027; base branch tp-run/databricks-20261027T213833Z; open exactly one PR from a branch
  mig/20261027/<batch_id> into tp-run/databricks-20261027T213833Z; never merge it. Never touch main or
  tech-partnerships.
- You run on your own VM: nothing under /home/ubuntu/bin exists for you; the recipes below are the helpers.
- PREFLIGHT (the workflow text says `factory-doctor ...`; there is no such executable, and `python3 .../doctor.py`
  is blocked by the guard because it reads the script body). Run the doctor as a module, from the repo root:
  `PYTHONPATH=<plugin>/skills/factory-doctor python3 -m doctor --workspace . --role child --reuse-record
  .migration/waves/wave-<n>.doctor.json --expect-identity <caps.identity> --expect-host <caps.host> --unit <unit>
  --source-family oracle --source-secret OW_BILLING_RO_DSN --param ns=demo ...` where <plugin> is the
  dbx-migration-plugin version directory under /opt/.devin/plugins/cache (ls -d /opt/.devin/plugins/cache/*dbx-migration-plugin*/*/).
  OW_BILLING_RO_DSN must be exported in that shell (recipe below). A fail row is status=BLOCKED naming the check id.
- Oracle OW_BILLING (52.201.36.9:1521/FREEPDB1) is READ-ONLY. The DSN is the env var OW_BILLING_RO_DSN,
  built from AWS Secrets Manager secret ow-tp/oracle/ow_billing_ro (us-east-1; JSON keys user, password, host,
  port, service; principal OW_BILLING_RO) as oracle://<user>:<password>@<host>:<port>/<service>, user and
  password url-quoted. Recipe, one shell: read the SecretString with `aws secretsmanager get-secret-value --region
  us-east-1 --secret-id ow-tp/oracle/ow_billing_ro --query SecretString --output text`, pipe it to a python3 -c
  one-liner that json.loads stdin and prints the oracle:// URL, and `export OW_BILLING_RO_DSN` from that.
  Never print or persist it. Fixture first (services/legacy-billing fixtures, testdata/legacy oracle_billing_seed
  NS=demo), then ONE live read per stage.
- Databricks: service principal d9d1c4ec-29da-4ec7-9aa0-e932710d61e2, DATABRICKS_AUTH_TYPE=oauth-m2m, no PAT,
  catalog ow_tp, warehouse 565cd2fd713738c4. Write only to your declared write_targets; any other write halts the
  wave. Schedules PAUSED. No cutover, no BILLING_BACKEND change on any deployed service, never Lakebase branch
  `production`, never ow_tp.bronze / ow_tp.silver / ow_tp.gold / airbyte / fivetran schemas.
- Lakebase: project ow-tp-billing, database ow_tp, branch mig-20261027-w0, host
  ep-crimson-wave-d1jr0yo9.database.us-west-2.cloud.databricks.com. Credential recipe: `databricks postgres
  generate-database-credential projects/ow-tp-billing/branches/mig-20261027-w0/endpoints/primary --ttl 3600s
  --output json` (top-level `token`); put it in ~/.pgpass (chmod 600) as
  <host>:5432:*:d9d1c4ec-29da-4ec7-9aa0-e932710d61e2:<token>, then `psql -h <literal host> -U
  d9d1c4ec-29da-4ec7-9aa0-e932710d61e2 -d ow_tp` (sslmode=require). Never assign the host to a shell variable the
  allowlist trusts and never print the token. Objects are owned by the service principal role.
- Recon: dbx-recon --family oracle from your session (install per the data-reconciliation skill into a venv;
  never from serverless), mapping
  .migration/units/<unit_id>/mapping_spec.json, tolerances .migration/03_recon_tolerances.json (tol-20261027-v1),
  params --param ns=demo --param batch_no=85559852 --param admin_tenant_id=a0000000-0000-0000-0000-000000000001
  --param fixture_tenant_id=00000000-0000-0000-0000-000000000001. Reports go under .migration/recon/<unit_id>/,
  the ONLY .migration path you may write. Max 3 full recon attempts, then stop and report. Only a dbx-recon
  verdict is parity; fix recon failures in converted code, never in the source or the tolerances.
- Before the PR: make tp-smoke, the tp-pre-pr-self-check skill for your unit, lint/typecheck/affected tests for
  code you touch. Report: changed paths, write targets actually written, recon verdict + report paths, PR URL.
- Secrets by name only. Do not edit .migration/05_progress.md, allowed_targets.json, 06_decisions.md, waves/.
