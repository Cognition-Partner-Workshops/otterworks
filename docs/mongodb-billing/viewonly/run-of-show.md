# Run of show

The Oracle to MongoDB billing demo in the ViewOnly org, about 25 minutes live.
Three sessions, one run branch `tp-run/mongodb-<timestamp>` and one migration
database `ow_tp_billing_<timestamp>` with the same token.

## The day before

1. Confirm the blueprint items in `READINESS.md` are in the snapshot: the
   billing worker venv, the `mongo:7` image and the Oracle Free image.
2. A human creates the dedicated Atlas user for the new run token with the
   command in `migration/billing/README.md` and points `MONGODB_ATLAS_URI` at
   it. `OW_TP_ORACLE_RO_DSN` is set only when a live Oracle is wanted.
3. Run session 1 from `census-and-plan.md`. It creates the run branch, so the
   token is known from here on. Approve the plan.
4. Start session 3 from `switch-and-verify.md` only after session 2 has merged;
   the night before, check that the prompts still carry the right token.

## Live

1. Open on the census and plan from session 1. Name the 19 tables in scope,
   the 25,000 demo customers and the attribute rows that become
   `customers.attributes[]`.
2. Start session 2 from `customers-unit-live.md`. The scope check passes, the
   loader runs twice and the second pass is a no-op.
3. The first live recon fails on the customer collection. Let Devin read the
   report and change the loader. Say nothing about the cause.
4. The rerun of the live recon passes with `merge_evidence: true`.
5. Session 3: switch the customer module to `BILLING_BACKEND=mongo` and refresh
   both panes for the same tenant. Same request, same answer, two databases.
6. Close on the evidence table and the scope check output.

## Fallback

When Atlas is unreachable, run steps 2 to 4 against the local fixtures with
`make tp-u2-load`, `make tp-u2-recon` and `make tp-u2-parity`, and say that a
fixture result is never merge evidence.

## Reset

```bash
make tp-mongodb-reset TARGET=atlas DB=ow_tp_billing_<timestamp> RESEED=1
make tp-mongodb-reset                          # local mongo:7 fixture
```

Then delete the run's Atlas user with the command in
`migration/billing/README.md` and serve the billing service on
`BILLING_BACKEND=oracle` again. A new run starts from `main` with
`make tp-run-branch TRACK=mongodb`.
