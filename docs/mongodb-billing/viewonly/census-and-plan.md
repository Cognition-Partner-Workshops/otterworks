# Census and plan

Session 1 of the Oracle to MongoDB billing demo. Persona `dba` (group
Devin-Demo-DBA) on the Migrations page of the ViewOnly org. Run before the
audience joins; the presenter walks the result.

## Setup

Repository: `Cognition-Partner-Workshops/otterworks`, base branch `main`.

Branch: the session creates the run branch itself with
`make tp-run-branch TRACK=mongodb`. The target cuts `tp-run/mongodb-<timestamp>`
from `main` and stamps the migration database `ow_tp_billing_<timestamp>`.
Every later session and PR of the run uses that branch and that token.

Secrets by name only: `OW_TP_ORACLE_RO_DSN` for the read-only Oracle
principal, `MONGODB_ATLAS_URI` for the dedicated user. When
`OW_TP_ORACLE_RO_DSN` is not set the session uses the local fixture from
`make oracle-billing-up` and says so.

## Prompt

```
Work in Cognition-Partner-Workshops/otterworks. Run make tp-run-branch TRACK=mongodb and work only on the branch it prints. Take a census of the running Oracle OW_BILLING schema through the read-only DSN in OW_TP_ORACLE_RO_DSN, map every legacy-billing Flask entrypoint to the PL/SQL, tables and transaction boundary it uses, and produce the MongoDB Atlas migration plan as units with embed-or-reference decisions, dependencies and a live reconciliation gate per unit. Refer to secrets by environment variable name only. Do not edit the Oracle fixture under services/legacy-billing/db/oracle/, the recordings under procs/oracle/transcripts/, or the gate files migration/billing/recon/recon.py, migration/billing/tolerances.json, migration/billing/mapping_spec.json, migration/billing/units/units.json and migration/billing/scripts/atlas-scope-check.sh. Post the census table, the access pattern table and the plan in this session before you open the PR.
```

## Protected files

The Oracle fixture under `services/legacy-billing/db/oracle/` and its seed
`testdata/legacy/oracle_billing_seed.py`. The recordings under
`procs/oracle/transcripts/`. The validators and gates: `recon/recon.py`,
`tolerances.json`, `mapping_spec.json`, `units/units.json` and
`scripts/atlas-scope-check.sh` under `migration/billing/`, and the schemas
under `docs/tech-partnerships/contracts/schema/`.

## Evidence posted in the session

1. The census table: tables in `OW_BILLING`, the tables in scope, rows per
   table, the `CUSTOMER_MASTER` column count, and the `ENTITY_ATTR_VALUE` row
   count with how many customers carry attributes.
2. The access pattern table: each Flask entrypoint with its PL/SQL package,
   tables and transaction boundary.
3. The plan: units with their collections, the embed or reference decision for
   each child table (`ENTITY_ATTR_VALUE` embedded as `customers.attributes[]`),
   dependencies, and the live recon gate per unit.
4. The run branch name and the migration database name.

Done means the plan holds the census, the access patterns, the unit list with
dependencies and the recon gate, and the board shows one ticket per unit.

## Fallback

Open `migration/billing/units.md`, `migration/billing/access_patterns.md` and
`migration/billing/census/README.md` on `main`. They are the plan of the
reference run and carry the same tables and units.
