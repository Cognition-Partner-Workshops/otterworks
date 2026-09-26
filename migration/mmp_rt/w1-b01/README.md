# w1-b01: users, folders (mmp_rt_src -> mmp_rt_billing_n)

Identity lift (map-v1, tol-v1): same collection names, `_id`, field names and BSON types.
Loader reads and writes `RawBSONDocument`, so documents are copied byte-for-byte (no decode/re-encode).
Writes only `mmp_rt_billing_n.users` and `mmp_rt_billing_n.folders`; each is dropped and recreated
on every run (idempotent). `insert_many(ordered=False)` in batches of 1000, single writer.
Indexes: `users.email_1` (`{email: 1}`, not unique, decision M3); `folders` has only `_id_`.

## Run
```
~/.venvs/recon/bin/python migration/mmp_rt/w1-b01/load.py --mode fixture   # fx_src_* in mmp_rt_billing_n
~/.venvs/recon/bin/python migration/mmp_rt/w1-b01/load.py --mode live      # mmp_rt_src (read-only)
```
Secrets by name: `MONGODB_MMP_RT_TARGET_N_URI` (target and fixture), `MONGODB_MMP_RT_SOURCE_URI` (live source).
Prints per-collection source/inserted/target counts and `getIndexes()` for both sides; exits 1 on a count mismatch.

## Recon
Graded with the batch-scoped mappings `.migration/mappings/w1-b01.fixture.json` (fixture) and
`.migration/mappings/w1-b01.json` (live); the harness has no collection filter, so grading the
whole spec would make the verdict depend on sibling batches.
```
~/.venvs/recon/bin/recon run --unit w1-b01 --family mongodb-atlas --mapping .migration/mappings/w1-b01.json \
  --tolerances .migration/02_tolerances.json --canonicalization .migration/canonicalization.json --mode live \
  --source-dsn-secret MONGODB_MMP_RT_SOURCE_URI --source-db mmp_rt_src \
  --target-uri-secret MONGODB_MMP_RT_TARGET_N_URI --target-db mmp_rt_billing_n \
  --target-class migration_cluster --source-concurrency 2 --seed 1 --out migration/mmp_rt/w1-b01/recon/live/
```
Evidence: `recon/fixture/` (PASS, 2/9/80 checks, not merge evidence) and `recon/live/` (PASS,
2/9/800 checks, `merge_eligible=true`). Live source read exactly once by the loader plus one recon run;
a second `--mode live` load reproduced users=500, folders=300 (idempotent).
