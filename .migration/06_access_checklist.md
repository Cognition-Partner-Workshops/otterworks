# Access checklist and access model

## Capability checklist

| Capability | Principal / secret | Status | Evidence / request |
|---|---|---|---|
| Oracle catalog and data read | Dedicated read-only assessment DSN, proposed name `ORACLE_MIGRATION_READONLY_DSN` | BLOCKED | No running Oracle endpoint and no dedicated read-only source secret were found. Source owner must provision `CREATE SESSION` plus read-only catalog/object access, with no DML/DDL grants. |
| Atlas project read | `MONGODB_ATLAS_PUBLIC_KEY` / `MONGODB_ATLAS_PRIVATE_KEY` / `MONGODB_ATLAS_PROJECT_ID` | WORKS | `project-read`, HTTP 200 in `evidence/atlas-capabilities.json`. |
| Atlas cluster configuration read | Same Atlas API principal | WORKS | `cluster-read`, HTTP 200 in `evidence/atlas-capabilities.json`. |
| Atlas database-user read | Same Atlas API principal | WORKS | `db-user-read`, HTTP 200 in `evidence/atlas-capabilities.json`. |
| Atlas network access-list read/write cleanup | Same Atlas API principal | WORKS | GET, temporary POST, and DELETE all verified; temporary entry removed. |
| Atlas migration data read/write | `MONGODB_ATLAS_URI` | WORKS | Temporary insert/delete/drop in registered `ow_tp_preflight` verified and cleaned. |
| Atlas audit owner mapping | Atlas API key and database user | BLOCKED | Probe could not resolve `credential_identity`; Atlas owner must confirm the service-account owner before unit launch. |
| Full-estate target capacity | Shared `otterworks-demo` M0, approximately 512 MB | BLOCKED FOR LOAD | M0 is demo scale. Recommend M10+; alternatively allow phase 2 modeling only and require measured-fit approval at STOP B before any load. |
| Sample/source data approval | Complete approved census and read-only source population | BLOCKED | User requested complete discovered-object coverage; no narrowing is allowed. Data cannot move until source access and target capacity are approved. |
| Production repoint | Customer-held cutover principal | CUSTOMER HELD | Devin will not request, store, or execute it. |

## Access model

### Tier 1 — assessment

- Purpose: Oracle catalog census, read-only data profiling, extraction, and recon source reads.
- Required secret: `ORACLE_MIGRATION_READONLY_DSN` or an equivalent dedicated name approved at STOP A.
- Required privilege: session/connect plus read-only access to in-scope objects and the Oracle `ALL_*` or approved `DBA_*` catalog views used by the source profile.
- Forbidden: DML, DDL, scheduler changes, grants, sequence advancement, or source fixture seeding.

### Tier 2 — migration

- Purpose: Atlas project/cluster inspection, network-path management, target DDL, loading, and recon target reads.
- Secrets: `MONGODB_ATLAS_PUBLIC_KEY`, `MONGODB_ATLAS_PRIVATE_KEY`,
  `MONGODB_ATLAS_PROJECT_ID`, and `MONGODB_ATLAS_URI`.
- Allowed writes: registered temporary objects in `ow_tp_preflight` and exact unit targets
  registered under `ow_tp_mongodb_20260901t033738z`.
- Attribution: Atlas API and database audit/activity logs identify the programmatic API key
  and database user; unit PRs and recon results link each target to its session and branch.

### Tier 3 — cutover

- Purpose: production application/DNS/config repoint and rollback.
- Principal: customer-held only.
- Devin posture: no credential is requested or stored; the final runbook names the customer
  executor for every production-touching step.

## Fired access requests

1. **Oracle owner/DBA:** provision a dedicated read-only Oracle assessment principal and
   expose its DSN as `ORACLE_MIGRATION_READONLY_DSN`; grant only connect plus select on the
   approved schema and required catalog views. Suggested DBA-run template:

   ```sql
   CREATE USER OW_MIGRATION_RO IDENTIFIED BY "<generated-secret>";
   GRANT CREATE SESSION, SELECT_CATALOG_ROLE TO OW_MIGRATION_RO;

   SELECT 'GRANT SELECT ON "' || owner || '"."' || object_name ||
          '" TO OW_MIGRATION_RO;'
   FROM dba_objects
   WHERE owner = 'OW_BILLING'
     AND object_type IN ('TABLE', 'VIEW', 'MATERIALIZED VIEW', 'SEQUENCE');
   ```

   Review and execute the generated `GRANT SELECT` statements. Do not grant INSERT,
   UPDATE, DELETE, EXECUTE, or DDL privileges. The DBA may replace
   `SELECT_CATALOG_ROLE` with narrower catalog grants if the Oracle policy requires it.
2. **Atlas owner:** if the capability probe confirms M0, approve or provision an M10+
   migration cluster before any complete-estate load. Metadata-only census/modeling may
   continue after STOP A while capacity is pending, but no scope may be removed.
3. **Atlas owner:** name the owner of the API key and database user used by the migration
   principal so audit events can be attributed before unit launch.
