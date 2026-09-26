# w1-b05: audit_events (mmp_rt_src -> mmp_rt_billing_n)

Identity lift of one collection. No application code changes (the repo has no MongoDB
driver usage; see `.migration/census/app_code_census.md`).

## Run

```
# once per session
~/.venvs/recon/bin/recon selftest

# fixture first (reads mmp_rt_billing_n.fx_src_audit_events via MONGODB_MMP_RT_TARGET_N_URI)
~/.venvs/recon/bin/python migration/mmp_rt/w1-b05/load.py --mode fixture
~/.venvs/recon/bin/recon run --unit w1-b05 --family mongodb-atlas \
  --mapping migration/mmp_rt/w1-b05/mapping_fixture.json \
  --tolerances .migration/02_tolerances.json --canonicalization .migration/canonicalization.json \
  --mode fixture --source-dsn-secret MONGODB_MMP_RT_TARGET_N_URI --source-db mmp_rt_billing_n \
  --target-uri-secret MONGODB_MMP_RT_TARGET_N_URI --target-db mmp_rt_billing_n \
  --target-class migration_cluster --source-concurrency 2 --seed 1 \
  --out migration/mmp_rt/w1-b05/recon/fixture/

# live, once (reads mmp_rt_src.audit_events via MONGODB_MMP_RT_SOURCE_URI, read-only)
~/.venvs/recon/bin/python migration/mmp_rt/w1-b05/load.py --mode live
~/.venvs/recon/bin/recon run --unit w1-b05 --family mongodb-atlas \
  --mapping migration/mmp_rt/w1-b05/mapping_live.json \
  --tolerances .migration/02_tolerances.json --canonicalization .migration/canonicalization.json \
  --mode live --source-dsn-secret MONGODB_MMP_RT_SOURCE_URI --source-db mmp_rt_src \
  --target-uri-secret MONGODB_MMP_RT_TARGET_N_URI --target-db mmp_rt_billing_n \
  --target-class migration_cluster --source-concurrency 2 --seed 1 \
  --out migration/mmp_rt/w1-b05/recon/live/
```

Secrets are referenced by environment-variable name only.

## Decisions

- Write target: only `mmp_rt_billing_n.audit_events`; dropped and recreated on every run
  (idempotent), inserted in batches of 1000 with `insert_many(ordered=False)`, single writer.
- M4: string-typed `ts` (`%Y-%m-%dT%H:%M:%S%z`) is parsed and stored as a UTC BSON date;
  date-typed `ts` is copied unchanged. The loader exits non-zero if any target `ts` is not
  a BSON date. Any other `ts` type raises.
- Index parity: `ts_1` (`{ts: 1}`) recreated with identical key spec and options.
- `mapping_fixture.json` / `mapping_live.json` are the `audit_events` rows of
  `migration/mmp_rt/fixture_mapping_spec.json` and `.migration/03_mapping_spec.json`
  respectively, byte-identical rows (version, `_notes`, `canonicalization` preserved). The
  harness grades every collection in the spec it is given, and the shared spec covers all
  six wave-1 collections, so running it unfiltered graded other units' in-flight write
  targets (first fixture run: T1 FAIL on documents/comments/shares, all outside this
  batch). No mapping row was changed.

## Evidence

`recon/fixture/` and `recon/live/` hold the harness output (redacted by default; no
`--raw-values`). Live: PASS, `merge_eligible=true`, mapping `map-v1`, tolerances `tol-v1`.
