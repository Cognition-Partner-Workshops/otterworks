# 06 — Access Checklist and Access Model

## Probes (2026-09-01, this session)

| Capability | Status | Evidence |
|---|---|---|
| Oracle `OW_BILLING` read | WORKS | `ow_billing@localhost:52521/FREEPDB1`: `USER_OBJECTS` census (20 tables, 25 indexes, 5 seq, 5 pkg+body, 7 triggers, 2 jobs); `COUNT(*) CUSTOMER_MASTER = 25000`; server 23.26.3.0.0 |
| Postgres documents read | WORKS | `otterworks@localhost:5432/otterworks`, schema `otterworks_demo`: documents 2000 / document_versions 13876 / document_snapshots 390 (matches manifest) |
| DynamoDB file metadata read | WORKS | LocalStack `:4566`, table `otterworks-file-metadata`, 10000 items scanned, `ns = demo` |
| Fixture population pinned | WORKS | `testdata/legacy/manifests/demo.json` (seed 714559852; Oracle CUSTOMER_MASTER 25000, EAV 8333, INVOICE_HEADER 18750, INVOICE_LINE 150000 (37 orphans), TENANTS 60) |
| Atlas project / cluster / DB-user read | WORKS | `make tp-preflight PLATFORM=atlas` → HTTP 200 ×3 |
| Atlas access list read/write/delete | WORKS | POST 201, DELETE 204; VM IP covered by 6 entries |
| Atlas data-plane write + cleanup | WORKS | temporary collection written and dropped via `MONGODB_ATLAS_URI` |
| Migration DB `ow_tp_mongodb_205236` | NOT YET CREATED | created on first registered load, never before STOP B |
| Source write | NOT ATTEMPTED (forbidden) | assessment principal used read-only by policy |
| Customer cutover principal | N/A | customer-held; Devin never requests it |

BLOCKED items: **none**. No access requests fired.

Fixture credentials are the repository's local development defaults for Docker fixtures
(`docker-compose.yml`, `docker-compose.oracle-billing.yml`); they are not organisation
secrets and are not recorded here beyond user/host.

## Access model (for the security reviewer)

| Tier | Purpose | Principal / secrets | Scope | Attribution |
|---|---|---|---|---|
| Assessment | census, extract, recon source side | fixture dev users (Oracle `ow_billing`, Postgres `otterworks`, LocalStack test keys) | read-only by policy; no DDL/DML issued | connection `program`/`module` = Devin session id; Docker logs on the VM |
| Migration | load + recon target side; access-list self-service | `MONGODB_ATLAS_URI`, `MONGODB_ATLAS_PUBLIC_KEY`, `MONGODB_ATLAS_PRIVATE_KEY`, `MONGODB_ATLAS_PROJECT_ID` | databases `ow_tp_mongodb_205236`, `ow_tp_mongodb_205236_quarantine` only | Atlas project activity feed + access-list audit (API-key identity); every write carries `ns: "mongo_205236"` |
| Cutover | production repoint, rollback | customer-held | production config/DNS | customer's change record; Devin runs verification only with the migration principal |

Revocation of the migration principal is part of the decommission plan (playbook 5).
