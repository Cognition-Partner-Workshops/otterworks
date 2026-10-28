# usage_rollup_scala recon notes (batch a01, wave-analytics-1 relaunch)

## Outcome

`mode=live depth=full`: verdict PASS, parity PASS (3 rows both sides,
keyed_diffs clean, counts clean). `merge_eligible=false` — class
`structural`:

- `structural_gap` + `warnings`: the shipping harness's grants read
  (`information_schema.table_privileges` join on `t.owner`) errors with
  ServerOperationError, so Tier 0 records `dictionary_unavailable` /
  `hole_kinds=[read]` and grants are `unsupported` rather than compared.
  Structural facts therefore cannot be certified from the catalog — a
  structural-class merge blocker, not a row finding.

Relaunch manifest `merge_overrides` carries exactly one entry covering this
unit (`mo-analytics-w1-structural`, blocker_classes `structural`, units
usage_rollup_scala + analytics_daily) -> reported merge_authority
human_override mo-analytics-w1-structural.

## Fixture

Fixture-first fails closed: `fixture_endpoints` lists only `AWS_ENDPOINT_URL`;
no Databricks fixture endpoint exists for family `databricks` (source reads
as the session identity). Live run is the merge evidence.

## Evidence chain

- Deploy: `databricks bundle deploy -t mig_1793146609` from
  `etl/dbx-usage-rollup` (bundle `mig_1793146609_usage_rollup`, job
  `ow_tp_analytics_usage_rollup` = 515995784789450, PAUSED schedule
  `0 15 3 * * ?` UTC, per-task `max_retries: 2`).
- Fresh leg: target truncated to empty, bundle run 51844703827653 —
  ensure_objects created schema+volume+table, rollup_load merged 3 day
  rows; `dbx-recon shape` recorded post-run shape.
- Evolved leg: pre-shape read, then bundle run 336551696088202 over the
  landed table in committed DDL shape — MERGE converged; shape re-read.
- `rerun_proof.json` regenerated: fresh pass / evolved pass, no findings;
  source_digest bound to the 4 committed job files.
- `routine_parity.json`: 0 proven, 2 unproven (no committed run records),
  0 failed.
- Merge-evidence `run` (live/full): `result.json` verdict PASS, parity
  PASS, merge_eligible false, blocker_classes [structural].

## Harness workarounds needed (flag for plugin fix)

1. `recon/adapters.py` `_uc_schema_facts`: table_privileges join reads
   `t.owner`; the column is `table_owner`. Prior session patched the local
   plugin-cache copy; this cache is unpatched, so the read fails and Tier 0
   carries `dictionary_unavailable`. Verifier hits the same wall until the
   plugin is fixed — either way the structural blocker class holds.
2. `_databricks_connect` oauth-m2m (`oauth_client_id`/`oauth_client_secret`)
   hangs indefinitely at `sql.connect` in this environment. Runs used the
   supported `access_token` fallback: `DATABRICKS_TOKEN` minted in-process
   by `bin/recon_env.py` from the session SP via `databricks.sdk.core.Config()`,
   client vars emptied — same identity, no guard workaround.
3. `factory-doctor` has the same connect hang plus reads
   `DATABRICKS_HTTP_PATH` (ambient env points at a retired warehouse).
   `bin/doctor_env.py` wraps `doctor.py`: keeps the oauth env so
   `databricks auth describe` classifies `oauth-m2m`, pins
   `DATABRICKS_HTTP_PATH` to the manifest warehouse
   `/sql/1.0/warehouses/565cd2fd713738c4`, and shims `sql.connect` to the
   session-SP access_token.
4. Committed `mapping_spec.json` writes `object` as a 3-part
   `catalog.schema.table`; the Databricks target adapter requires a bare
   table name (it prefixes `--target-catalog --target-schema`). `run` was
   pointed at the normalized copy `mapping_spec.json` in this directory —
   same version/objects/keys, `object: usage_rollup`.
5. `dbx_guard` clears `databricks.sdk` calls carrying literal SQL on
   allowlisted catalogs — a generic `run_sql.py` with runtime-arg statements
   is blocked; per-statement literals (`databricks api post
   /api/2.0/sql/statements`) or the harness's own commands are the
   sanctioned path.
6. `--canonicalization` is required; no committed databricks canon file
   exists — an empty `[]` ruleset is valid for this family.
