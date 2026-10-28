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

Committed wave manifest `merge_overrides` entry `mo-custbill-w1-structural`
covers blocker class `structural` on unit `custbill-feed` -> merge_authority
`human_override`, decision `mo-custbill-w1-structural`.

## Fixture

Fixture-first fails closed: no fixture DSN endpoint is declared for OW_BILLING
(allowed_targets fixture_endpoints lists AWS_ENDPOINT_URL only; no Oracle
fixture copy exists). Live run is the merge evidence.

## Harness workarounds needed (flag for plugin fix)

1. `recon/adapters.py` `_uc_schema_facts`: the table_privileges join read
   `t.owner`; on Databricks `information_schema.tables` the column is
   `table_owner`. Session-local patch applied per the wave brief.
2. `_databricks_connect` oauth-m2m (`oauth_client_id`/`oauth_client_secret`)
   hangs at `sql.connect` in this environment. Session-local patch per the
   brief: `sql.connect(server_hostname=host, http_path=http_path,
   access_token=_databricks_bearer())`.

## Mapping spec normalization

Committed `.migration/units/custbill-feed/mapping_spec.json` writes `object`
as 3-part `ow_tp.ow_tp_custbill.custbill_feed`; the Databricks target adapter
only accepts a bare table name (it prefixes `--target-catalog --target-schema`
itself). `run` was pointed at the normalized copy `mapping_spec.json` in this
directory — same version/objects/keys, `object: custbill_feed`. The committed
spec should be corrected at wave close.

## Rerun proof (posture `required`)

- fresh: `databricks bundle run ow_tp_custbill_feed -t mig_1793146609` after
  DROP TABLE -> run 88652120260415 -> `rerun/fresh.json`
- evolved: same job over the landed table -> run 165607592354729 ->
  `rerun/evolved.json` (pre_shape = shape the committed DDL lands)
- prior-shape: `rerun/prior_shape.json` = the shape the committed DDL
  (ensure_objects.sql) lands -> evolved leg `pass`.

## Devin Review fixes (this PR)

- `drop_path` was a declared-but-unused task parameter: `land_feed.sql` now
  reads `read_files({{drop_path}} || '/*.feed', ...)` and `ensure_objects.sql`
  creates the volume named by drop_path's basename (`IDENTIFIER` +
  `regexp_extract`), so the configured drop location and the read agree.
- Duplicate `invoice_id` across feed files: dedup now ranks by
  `_metadata.file_modification_time DESC` (then file_path) — the newest
  snapshot wins, not the lexicographically first path.
- Snapshot semantics: `WHEN NOT MATCHED BY SOURCE THEN DELETE` makes the
  table mirror the current drop; invoices absent from the latest extract no
  longer linger in staging.

## Routine parity

`dependencies.json` declares 3 writing routines (legacy-side writes to
ow_billing.invoice_header / the feed). No fixture snapshot + dedicated exec
schema exists to grade them -> carried `unproven` (cutover exceptions, not
merge blockers).

## Deploy

Bundle `mig_1793146609` deployed idempotently (`Resources: 1 unchanged`); job
schedule remains PAUSED (`0 10 2 * * ?` UTC). Extract re-run live against
OW_BILLING (read-only DSN) -> 18,750 records -> `CUSTBILL_DEMO_ORACLE.dat` +
`.feed` uploaded to `/Volumes/ow_tp/ow_tp_custbill/custbill_drop/`.
