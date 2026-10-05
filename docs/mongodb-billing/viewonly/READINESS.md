# Readiness

State of the Oracle to MongoDB billing demo after the builder rehearsal of
2026-10-05 on a builder VM, against the Oracle fixture and the local `mongo:7`
fallback. No Atlas cluster was contacted.

## Secrets a human provides

| Name | Required | Purpose |
|---|---|---|
| `MONGODB_ATLAS_URI` | Yes | Connection string of the dedicated user that holds exactly `readWrite@ow_tp_billing_<timestamp>` |
| `MONGODB_ATLAS_PROJECT_ID` | Optional | Project id for the Atlas CLI user creation and deletion |
| `MONGODB_ATLAS_PUBLIC_KEY` | Optional | Atlas API public key for the same CLI commands |
| `MONGODB_ATLAS_PRIVATE_KEY` | Optional | Atlas API private key for the same CLI commands |
| `OW_TP_ORACLE_RO_DSN` | Only for a live Oracle | Read-only Oracle principal; without it every session uses the local fixture |

The dedicated user is created per run token with the command in
`migration/billing/README.md`. An over-scoped principal fails the scope check
and is not accepted for a run.

## Blueprint changes

`migration/billing/env/blueprint-proposal.diff` holds the full proposal. The
snapshot needs the worker venv and both images:

1. The billing migration worker venv at `/home/ubuntu/.venvs/ow-billing` with
   `oracledb==2.5.1` and `pymongo==4.10.1`.
2. The `mongo:7` image pulled. Docker Hub answered the builder pull with
   `429 Too Many Requests`; pulling `mirror.gcr.io/library/mongo:7` and tagging
   it `mongo:7` worked.
3. The Oracle fixture image `container-registry.oracle.com/database/free:latest`
   pulled, so `make oracle-billing-up` does not download it during a session.

The builder VM also had no `mongosh`, no MongoDB Database Tools and no Atlas
CLI. The post setup check now pings the fallback through the shell inside the
`mongo:7` container, but `make tp-mongodb-reset TARGET=atlas` and the human
user creation need `mongosh` and the Atlas CLI on the host.

## Measured in the rehearsal

| Item | Value | Command | UTC |
|---|---|---|---|
| Tables in `OW_BILLING` | 20 | `select count(*) from user_tables` in the fixture | 2026-10-05T07:58:16Z |
| Tables in scope (migrate bucket of `census/buckets.json`) | 19, all present | `user_tables` filtered by the bucket list | 2026-10-05T07:58:16Z |
| `CUSTOMER_MASTER` rows | 25,001 (25,000 seeded for `NS=demo` plus 1 static) | `select count(*)` | 2026-10-05T07:58:16Z |
| `CUSTOMER_MASTER` columns | 155 | `user_tab_columns` | 2026-10-05T07:58:16Z |
| `ENTITY_ATTR_VALUE` rows | 8,337 (8,333 seeded plus 4 static) on 7,076 customers, at most 5 per customer | `select count(*)` | 2026-10-05T07:58:16Z |
| `INVOICE_HEADER` and `INVOICE_LINE` rows | 18,750 and 150,000, 37 orphan lines | `select count(*)` | 2026-10-05T07:58:16Z |
| PL/SQL packages | 5 | `user_objects` | 2026-10-05T07:58:16Z |
| Flask access patterns | 12 entrypoints over 5 packages and 19 tables; 79 cites checked, 1 unresolved | `python3 migration/billing/access_patterns/check.py` | 2026-10-05T07:57:52Z |
| Post setup check, auto mode | mongo PASS fallback, oracle PASS fallback, schemas PASS | `OW_BILLING_ENV_MODE=auto migration/billing/env/postsetup-check.sh all` | 2026-10-05T07:58:55Z |
| Schema validation | ok | `make tp-validate-schemas` | 2026-10-05T07:58:56Z |
| U2 load pass 1 | customers +25,001 upserted, 8,337 attribute elements, customers_hist 0 | `make tp-u2-load` | 2026-10-05T07:58:56Z |
| U2 load pass 2 | 25,001 matched, 0 modified, no-op | `make tp-u2-load` | 2026-10-05T07:59:08Z |
| Recon, live mode on the VM | refused before connecting: `OW_TP_ORACLE_RO_DSN` is not set | `recon.py run --mode live` | 2026-10-05T07:59:23Z |
| Recon, local mode | verdict fail, 28 checks, 26 pass, 2 fail on the customer collection | `make tp-u2-recon` | 2026-10-05T07:59:24Z |
| Customer route parity | fail on `/customer` for the tenant with attributes, identical elsewhere | `make tp-u2-parity` | 2026-10-05T08:00:22Z |
| Reset of the fallback | 3 databases dropped; only `admin`, `config` and `local` remain | `make tp-mongodb-reset` | 2026-10-05T08:00:53Z |
| Scope check without `MONGODB_ATLAS_URI` | FAIL, exit 2, no connection attempted | `env -u MONGODB_ATLAS_URI migration/billing/scripts/atlas-scope-check.sh --db ow_tp_billing_x` | 2026-10-05T08:00:32Z |

The local recon failure is the planted one the customer session has to find.
It is left in place.

## Known blockers

1. No Atlas credentials were available to the builder, so the scope check, the
   live load and the live recon against Atlas are not rehearsed. They need
   `MONGODB_ATLAS_URI` for a dedicated user.
2. `scripts/check-redaction.sh` does not exist on `main` or on the source
   branches. The builder ran a pattern scan over the diff instead.
3. `migration/billing/access_patterns.md` cites
   `frontend/admin-dashboard/src/app/core/services/billing-report.service.ts`,
   which is not on `main`, so `access_patterns/check.py` reports one
   unresolved cite. Session 1 regenerates the document for its run.
