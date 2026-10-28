# usage_rollup_scala recon notes

## Outcome

`mode=live depth=full`: parity PASS (3 rows both sides, keyed_diffs clean,
per-field aggregates clean, counts clean). `merge_eligible=false` — class
`structural`:

- `grant_extra` x2: migration-side SP grants on
  ow_tp.ow_tp_analytics.usage_rollup (2e90bc1d-…, bc8a2ef7-…) have no
  source-side counterpart — platform grants outside worker scope (same class
  as custbill-feed).
- `grant_missing`: the session SP (d9d1c4ec-…) appears as a grantee on the
  source staging table (all_privileges, select); on the target it is the
  table owner, so information_schema carries no grant row. Platform-inherent.

No committed `merge_overrides` entry covers this unit -> merge_authority harness.

## Fixture

Fixture-first fails closed: `fixture_endpoints` lists only `AWS_ENDPOINT_URL`;
no Databricks fixture endpoint exists for family `databricks` (source reads
as the session identity). Live run is the merge evidence.

## Harness workarounds needed (flag for plugin fix — same as custbill-feed)

1. `recon/adapters.py` `_uc_schema_facts`: table_privileges join read
   `t.owner`; on Databricks `information_schema.tables` the column is
   `table_owner`. Raised ServerOperationError until patched in the local
   plugin-cache copy. Verifier hits the same wall until the plugin is fixed.
2. `_databricks_connect` oauth-m2m (`oauth_client_id`/`oauth_client_secret`)
   hangs indefinitely at `sql.connect` in this environment. Runs used the
   supported `access_token` fallback: `DATABRICKS_TOKEN` minted from the
   session SP via the SDK, client vars emptied. Same identity, no guard
   workaround.
3. Committed `mapping_spec.json` writes `object` as a 3-part
   `catalog.schema.table`; the Databricks target adapter requires a bare
   table name (it prefixes `--target-catalog --target-schema`). `run` was
   pointed at the normalized copy `mapping_spec.json` in this directory —
   same version/objects/keys, `object: usage_rollup`.
4. `--canonicalization` is required for `run` but no databricks-family
   canonicalization.json exists; used `canonicalization.json` = `[]` here
   (same-platform family, no type remap).

## Converted-DDL fix between recon runs 1 and 2

First run carried `not_null_extra` (target `date` NOT NULL vs nullable
source column) and `primary_key_informational` — both artifacts of my
`ensure_objects.sql`, not platform gaps. Removed the PK + NOT NULL so the
target mirrors the source shape; table dropped and re-landed, rerun proof
regenerated, recon re-run. Only grant-parity findings remain.

## Rerun proof (posture `required`)

- fresh: `databricks bundle run ow_tp_analytics_usage_rollup -t
  mig_1793146609` on an empty target -> run 382809944790933 ->
  `rerun/fresh.json`
- evolved: same job over the landed table (committed DDL shape) -> run
  45502988345974 -> `rerun/evolved.json` (pre_shape = committed shape)
- prior-shape: `rerun/prior_shape.json` = the shape the committed DDL lands
  -> evolved leg `pass`.

## Routine parity

`dependencies.json` declares 2 routines (legacy-side analytics rollup
steps). No fixture snapshot + exec schema exists to grade them -> carried
`unproven` (cutover exceptions, not merge blockers).

## Deploy note

Two wave-1 batches initially derived the same DAB bundle name
(`mig_1793146609_analytics`); a01's first `bundle deploy` deleted a02's
deployed job `ow_tp_analytics_daily` via shared deploy state. a01 destroyed
under the shared name and redeployed under `mig_1793146609_usage_rollup`;
a02 redeployed under its own unique name. Only the `-t` target is
allowlist-checked; bundle names must stay unique per batch.
