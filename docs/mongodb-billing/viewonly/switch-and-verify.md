# Switch and verify

Session 3 of the Oracle to MongoDB billing demo. Persona `backend` (group
Devin-Demo-Backend) for the switch, then persona `dba` for the evidence table,
in the Devin web app of the ViewOnly org. Prepared before the demo; the two
pane refresh happens live.

## Setup

Repository: `Cognition-Partner-Workshops/otterworks`, on the run branch
`tp-run/mongodb-<timestamp>` from session 1, after the customer unit PR from
session 2 has merged into it.

Environment by name only: `BILLING_BACKEND` selects the backend of the billing
service (`oracle` before the switch, `mongo` after it), `MONGODB_ATLAS_URI`
for the dedicated user, `OW_TP_ORACLE_RO_DSN` for the read-only Oracle
principal.

## Prompt for the backend persona

```
Work in Cognition-Partner-Workshops/otterworks on the branch tp-run/mongodb-<timestamp>. Serve the customer module on BILLING_BACKEND=mongo for the demo tenant, prove GET /api/v1/billing/customer and the customer key of /me answer identically on the Oracle and MongoDB backends, and post both responses for the same customer side by side in this session. Refer to secrets by environment variable name only. Do not edit the Oracle fixture, the recordings under procs/oracle/transcripts/, or the gate files under migration/billing/ (recon/recon.py, tolerances.json, mapping_spec.json, units/units.json, scripts/atlas-scope-check.sh).
```

## Prompt for the dba persona

```
Work in Cognition-Partner-Workshops/otterworks on the branch tp-run/mongodb-<timestamp>. Run make tp-atlas-scope-check DB=ow_tp_billing_<timestamp> for the dedicated user, rerun the live recon across the merged units, and publish the table of tables migrated with their live recon verdict, source rows and documents per collection, with the path each number was read from. Refer to secrets by environment variable name only and edit none of the gate files.
```

## Protected files

The Oracle fixture, its seed and the recordings under
`procs/oracle/transcripts/`. The gate files `recon/recon.py`,
`tolerances.json`, `mapping_spec.json`, `units/units.json` and
`scripts/atlas-scope-check.sh` under `migration/billing/`, and the schemas
under `docs/tech-partnerships/contracts/schema/`.

## Evidence posted in the session

1. Two panes for one customer of the demo tenant: the response from
   `BILLING_BACKEND=oracle` and the response from `BILLING_BACKEND=mongo`,
   identical field for field, attributes included.
2. The parity report for `/api/v1/billing/customer` and `/me.customer`.
3. The Atlas scope check output with verdict PASS.
4. The live recon across the merged units with verdict PASS.
5. The evidence table: each migrated table, its collection, source rows,
   documents, live recon verdict and the report path.

Done means the parity report shows identical responses on both backends, the
scope check is PASS, and the evidence table lists each migrated table with its
recon verdict.

## Fallback

Run `make tp-u2-parity` against the local fixtures after the loader fix and
show its report, and open the recorded two pane view.
