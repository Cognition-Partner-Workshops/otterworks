# search_reindex_weekly — wave-2 a02 notes

Legacy `etl/scripts/search_reindex_weekly.py` paged document-service
`/api/v1/documents` and file-service `/api/v1/files`, deleted and recreated
the MeiliSearch `documents`/`files` indexes, and validated
`numberOfDocuments` against indexed counts. Converted to Lakeflow job
`ow_tp_analytics_search_reindex` (bundle `etl/dbx-search-reindex`, target
`mig_1793146609`): `ensure_objects` (idempotent DDL) -> `reindex_docs`
(union of `ow_tp_analytics_src.search_index_documents` + `search_index_files`
into `search_index_docs` keyed `(index_name, doc_id)`, `doc_sha256 =
sha2(doc_json, 256)`, snapshot MERGE with NOT MATCHED BY SOURCE DELETE) ->
`reindex_report` (snapshot MERGE of `reindex_report` keyed `metric`).
Schedule PAUSED (`0 0 6 ? * MON` UTC), max_retries 2.

## Mapping normalization (this dir's mapping_spec.json vs the committed units/ spec)

The committed `.migration/units/search_reindex_weekly/mapping_spec.json`
was normalized for the run — documented divergence a verifier must see:

1. `object` rewritten to the bare table name (`search_index_docs`,
   `search_reindex_report`): the Databricks target adapter qualifies objects
   with `--target-catalog`/`--target-schema`; an FQ object would double-
   qualify. `root_table` stays fully-qualified — the source adapter needs
   `catalog.schema.table`.
2. Two source roots land in ONE target table discriminated by `index_name`.
   `root_where`/`target_where` (`index_name = 'documents'` /
   `'files'`) scope each object to its slice; the engine requires both
   sides scoped or neither. Without them tier-1 counts 13-or-15 vs 28 and
   tier-3 flags the other index's rows as extras.
3. `fields` added (`doc_json -> doc_json` per docs object;
   `metric_value`/`report_date`/`generated_at` for the report): the wave-1
   a02 verifier FAILed a keys-only diff as vacuous row_parity evidence.
   `doc_sha256` is target-derived, not mapped.
4. `rerun_posture` undeclared -> `required`; proof legs in `rerun/`.

## Structural grant class (merge-blocker, not worker-fixable)

Run (live, depth full, seed 0): parity PASS, all row tiers clean
(28 docs rows + 5 metric rows, keyed diff clean). `merge_eligible=false`
on blocker_classes=["structural"]: grant parity findings only.

- `grant_missing` for `d9d1c4ec-…`: the grants read filters
  `grantee <> table_owner`; the session SP owns the target tables (it
  created them), so its grants are never visible on the target side.
  GRANT SELECT TO the SP was applied — the row exists in
  table_privileges but is filtered by the owner exclusion, so the finding
  stands. Unfixable while the SP owns the tables.
- `grant_extra` for `2e90bc1d-…` (all_privileges) and `bc8a2ef7-…`
  (modify,select): schema-level grants on `ow_tp.ow_tp_analytics` that UC
  reports as inherited table privileges on every table. Revoking them at
  schema scope would break other principals on tables other units own —
  out of scope for a worker.

Identical class to wave-1, cleared there by human_override
`mo-analytics-w1-structural`. The wave-2 manifest carries
`merge_overrides: null` — no committed entry covers this unit, so
merge_authority stays `harness` and the unit reports not-merge-eligible.

## Workarounds (same identity, documented)

- `bin/recon_env.py`: monkeypatches `recon.adapters._databricks_connect`
  to mint the session SP's token via SDK `Config().authenticate()` and use
  the `access_token` kwarg. The 0.6.1 harness passes
  `credentials_provider=Config().authenticate` directly, but connector 4.8's
  ExternalAuthProvider calls `credentials_provider()` expecting it to
  RETURN the header factory -> `'dict' object is not callable`. The
  oauth-m2m kwargs branch hangs headless.
- `bin/reset_target.py`, `bin/grant_select_self.py`: literal-statement
  scripts (dbx_guard rejects parameterized/multi-statement Databricks
  writes).
- Fixture-mode skipped: `example_databricks/dictionary.json` is a generic
  shape example, not this unit's tables; same-workspace posture means the
  live run is the dev loop anyway.

## Runs

- fresh leg: bundle run 780638694703120 (empty targets -> 28 + 5 rows).
- evolved leg: bundle run 975360374613706 (over landed tables; MERGE
  converged). rerun_proof.json: both legs pass.
- routine_parity: 2 routines unproven (no committed runs), 0 failed.
- Merge-evidence run 1: parity PASS, merge_eligible=false (structural).
- Merge-evidence run 2 (after GRANT SELECT): identical — owner-filter
  confirmed. Recon budget remaining: 1 full run.
