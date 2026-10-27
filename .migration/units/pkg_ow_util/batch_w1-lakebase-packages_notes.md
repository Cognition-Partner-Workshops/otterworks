UNITS pkg_ow_util, pkg_plans, pkg_rating, pkg_invoicing (one child: the packages are a call chain
pkg_ow_util -> pkg_plans / pkg_rating -> pkg_invoicing and all four write billing_audit_log through log_msg, so
they cannot be split across children). Convert the Oracle packages
services/legacy-billing/db/oracle/packages/*.sql to Lakebase Postgres (PL/pgSQL) routines in schema `billing`
on branch mig-20261027-w0, with the names the app backend expects
(services/legacy-billing/app/backends/postgres.py): fn_<name> returns rows, sp_<name> is a procedure.
Load the oracle-plsql skill (dbx-migration-factory:oracle-plsql, OLTP track) before writing code.
1. DDL first, per the four unit mapping specs (.migration/units/<unit>/mapping_spec.json): billing_audit_log;
   subscriptions, subscriptions_hist; rating_periods, rating_results; invoices, invoice_lines, credit_notes;
   plus the sequences/triggers (trg_billing_audit_log_id -> identity default; trg_subscriptions_hist and
   trg_sub_no_uncancel as PL/pgSQL triggers). Load every owned table from Oracle once so the branch is an exact
   copy of Oracle state before any routine runs there.
2. Routines, one file per package under databricks/mig_20261027/lakebase/1x_pkg_*.sql: f_md5_uuid, f_code_desc,
   f_dt2str, f_str2dt, log_msg, job_purge_audit_log; fn_list_plans, fn_entitlement, sp_change_plan;
   compute_rating, fn_usage_rating, fn_usage_summary, sp_finalize_rating; compute_preview, fn_invoice_preview,
   fn_invoice_lines, sp_issue_invoice. Accepted deviation DEP-003 (STOP B, D-011): log_msg has no autonomous transaction on
   Postgres (it commits with the caller); audit presence and ordering are graded, logged_at is not. Keep Oracle
   rounding (ROUND half away from zero on NUMBER(12,2)), NVL / empty-string semantics, status codes from CODES,
   and the sp_issue_invoice write order (rating_periods, rating_results, invoices, invoice_lines, credit_notes,
   billing_audit_log).
3. Fixture first: develop and prove the golden set on a LOCAL Postgres fixture (make procs-up NS=<ns>, seeded from
   the services/legacy-billing fixtures; Tenant One 00000000-0000-0000-0000-000000000001, plan STARTER,
   260 units on 2026-02-10, period 2026-02-01..2026-02-28). Record golden runs with make procs-record and
   dbx-recon routine-parity; commit them under .migration/recon/<unit_id>/routine_parity/.
   DO NOT execute sp_issue_invoice or sp_change_plan against Lakebase mig-20261027-w0: the parent runs the live
   invoice on the -exec branch after the wave closes; the w0 branch stays a clean copy of Oracle state.
4. Deploy the routines to mig-20261027-w0 (psql, literal host, env DSN). Recon live, depth full, on every owned
   table (PASS). Gates: w1-pkg-structural (all routines present, signatures match the backend),
   w1-pkg-routine-parity (dbx-recon routine-parity: every routine proven, exit 0), w1-pkg-state-parity
   (row_parity, depth full, PASS on the 8 owned tables), w1-pkg-invoice-fixture (fixture issue_invoice for
   Tenant One yields subtotal / tax / total identical to the Oracle fixture run; both rows recorded side by side
   under .migration/recon/pkg_invoicing/).
Write targets: ow_tp.billing.billing_audit_log, subscriptions, subscriptions_hist, rating_periods,
rating_results, invoices, invoice_lines, credit_notes and the routines in deploy_objects (Lakebase branch
mig-20261027-w0 only). Give each unit its own section in the PR body.

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

WAVE-1 RERUN (D-022) — corrections to the first attempt, they override anything above that conflicts:
- Gate evidence in your report MUST be a bare relative path (or ';'-separated bare paths) to files that exist under
  .migration/recon/<unit>/ at your PR head. No annotations in the evidence string; put commentary in the PR body.
- Doctor: run `python -m doctor` with the interpreter of your dbx-recon venv (it needs oracledb importable).
- Secrets: the guard blocks any shell `export`/assignment of OW_BILLING_RO_DSN and blocks unknown wrapper
  functions. Use a python launcher instead: a script that builds the DSN in-process from the Secrets Manager JSON,
  sets os.environ["OW_BILLING_RO_DSN"], and os.execvpe()s the command given on its argv (`python3 launcher.py
  <cmd> ...`). Never print or write the DSN.
- mapping_spec.json target names are catalog-qualified; dbx-recon's lakebase/databricks harness qualifies via
  --target-catalog/--target-schema, so pass a de-qualified copy of the spec (commit it next to your reports).
- Max 3 full recon attempts still applies; a recon that makes no progress for 10 minutes counts as one attempt:
  kill it, record the stall in the report, and continue at the depth this brief allows.
- Branches: mig/20261027/<batch_id> already exists from attempt 1 with your predecessor's work and an open PR
  (#1730 packages, #1731 custbill). Continue on that branch and that PR; do not open a second PR.
- log_id: do NOT use an identity column. billing_audit_log.log_id gets `DEFAULT nextval('billing.billing_audit_log_seq')`
  (a plain sequence, mirroring Oracle's SEQ + trg_billing_audit_log_id) so dbx-recon tier 0 sees a non-identity
  column as in Oracle. Alter the deployed w0 table accordingly before re-running recon.
- Dependencies: before any `dbx-recon run`, write ONE merged dependency file listing every cross-package callee
  (log_msg, f_*, compute_rating, compute_preview, ...) and copy it as .migration/recon/<unit>/dependencies.json
  for each of the four units, so the harness accepts the call chain.
- Fixture writes are now allowed: allowed_targets.json (run branch, D-022) lists localhost / 127.0.0.1 in
  target_hosts and the fixture database billing_demo in catalogs. Use `make procs-up NS=demo` (docker compose;
  DB billing_demo on port 55432+PROCS_PORT_OFFSET) and psql -h localhost -p <port> -d billing_demo for the
  golden set, make procs-record, and dbx-recon routine-parity.
- The -exec branch now exists: mig-20261027-exec, forked from `production` (NOT from w0, TTL branches cannot
  have children), host ep-bitter-haze-d1cs5zdx.database.us-west-2.cloud.databricks.com, credential via
  `databricks postgres generate-database-credential projects/ow-tp-billing/branches/mig-20261027-exec/endpoints/primary
  --ttl 3600s --output json`. Apply to it, in order: the wave-0 scaffold + reference loads
  (databricks/mig_20261027/lakebase/00_scaffold.sql, apply.sh, load_reference.py — already on the run branch),
  then your DDL, state loads and routines. Then run the fixture issue_invoice for Tenant One on -exec ONLY
  (sp_issue_invoice, plan STARTER, 260 units on 2026-02-10, period 2026-02-01..2026-02-28), and record the
  Oracle fixture invoice row and the -exec invoice row side by side in .migration/recon/pkg_invoicing/
  invoice_fixture.json (subtotal, tax, total, line count, status). w0 stays a clean copy of Oracle state:
  still never run sp_issue_invoice / sp_change_plan on w0. The -exec branch and its host are in your write scope.
- Gate w1-pkg-routine-parity evidence = the dbx-recon routine-parity report files; w1-pkg-invoice-fixture
  evidence = .migration/recon/pkg_invoicing/invoice_fixture.json.
