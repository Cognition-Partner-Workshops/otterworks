# Customer unit live

Session 2 of the Oracle to MongoDB billing demo. Persona `mongodb` (group
Devin-Demo-MongoDB) in the Devin web app of the ViewOnly org. The audience
watches this session from the first live recon onward.

## Setup

Repository: `Cognition-Partner-Workshops/otterworks`, on the run branch
`tp-run/mongodb-<timestamp>` that session 1 created with
`make tp-run-branch TRACK=mongodb`. The migration database is
`ow_tp_billing_<timestamp>` with the same token.

Secrets by name only: `MONGODB_ATLAS_URI` for the dedicated user that holds
`readWrite` on the migration database and nothing else, `OW_TP_ORACLE_RO_DSN`
for the read-only Oracle principal. The scope check needs only
`MONGODB_ATLAS_URI`.

## Prompt

```
Work in Cognition-Partner-Workshops/otterworks on the branch tp-run/mongodb-<timestamp>. First run make tp-atlas-scope-check DB=ow_tp_billing_<timestamp> and stop if it is not PASS. Migrate unit U2 from the read-only Oracle source into the migration database on Atlas with ENTITY_ATTR_VALUE embedded as customers.attributes[], run the loader with two passes so the rerun is a no-op, run the live recon for customers and customers_hist, and fix whatever the recon rejects by changing the loader while leaving the tolerances untouched. Refer to secrets by environment variable name only. Do not edit the Oracle fixture, the recordings under procs/oracle/transcripts/, or the gate files migration/billing/recon/recon.py, migration/billing/tolerances.json, migration/billing/mapping_spec.json, migration/billing/units/units.json and migration/billing/scripts/atlas-scope-check.sh. Post the scope check output, both loader passes, the failing recon checks, your loader change and the passing recon in this session, then open the PR against the run branch.
```

The presenter pastes the prompt unchanged, since it names no cause for a
recon failure, and answers no question about the cause during the session.
Devin finding the cause is the point of this segment.

## Protected files

The Oracle fixture under `services/legacy-billing/db/oracle/` and its seed.
The recordings under `procs/oracle/transcripts/`. The gates `recon/recon.py`,
`tolerances.json`, `mapping_spec.json`, `units/units.json` and
`scripts/atlas-scope-check.sh` under `migration/billing/`, the schemas under
`docs/tech-partnerships/contracts/schema/`, and every file under
`migration/billing/fixtures/`. The fix belongs in
`migration/billing/loaders/`.

## Evidence posted in the session

1. The Atlas scope check output: roles exactly `readWrite` on the migration
   database, the denied probe refused with code 13, the allowed probe
   accepted, verdict PASS.
2. Loader pass 1 and pass 2, with pass 2 reported as a no-op.
3. The first live recon with verdict FAIL and the failing check ids.
4. The loader diff.
5. The rerun of the live recon with verdict PASS and `merge_evidence: true`,
   and `make tp-validate-recon FILE=<report>` passing on it.

Done means `recon.py run --mode live` reports `verdict: pass` and
`merge_evidence: true`, the second loader pass is a no-op, and the report
validates.

## Fallback

Show the local rehearsal: `make tp-u2-load` and `make tp-u2-recon` against the
`mongo:7` fixture produce the same FAIL, and the same loader change turns it
to PASS. Say plainly that a fixture result is never merge evidence.
