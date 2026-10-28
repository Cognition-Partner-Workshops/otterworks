# custbill-feed recon notes

## Outcome

`mode=live depth=full`: parity PASS (18,750 rows both sides, keyed_diffs clean,
per-field aggregates clean). `merge_eligible=false` — class `structural`:

- `primary_key_informational_only`: Delta constraints are informational (RELY);
  an enforced PK cannot exist on the target. Platform-inherent, not fixable in
  converted code.
- `grant_extra` x2: SP grants on ow_tp.ow_tp_custbill.custbill_feed
  (2e90bc1d-…, bc8a2ef7-…) have no Oracle counterpart — migration-side platform
  grants. Revoking them is a catalog permission change the allowlist does not
  authorize.

No committed `merge_overrides` entry covers this unit -> merge_authority harness.

## Fixture

Fixture-first fails closed: no fixture DSN endpoint is declared for OW_BILLING
(allowed_targets fixture_endpoints lists AWS_ENDPOINT_URL only; no Oracle
fixture copy exists). Live run is the merge evidence.

## Harness workarounds needed (flag for plugin fix)

1. `recon/adapters.py` `_uc_schema_facts`: the table_privileges join read
   `t.owner`; on Databricks `information_schema.tables` the column is
   `table_owner`. The query raised ServerOperationError -> structural tier read
   `unverified` -> structural_gap + warnings blockers. Local harness copy
   patched one column name; the verifier's harness will hit the same wall until
   the plugin is fixed.
2. `_databricks_connect` oauth-m2m (`oauth_client_id`/`oauth_client_secret`)
   hangs indefinitely at `sql.connect` in this environment. Runs used the
   supported `access_token` fallback: DATABRICKS_TOKEN minted from the session
   SP via the SDK, client vars emptied. Same identity, no guard workaround.

## Mapping spec normalization

Committed `.migration/units/custbill-feed/mapping_spec.json` (and every
databricks unit spec on this wave) writes `object` as a 3-part
`catalog.schema.table`; the Databricks target adapter only accepts a bare table
name (it prefixes `--target-catalog --target-schema` itself). `run` was pointed
at the normalized copy `mapping_spec.json` in this directory — same
version/objects/keys, `object: custbill_feed`. The committed spec should be
corrected at wave close.

## Rerun proof (posture `required`)

- fresh: `databricks bundle run ow_tp_custbill_feed -t mig_1793146609` after
  DROP TABLE -> run 173209521907540 -> `rerun/fresh.json`
- evolved: same job over the landed table -> run 1040303351932837 ->
  `rerun/evolved.json` (pre_shape = committed shape)
- prior-shape: `rerun/prior_shape.json` = the shape the committed DDL
  (ensure_objects.sql) lands -> evolved leg `pass`.

## Routine parity

`dependencies.json` declares 3 writing routines (legacy-side writes to
ow_billing.invoice_header / the feed). No fixture snapshot + dedicated exec
schema exists to grade them -> carried `unproven` (cutover exceptions, not
merge blockers).

## Deploy fix this batch

The bundle was deployed while `land_feed.sql` still interpolated
`${var.drop_path}`; `bundle deploy` re-synced and run 173209521907540 landed.
Job schedule remains PAUSED; run_364247554199631 (stale-deploy failure) is not
evidence.
