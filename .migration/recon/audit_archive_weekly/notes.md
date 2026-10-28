# audit_archive_weekly recon notes

## Outcome

`mode=live depth=full`: parity FAIL, merge blocked — classes `data` + `structural`.
`merge_eligible=false`; wave-analytics-2 manifest carries no `merge_overrides`
entry, so `merge_authority` is `harness`.

### data: duplicate_source_key (spec defect, not fixable in converted code)

The committed mapping spec keys `ow_tp.ow_tp_analytics_src.audit_events ->
audit_archive` on `event_id`. In the staged source, `event_id` is the event
*type* — 4 distinct values over 120 rows (`file.download` 38, `login` 30,
`document.share` 28, `document.view` 24). The column that actually identifies
each staged row is `actor` (`t1-audit-0000`..`t1-audit-0119`, 120 distinct);
the staged column order appears shifted relative to the DynamoDB item shape
(`event_id` holds event_type, `action` holds user_id, `actor` holds the audit
id). Tier 3 fired `duplicate_source_key` x4 and `duplicate_target_key` x4;
counts (120 rows) and per-field aggregates PASS both sides.

No converted-code change clears this: a MERGE keyed on event_id cannot even
land the rows (multiple source rows match one target row), dedup drops 116
rows (count_mismatch), and a wholesale load only swaps the findings to the
target side. The fix is a mapping-spec `key` revision (e.g. `actor`) — a plan
decision a worker may not take mid-run. failure_class: `missing_rule`.

### structural (platform-inherent, same as wave-1)

- `grant_missing` x2: the session SP is the target tables' owner, so it holds
  no grant row while the source side shows one (all_privileges,select).
- `grant_extra` x4: migration-side SP grants on the target tables
  (2e90bc1d-…, bc8a2ef7-…) have no source counterpart.

Wave-1 covered these via `merge_overrides` `mo-analytics-w1-structural`;
wave-analytics-2's manifest has `merge_overrides: null` — if wave close wants
the same coverage it needs a committed override entry for
`audit_archive_weekly` (classes `structural`; the `data` blocker stands on its
own and still needs the spec fix above).

## Fixture

Fixture-first fails closed: `allowed_targets.json` fixture_endpoints lists
AWS_ENDPOINT_URL only; no Databricks fixture endpoint for family `databricks`.
Live run is the merge evidence.

## Harness workaround (flag for plugin fix)

`recon/adapters.py` `_databricks_connect` passes
`credentials_provider=Config().authenticate`, but with databricks-sql-connector
4.8.0 / databricks-sdk 0.157.0 `Config().authenticate()` returns a headers dict
while the connector calls `credentials_provider()` expecting a header *factory*
-> `'dict' object is not callable` at open_session. Session-local shim in
`bin/recon_env.py` wraps it (`credentials_provider=lambda: cfg.authenticate`),
same identity, same auth path — not a guard workaround.

## Mapping spec normalization

Committed spec writes `object` as 3-part `ow_tp.ow_tp_analytics.audit_archive`;
the Databricks target adapter requires a bare table name (it prefixes
`--target-catalog/--target-schema` itself). `run` used the normalized copy
`mapping_spec.json` here — same version/objects/keys. Correct the committed
spec at wave close.

## Rerun proof (posture `required` — spec default)

- fresh: `databricks bundle run ow_tp_analytics_audit_archive -t
  mig_1793146609` on empty target -> run 945578853418146 -> `rerun/fresh.json`
- prior-shape: `rerun/prior_shape.json` = shape the committed DDL
  (ensure_objects.sql) lands -> evolved leg `pass`
- evolved: same job over the pre-created tables -> run 660661020843482 ->
  `rerun/evolved.json` (INSERT OVERWRITE re-landed 120 + 15 rows idempotently)

## Routine parity

No committed `*.run.json` records -> both routines `unproven` (cutover
exceptions, not merge blockers; a missing file would block with
`routine_parity_missing`).

## Conversion notes

`etl/scripts/audit_archive_weekly.py` (DynamoDB >90d sweep -> GLACIER jsonl +
batch deletes + compliance report.json) -> Lakeflow Job
`ow_tp_analytics_audit_archive` (bundle `etl/dbx-audit-archive/`, schedule
PAUSED, max_retries 2). Legacy deletes-from-source are intentionally not
carried: the job lands every staged archived row in `audit_archive` as ledger
rows (`INSERT OVERWRITE` — keyed MERGE is invalid here since event_id does not
identify rows) and MERGEs report metrics into `audit_archive_report`.
