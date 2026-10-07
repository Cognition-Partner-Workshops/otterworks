# Migration run `mmp_rt_b3_oracle`

Unattended red-team run of the `mongo-migration` Devin plugin against the OtterWorks legacy Oracle billing estate (`services/legacy-billing/db/oracle/**`, schema `OW_BILLING`, mini fixture scale, read-only). Plugin under test: `Cognition-Partner-Workshops/mongo-migration-plugin` at branch `devin/1791335937-app-aware-modeling-next` with `865b105d695090615d1efa908fd9621e7bbd7bff` (PR #54, recon `index_keys` fix) cherry-picked on top, HEAD `6e96827f380046e3f0663f39a02cec930a99143d`; the recon harness from that clone is installed in `/home/ubuntu/.venvs/recon`. Target: shared Atlas M0 reached via the secret named `MONGODB_ATLAS_URI`; this run writes only to database `mmp_rt_b3_oracle`, keeps it under 10 MB, and never touches `ow_tp_*`, `ow_billing_*` or other `mmp_rt_*` databases. Run branch: `tp-run/mongodb-20261007T062215Z`; every PR targets it. Machine files written by the plugin land next to this file; findings about the plugin itself (wrong, blind, or manually corrected tool behaviour) are the main output of the run and are recorded in `05_decisions.md`.

## Recon tolerances (`recon_tolerances.json`, version 1, decision `d-tolerances: strict`)

`full_diff_row_threshold` 100000 (every fixture-scale collection gets a full keyed Tier 3 diff; Tier 1 row counts are always exact — the harness has no row-count slack), `numeric_abs_tol` 0 and `aggregate_rel_tol` 0 (field-level parity), `sample_size` 1000 (harness default, unused below the threshold), `source_concurrency` 1. Strings are compared only after the Oracle profile's canonicalization (`rstrip_spaces` for CHAR, `null_missing_equiv`): pass `--canonicalization skills/mongo-migration/profiles/oracle.md` unchanged in every recon run and name the rules per field in the mapping spec. Changing any value is a new version through a re-picked plan decision, never mid-run (see F5).

## Source fixture (s1.2-fixture)

The live source is the Oracle Free fixture from `docker-compose.oracle-billing.yml` (container `otterworks-oracle-billing-oracle-billing-1`, host port 52521, PDB `FREEPDB1`, schema `OW_BILLING`), seeded once at **mini** scale under namespace `mmprt` (200 customers / 1,000 invoice headers / 1,500 invoice lines with 37 planted orphans / 66 EAV rows / 5 core tenants). Per-table baseline counts are in `fixture_counts.json`. Until `allowed_targets.json` is on the branch, run every command below from `$HOME`, not from inside the checkout (finding F4).

```sh
make -C ~/repos/otterworks oracle-billing-up          # reuses the local image; never oracle-billing-down
DB_PORT=52521 uv run --no-project --with oracledb==2.5.1 python ~/repos/otterworks/testdata/legacy/mmp_rt_mini_seed.py
# read-only source principal (plan decision d-source-principal = ro-user); idempotent
docker cp ~/repos/otterworks/testdata/legacy/mmp_rt_ro_user.sql otterworks-oracle-billing-oracle-billing-1:/tmp/
docker exec -i otterworks-oracle-billing-oracle-billing-1 bash -c 'sqlplus -s system/${ORACLE_PWD}@localhost:1521/FREEPDB1 @/tmp/mmp_rt_ro_user.sql'
```

Source DSN in the plugin's Oracle secret shape (a local env var, not a secret: both passwords are the fixture's compose defaults). Re-create it in every new shell:

```sh
export MMP_RT_SRC_DSN='{"user":"ow_billing_ro","password":"ow_billing_ro","dsn":"localhost:52521/FREEPDB1"}'
```

Connect test (`/home/ubuntu/.venvs/recon/bin/python` has `oracledb`):

```sh
/home/ubuntu/.venvs/recon/bin/python -c 'import json,os,oracledb; s=json.loads(os.environ["MMP_RT_SRC_DSN"]); c=oracledb.connect(user=s["user"],password=s["password"],dsn=s["dsn"]); x=c.cursor(); x.execute("SELECT user, COUNT(*) FROM ow_billing.customer_master GROUP BY user"); print(x.fetchone())'
```

`OW_BILLING_RO` holds exactly the oracle profile's assessment tier (`CREATE SESSION`, `SELECT_CATALOG_ROLE`, `SELECT` on the 20 tables). Under that tier the `ALL_*` catalog views the census runs are blind to PL/SQL source, sequences and scheduler jobs (finding F11); the `DBA_*` views see them. Counting inside the container still uses the owner: `docker exec -i otterworks-oracle-billing-oracle-billing-1 bash -c "sqlplus -s ow_billing/ow_billing@localhost:1521/FREEPDB1"`.

## Fixture manifest (s2.4-fixture)

`fixtures/mmp-rt-mini.json` is the fixture manifest `wave-preflight` requires on every batch (`fixture_manifest`). In this run the fixture *is* the live source (the mini-seeded Oracle Free above; no masked export exists), so `method: synthetic`, `masked_columns: []`, `fixture_is_live_source: true`: `recon --mode fixture` is only a dry-run of the load, the single `--mode live` run is the merge verdict (finding F24). `row_counts` are whole-table counts copied from `fixture_counts.json` because the census carries no row counts (F25). The manifest also lists the planted hostile shapes (37 orphan `INVOICE_LINE` rows, 41 dirty `SIGNUP_DT` text dates, 23 malformed `RELATED_ACCT_IDS` CSV lists, 66 EAV rows, dangling power-law tenant ids) with the rule that finds each one.
