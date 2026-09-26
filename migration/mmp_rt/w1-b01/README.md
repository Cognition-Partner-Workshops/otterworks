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

## Status: BLOCKED before the live run
The brief's fixture recon command (`recon/fixture/`) FAILs in Tier 1 on `shares` and
`audit_events`: the command passes the whole mapping spec (all six collections), and those two
collections belong to w1-b04/w1-b05 and were not yet loaded. `users`/`folders` passed Tier 1.
The harness has no collection filter and the mapping has no per-batch scoping, so this batch
cannot reach PASS without depending on (and certifying) other batches' collections.
A diagnostic fixture run with a scratch mapping restricted to the users/folders rows (not
committed, not merge evidence) PASSed Tiers 1-3 (2 / 9 / 80 checks).
No live load or live recon was run.
