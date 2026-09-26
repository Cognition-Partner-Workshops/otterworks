# w1-b03: `comments` (mmp_rt_src -> mmp_rt_billing_n)

Identity lift of one collection. No application code changes (repo has no MongoDB driver usage).

## Run

```
~/.venvs/recon/bin/python migration/mmp_rt/w1-b03/load.py --mode fixture   # reads mmp_rt_billing_n.fx_src_comments
~/.venvs/recon/bin/python migration/mmp_rt/w1-b03/load.py --mode live      # reads mmp_rt_src.comments (read-only principal)
```

Env (names only): `MONGODB_MMP_RT_SOURCE_URI` (live source), `MONGODB_MMP_RT_TARGET_N_URI` (target and fixture).

Each run drops and recreates the two write targets, so a rerun is idempotent:
`mmp_rt_billing_n.comments`, `mmp_rt_billing_n._dq_comments_orphans`. Inserts are batches of <= 1000,
`insert_many(ordered=False)`, single writer (shared M0).

Recon (fixture, then live once):

```
~/.venvs/recon/bin/recon run --unit w1-b03 --family mongodb-atlas \
  --mapping migration/mmp_rt/w1-b03/fixture_mapping_spec.w1-b03.json --tolerances .migration/02_tolerances.json \
  --canonicalization .migration/canonicalization.json --mode fixture \
  --source-dsn-secret MONGODB_MMP_RT_TARGET_N_URI --source-db mmp_rt_billing_n \
  --target-uri-secret MONGODB_MMP_RT_TARGET_N_URI --target-db mmp_rt_billing_n \
  --target-class migration_cluster --source-concurrency 2 --seed 1 --out migration/mmp_rt/w1-b03/recon/fixture/

~/.venvs/recon/bin/recon run --unit w1-b03 --family mongodb-atlas \
  --mapping migration/mmp_rt/w1-b03/mapping_spec.w1-b03.json --tolerances .migration/02_tolerances.json \
  --canonicalization .migration/canonicalization.json --mode live \
  --source-dsn-secret MONGODB_MMP_RT_SOURCE_URI --source-db mmp_rt_src \
  --target-uri-secret MONGODB_MMP_RT_TARGET_N_URI --target-db mmp_rt_billing_n \
  --target-class migration_cluster --source-concurrency 2 --seed 1 --out migration/mmp_rt/w1-b03/recon/live/
```

## Decisions

- **Unit-scoped mapping copies.** The harness grades every collection in the spec and has no per-unit
  filter; the brief's command (whole `03_mapping_spec.json`) graded other batches' collections and failed
  outside this unit. `mapping_spec.w1-b03.json` / `fixture_mapping_spec.w1-b03.json` are mechanical
  filters of the contract files to the `comments` rows (rows, versions and canonicalization untouched).
- **M1 orphans** (09_compat_report.md): all 12,000 comments loaded unchanged; comments whose `documentId`
  matches no source `documents._id` are written to `_dq_comments_orphans` as
  `{_id, documentId, reason: "orphan_documentId", detectedAt}` (computed from the source side only).
- **Index parity**: `documentId_1` recreated with identical key spec; `_id_` implicit.

## Evidence

`recon/fixture/`, `recon/live/` (harness output, redacted), `recon/live_load_run1.txt`,
`recon/live_load_run2_idempotency.txt`, `recon/get_indexes.txt`.
