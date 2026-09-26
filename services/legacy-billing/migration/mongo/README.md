# Mongo migration service code — wave 3, batch w3-b01

Units: **u-07-plsql-util** (PKG_OW_UTIL) and **u-08-plsql-plans**
(PKG_PLANS + triggers TRG_SUBSCRIPTIONS_HIST, TRG_SUB_NO_UNCANCEL).

`target_class=local` — fixture evidence only, **not merge evidence**
(live recon: not possible; the engagement is offline,
`source_access=ddl_only`, `auto_merge=false`).

## Files

- `ow_util.py` — PKG_OW_UTIL port: `md5_uuid` (f_md5_uuid), `code_desc`
  (f_code_desc, `UNKNOWN(n)` miss), `dt2str`/`str2dt` (`DD-MON-YY`,
  dirty → `None`), `money_round` (Oracle HALF-EVEN-style rounding to 2dp),
  `log_msg` (autonomous-commit equivalent: insert into `billingAuditLog`,
  swallows errors), `json_value`/`dec2` (BSON → transcript rendering).
- `plans_service.py` — PKG_PLANS port: `list_plans` (fn_list_plans),
  `entitlement` (fn_entitlement), `change_plan` (sp_change_plan) with
  `subscriptionsHist` writes replicating TRG_SUBSCRIPTIONS_HIST and the
  no-uncancel guard replicating TRG_SUB_NO_UNCANCEL.
- `fixture_load.py` — deterministic baseline loader: drops+recreates
  `ow_billing_migration.{codes,plans,tenants,subscriptions,
  subscriptionsHist,billingAuditLog}` from the Oracle fixture per
  `03_mapping_spec.json` and empties scratch `parity_w3_b01`.
- `parity_w3_b01.py` — replays `procs/oracle/transcripts/plans/*.json`
  against the service code (baseline reset per scenario) and runs u-07
  helper parity vs live read-only fixture calls; writes transcripts under
  `recon/<unit>/parity/` and summary docs into `parity_w3_b01`.
- `ops/*.ops.json` — Tier-4 read-only op transcripts (source SELECT +
  target aggregation pipeline) for the recon harness.
- `recon/<unit>/` — subset mapping specs + committed recon evidence.

## Usage (repo root, secrets by env-var NAME only)

    env -u MONGODB_ATLAS_URI \
      python3 services/legacy-billing/migration/mongo/fixture_load.py \
        --source-dsn-secret OW_BILLING_FIXTURE_DSN \
        --target-uri-secret MONGO_LOCAL_URI \
        --target-db ow_billing_migration

    env -u MONGODB_ATLAS_URI \
      python3 services/legacy-billing/migration/mongo/parity_w3_b01.py \
        --source-dsn-secret OW_BILLING_FIXTURE_DSN \
        --target-uri-secret MONGO_LOCAL_URI \
        --target-db ow_billing_migration

Write targets: `ow_billing_migration` spec collections used by the batch
plus declared scratch `ow_billing_migration.parity_w3_b01`.
