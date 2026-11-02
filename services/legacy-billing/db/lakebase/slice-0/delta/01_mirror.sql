-- unt19-20261030 slice-0: Delta mirror of the shared reference tables, read from the frozen
-- OW_BILLING snapshot (policy.source.access = ow_tp.mig_unt19_20261030_src). The Lakebase synced
-- tables read from here, and the finance slice decodes INV_STATUS through CODES here
-- (d-codes-on-delta: seed-on-delta). One statement per block; run_sql.py executes them in order.
CREATE SCHEMA IF NOT EXISTS ow_tp.mig_unt19_20261030_slice_0
  COMMENT 'unt19-20261030 slice-0: shared reference mirror (CODES, PLANS, TENANTS) from the frozen OW_BILLING snapshot';

CREATE OR REPLACE TABLE ow_tp.mig_unt19_20261030_slice_0.codes
  COMMENT 'OW_BILLING.CODES magic-number lookup, kept as data (never inlined); d-codes-on-delta seed'
  AS SELECT code_type, code_val, code_desc
     FROM ow_tp.mig_unt19_20261030_src.codes;

ALTER TABLE ow_tp.mig_unt19_20261030_slice_0.codes ALTER COLUMN code_type SET NOT NULL;

ALTER TABLE ow_tp.mig_unt19_20261030_slice_0.codes ALTER COLUMN code_val SET NOT NULL;

ALTER TABLE ow_tp.mig_unt19_20261030_slice_0.codes ALTER COLUMN code_desc SET NOT NULL;

ALTER TABLE ow_tp.mig_unt19_20261030_slice_0.codes ADD CONSTRAINT pk_codes PRIMARY KEY (code_type, code_val);

CREATE OR REPLACE TABLE ow_tp.mig_unt19_20261030_slice_0.plans
  COMMENT 'OW_BILLING.PLANS reference rows'
  AS SELECT id, code, tier_cd, monthly_fee, included_units, overage_rate, active_yn
     FROM ow_tp.mig_unt19_20261030_src.plans;

ALTER TABLE ow_tp.mig_unt19_20261030_slice_0.plans ALTER COLUMN id SET NOT NULL;

ALTER TABLE ow_tp.mig_unt19_20261030_slice_0.plans ADD CONSTRAINT pk_plans PRIMARY KEY (id);

CREATE OR REPLACE TABLE ow_tp.mig_unt19_20261030_slice_0.tenants
  COMMENT 'OW_BILLING.TENANTS reference rows (id, name, tax_exempt_yn, status_cd)'
  AS SELECT id, name, tax_exempt_yn, status_cd
     FROM ow_tp.mig_unt19_20261030_src.tenants;

ALTER TABLE ow_tp.mig_unt19_20261030_slice_0.tenants ALTER COLUMN id SET NOT NULL;

ALTER TABLE ow_tp.mig_unt19_20261030_slice_0.tenants ADD CONSTRAINT pk_tenants PRIMARY KEY (id);
