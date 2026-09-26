# Batch w1-b04 - `shares` (mmp_rt_src -> mmp_rt_billing_n)

Identity lift of one collection. No application code changes (the repo has no MongoDB
driver usage; see `.migration/census/app_code_census.md`).

## Run

```bash
# unit-scoped mapping copies (regenerate if the contract changes; never edit by hand)
python3 migration/mmp_rt/w1-b04/scope_mapping.py

# fixture first
~/.venvs/recon/bin/python migration/mmp_rt/w1-b04/load.py --mode fixture
~/.venvs/recon/bin/recon run --unit w1-b04 --family mongodb-atlas \
  --mapping migration/mmp_rt/w1-b04/fixture_mapping_spec.w1-b04.json \
  --tolerances .migration/02_tolerances.json --canonicalization .migration/canonicalization.json \
  --mode fixture --source-dsn-secret MONGODB_MMP_RT_TARGET_N_URI --source-db mmp_rt_billing_n \
  --target-uri-secret MONGODB_MMP_RT_TARGET_N_URI --target-db mmp_rt_billing_n \
  --target-class migration_cluster --source-concurrency 2 --seed 1 \
  --out migration/mmp_rt/w1-b04/recon/fixture/

# then live, once
~/.venvs/recon/bin/python migration/mmp_rt/w1-b04/load.py --mode live
~/.venvs/recon/bin/recon run --unit w1-b04 --family mongodb-atlas \
  --mapping migration/mmp_rt/w1-b04/mapping_spec.w1-b04.json \
  --tolerances .migration/02_tolerances.json --canonicalization .migration/canonicalization.json \
  --mode live --source-dsn-secret MONGODB_MMP_RT_SOURCE_URI --source-db mmp_rt_src \
  --target-uri-secret MONGODB_MMP_RT_TARGET_N_URI --target-db mmp_rt_billing_n \
  --target-class migration_cluster --source-concurrency 2 --seed 1 \
  --out migration/mmp_rt/w1-b04/recon/live/
```

Secrets are referenced by environment-variable name only. `MONGODB_MMP_RT_SOURCE_URI` is a
read-only principal; the loader never writes through it.

## Decisions

- **Write target:** `mmp_rt_billing_n.shares` only. Dropped and recreated on every run.
- **Unit-scoped mapping copies.** The recon harness grades every collection in the mapping
  it is handed and has no per-collection filter; the engagement spec covers all six
  collections owned by five parallel batches, so the brief's recon command graded sibling
  batches' collections and failed Tier 1 on their (in-flight) counts. `scope_mapping.py`
  copies `.migration/03_mapping_spec.json` and `migration/mmp_rt/fixture_mapping_spec.json`
  verbatim and keeps only the `shares` row (version, notes and canonicalization block
  untouched). No mapping row was changed and no contract file was edited.
- **Indexes:** the loader recreates all non-`_id` source indexes with identical keys and
  options; `shares` has none, so both sides show only `_id_`.
- **M0 tier:** batches of 1000, `insert_many(ordered=False)`, single writer, `maxPoolSize=2`.
- **Redaction:** `RECON_REDACT_SALT` is unset; harness output is redacted with unsalted
  hashes (accepted, STOP A P4).

## Evidence

- `recon/fixture/` - fixture PASS (300 docs), not a merge verdict.
- `recon/live/` - live PASS, `merge_eligible=true`, 3000 docs, map-v1 / tol-v1 / seed 1.
- Idempotency: a second `--mode live` run reported `source=3000 inserted=3000 count=3000`.
