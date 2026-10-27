# Global Fleet parity experiments

This package captures three different views of the legacy Global Fleet behavior:

- [`jsf/`](jsf/README.md) records and replays the live JSF portal.
- [`mainframe/`](mainframe/README.md) validates committed batch holdouts and self-tests
  a reference port of `FLEBEN01`.
- [`naive-load/`](naive-load/REPORT.md) demonstrates what a straightforward relational migration
  rejects or changes.

## JSF portal

The corpus contains 40 cases across seven contexts: employees (4), assignment (4),
request (11), mileage (6), statement (6), return (6), and static resources (3). The full
live replay after a fresh tenant reset reported `IDENTICAL` for all 40 cases, including
media type, visible text, non-HTML bodies, and clock-normalized dates. The immediate
post-replay reset also succeeded. Per-context output and the refreshed replay summary are
committed under [`jsf/evidence/`](jsf/evidence/); the offline `jsf/selftest.py` covers
date shifts and deliberate health/wizard differences.

Both requested `gf-before` resets loaded 215 employees and 120 vehicles. The reset script
reported that `otterworks-gf-after` was not deployed and skipped it.

## Mainframe holdouts

There is no IDMS runtime in this sandbox, so `FLEBEN01` cannot be run here. The 12
committed pairs `HP-202510` through `HP-202609` stand in for it; 202610 remains an open
period with no expected output. `EMPLOYEE.dat` is keyed by `dbkey`, not the non-unique
`empid`; duplicate keys within a file now stop pair generation. Every pair and the
current unload contain 217 employee rows, and each pair's employee records are an exact
subset by `dbkey`.

| Employee rows | Holdout pairs | Current unload | Employee relation |
|---:|---:|---:|---|
| 217 in each of 12 pairs | HP-202510–HP-202609 | 217 | 12/12 exact subsets |

All five holdout input files in every pair are exact subsets of the current unload: there
are no pair-only rows or same-key changed rows. Pair-specific current-only keys are
recorded in `mainframe/pairs.json`. All 84 checksum-manifest entries and 84 metadata file
entries verify.

All 12 pairs pass BENOUT/BENRPT consistency checks. The reference port produced
byte-identical BENOUT and BENRPT files for all 12 pairs (12/12 of each), with no
differing record. See [`mainframe/README.md`](mainframe/README.md) for pair counts,
commands, and the full findings.

## Naive relational load

`naive-load/naive_schema.sql` defines the IDMS tables without dbkeys and includes the
member foreign keys and one-open-assignment index. `naive-load/load_naive.py` inserts
unload records one at a time, loads the JSF seed into `jsf_seed`, attempts a single-key
global employee merge, and records rejected rows and comparison queries in
[`naive-load/results.json`](naive-load/results.json).

In the recorded run, the naive IDMS schema accepted 1,090 rows and rejected 890:
2 employee primary-key conflicts, 20 open-assignment uniqueness conflicts, and 868
claims whose vehicle key was null. The global merge inserted 215 IDMS employees and 200
JSF employees; 15 JSF rows conflicted on the shared employee-number primary key. The
current-car query returned 81 rows. For 202609, the loaded-data query returned 11,280
approved miles and 5,019.67 reimbursement, versus 34,306 miles and 15,266.40 in
`HP-202609` BENOUT (differences of -23,026 miles and -10,246.73).

The experiment uses the PostgreSQL 16 image `mirror.gcr.io/library/postgres:16`, bound
to `127.0.0.1:5432` in the local container `gf-parity-postgres16`. To rerun the load
against that database:

```sh
UV_PYTHON=3.12 uv run --python 3.12 --with 'psycopg[binary]==3.2.9' \
  python industries/manufacturing/global-fleet/parity/naive-load/load_naive.py
```

The loader emits a `REJECTED` JSON line for every rejected row and writes the compact
counts, representative samples, loaded row counts, merge outcomes, and business-query
comparisons to `naive-load/results.json`.
