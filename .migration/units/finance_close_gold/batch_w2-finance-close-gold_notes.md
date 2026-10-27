UNIT finance_close_gold (wave 2, serial, width 1). Gold finance table and the one AI/BI dashboard.
1. ow_tp.mig_20261027_gold.finance_close_detail: one row per invoice the close covers, from
   ow_tp.mig_20261027_silver.custbill_records joined back to ow_tp.mig_20261027_bronze.invoice_header
   (invoice_id, cust_id, tenant_id, invoice_dt, total_amt, batch_no, status_cd, plus cust_no, period_end,
   currency, rec_type). ow_tp.mig_20261027_gold.finance_close: SUM(total_amt) and COUNT(*) grouped by currency
   and rec_type, with ns = 'demo' and close_run_at: the same computation the legacy finance close performs
   (GET /api/reports/finance?ns=demo over the parsed CUSTBILL records). Both as tables built by a small DAB
   (databricks/mig_20261027/finance_close/, target mig_20261027, job ow_tp_20261027_finance_close, schedule
   PAUSED, run once manually).
2. Dashboard ow_tp_20261027_finance_close_dashboard (databricks:databricks-aibi-dashboards; test every query on warehouse
   565cd2fd713738c4 first): one page with the close total by currency / rec_type from finance_close, the detail
   row count, and the file sha256 from ow_tp.mig_20261027_silver.custbill_file_manifest. JSON committed under
   databricks/mig_20261027/dashboards/. Report the dashboard URL.
3. Legacy side: the legacy finance close total for NS=demo from the legacy chain (the finance report endpoint or
   its CSV, run locally over the legacy .dat, Oracle read-only), recorded in
   .migration/recon/finance_close_gold/close_total.json side by side with the gold row.
4. Gates: w2-detail-parity (row_parity, depth full, PASS of finance_close_detail vs Oracle INVOICE_HEADER scoped
   by the mapping's root_where), w2-close-total (publish_leg: gold total == SUM(detail) == legacy close total ==
   the dbx-recon Tier-2 aggregate_sum(TOTAL_AMT) of the detail run, all four values printed), w2-dashboard
   (structural: dashboard published, every query runs on the warehouse, URL recorded).
Write targets: ow_tp.mig_20261027_gold.finance_close_detail, ow_tp.mig_20261027_gold.finance_close, dashboard
ow_tp_20261027_finance_close_dashboard, job ow_tp_20261027_finance_close.

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

WAVE-1 LESSONS (D-023, fold in):
- Wave 1 landed: Lakebase packages on mig-20261027-w0/-exec (PR #1730), Lakeflow pipeline ow_tp_20261027_custbill (PR #1731) already populated ow_tp.mig_20261027_bronze.* (invoice_header, invoice_line, ...) and ow_tp.mig_20261027_silver.custbill_records / custbill_file_manifest by one manual update. Read them; do not re-run the pipeline unless a table is missing (then one update, then leave it PAUSED). Merge the base branch forward into yours (never rebase, never cherry-pick ledger commits) so the PR diff never touches .migration/ other than .migration/recon/finance_close_gold/.
- dbx-recon live Databricks: recon.adapters._databricks_connect passes oauth client_id/secret to databricks-sql-connector, which falls into a browser-OAuth wait and hangs. Mint the SP token in-process via databricks.sdk Config().authenticate() and hand it to the harness access_token path (as the wave-1 children did; see .migration/recon/custbill_lakeflow/ for their notes). Never wait more than 10 min on a silent recon run.
- Table-only units still need .migration/recon/finance_close_gold/dependencies.json (zero routines) committed and passed via --routine-dependencies before the merge-evidence run, else routine_parity_missing.
- dbx-recon run --rerun-proof also needs --rerun-source <DDL file>; if a rerun leg is not applicable to a batch job, say so in the PR body and report the unit anyway.
- ow_tp.information_schema.table_privileges is not readable by the SP; expect table_privileges structural_gap and report it as a harness finding, not a parity failure.
- The guard rejects $var in dbx-recon --unit loops; write literal unit names per command. Never wrap SQL clients in shell functions.
- Gate evidence values must be bare repo-relative paths (.migration/recon/finance_close_gold/<file>); put annotations in the PR body. Open exactly one PR from mig/20261027/w2-finance-close-gold into the base branch.
- Dashboard: the legacy close total for ns=demo and the four numbers (gold total, SUM(detail), legacy total, dbx-recon Tier-2 aggregate_sum) go in close_total.json; the dashboard shows the gold total, detail count and the CUSTBILL sha256. Publish it (embed credentials) and report the URL.
