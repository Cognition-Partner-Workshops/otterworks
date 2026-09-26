# w1-b02 - `documents` (mmp_rt_src -> mmp_rt_billing_n)

Identity lift of one collection. No application code changes: the repo has no
MongoDB driver usage (`.migration/census/app_code_census.md`).

## Run

```
PY=~/.venvs/recon/bin/python
$PY migration/mmp_rt/w1-b02/load.py --mode fixture   # reads mmp_rt_billing_n.fx_src_documents
$PY migration/mmp_rt/w1-b02/load.py --mode live      # reads mmp_rt_src.documents (read-only principal)
```

Secrets by env var name only: `MONGODB_MMP_RT_SOURCE_URI` (live source, read-only),
`MONGODB_MMP_RT_TARGET_N_URI` (target and fixture). Every run drops and recreates
`mmp_rt_billing_n.documents`, copies all documents in `_id` order in batches of 1000
(`insert_many(ordered=False)`, single writer), recreates the non-`_id` indexes with the
source's key spec and options, and prints source/target counts plus `getIndexes()` of both
sides. Exit code is non-zero on a count mismatch.

Recon commands are the ones in the batch brief (fixture, then live once); outputs land in
`recon/fixture/` and `recon/live/`. Never pass `--raw-values`.

## Decisions

- Documents are read and written as `RawBSONDocument`, so every BSON type is preserved
  byte-for-byte: `price` stays Decimal128 (M5), `folderId: null` stays null (M2), dates keep
  their millisecond precision, `tags` arrays and `_id` values are unchanged.
- Index parity: indexes are copied from the source collection's `list_indexes()`
  (`ownerId_1_updatedAt_-1`), not hard-coded, so the loader cannot drift from the source.
- The recon harness grades every collection in the mapping spec and has no per-unit filter.
  The binding runs (`recon/fixture/`, `recon/live/`) therefore also depend on the sibling
  batches (w1-b01, b03, b04, b05) having loaded their collections into the same target
  database. `recon/fixture-unit-scoped/` is a diagnostic run over a mechanical filter of the
  unmodified spec to this unit's rows (`recon/unit_scoped_*_mapping.json`); it is not merge
  evidence.
