UNIT custbill_lakeflow (wave 1, parallel to the package batch; no shared targets). Rebuild the nightly CUSTBILL
chain (etl/legacy-extra: oracle_custbill_extract.py -> ksh/perl fixed-width CUSTBILL_DEMO_ORACLE.dat) as a
Lakeflow Spark Declarative Pipeline with expectations and quarantine. Load databricks:databricks-pipelines,
databricks:databricks-dabs and dbx-migration-factory:target-routing before implementing; read the
legacy-etl-demo skill for the legacy chain.
1. Landing: extract INVOICE_HEADER, INVOICE_LINE, CUSTOMER_MASTER, ENTITY_ATTR_VALUE from Oracle via the session
   bridge (python-oracledb, whole tables, one live read) to parquet and upload to the volume
   /Volumes/ow_tp/mig_20261027_bronze/custbill_landing/<table>/. No 1521 from serverless, no Debezium.
2. Pipeline ow_tp_20261027_custbill (DAB under databricks/mig_20261027/custbill/, target mig_20261027,
   serverless, schedule PAUSED, never trigger-started): bronze = read_files / Auto Loader of the landing parquet
   into ow_tp.mig_20261027_bronze.<table> (types per mapping_spec); silver
   ow_tp.mig_20261027_silver.custbill_records = the legacy extract SQL (batch_no = 85559852 OR
   tenant_id = 'a0000000-0000-0000-0000-000000000001', join customer_master, ordered period_end, cust_no,
   invoice_id) with expectations: cust_no not null, cust_name not null, invoice_dt parses DD-MON-RR, total_amt
   not null and fits 9(10)V99, currency USD. Violations go to ow_tp.mig_20261027_quarantine.custbill_rejects
   (expect_or_drop plus a quarantine flow; never expect_or_fail on the whole batch).
3. Render job ow_tp_20261027_custbill_render (serverless python task, schedule PAUSED, run once manually):
   writes the 65-char records (cust_no X(10), cust_name X(30), period_end YYYYMMDD, amount 9(10)V99 implied
   decimal, 'USD', rec_type 01/02, negative -> 02) exactly like format_record() to
   /Volumes/ow_tp/mig_20261027_bronze/custbill_out/CUSTBILL_DEMO_ORACLE.dat and records the sha256 in the
   one-row table ow_tp.mig_20261027_silver.custbill_file_manifest (file, bytes, sha256, generated_at).
4. Legacy side: run the legacy chain against Oracle read-only (etl/legacy-extra tools, NS=demo) to produce the
   legacy .dat and its sha256. Gates: w1-cb-structural (pipeline + job exist, both PAUSED),
   w1-cb-bronze-parity (row_parity, depth full, PASS on the 4 bronze tables), w1-cb-file-sha256 (export_file:
   Databricks .dat sha256 == legacy .dat sha256, both hashes and byte counts in
   .migration/recon/custbill_lakeflow/custbill_sha256.json), w1-cb-expectations (pipeline event log shows the
   expectations evaluated; the quarantine table is populated by an injected bad row in a fixture-only run and
   has zero rejects on the live run).
Write targets: ow_tp.mig_20261027_bronze.{invoice_header, invoice_line, customer_master, entity_attr_value,
custbill_landing (volume), custbill_out (volume)}, ow_tp.mig_20261027_silver.{custbill_records,
custbill_file_manifest}, ow_tp.mig_20261027_quarantine.custbill_rejects, pipeline ow_tp_20261027_custbill,
job ow_tp_20261027_custbill_render.

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
- Bronze parity depth: run `dbx-recon run --depth sample` for gate w1-cb-bronze-parity (D-022 authorises sample
  depth for the four bronze tables; the 150k-row invoice_line full diff stalled 35 min in attempt 1). The
  file gate w1-cb-file-sha256 stays byte-exact (sha256 + byte counts of both .dat files) — it is the parity
  proof for the CUSTBILL output.
- Pipeline: 'never trigger-started' means no schedule trigger. Exactly one manual `databricks bundle run -t
  mig_20261027 ow_tp_20261027_custbill` update (plus one fixture-only update with the injected bad row) is
  allowed and expected to populate bronze/silver, the quarantine table and the event log for w1-cb-expectations.
- Serverless SDP reading Oracle DATE parquet: set table_properties delta.feature.timestampNtz=supported on the
  bronze streaming tables. Wire dependencies with spark.read.table / dlt.read, not spark.sql over
  fully-qualified pipeline tables inside a temporary view. Omit DAB `mode: development` so resource names are
  exact (name_prefix '' does not override).
- No rerun-proof exists for an SDP pipeline; state `rerun_proof: not_applicable (declarative pipeline)` in the
  report and cite the event log path instead.
