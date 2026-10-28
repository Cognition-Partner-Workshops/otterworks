# billing_history — unit contract (wave invoicing-1, batch w1-b01)

Snapshot copy of the OW_BILLING invoicing-history surface into Delta.

| Source | Target | Key |
|---|---|---|
| OW_BILLING.CUSTOMER_MASTER | ow_tp.ow_tp_invoicing_history.customer_master | cust_id |
| OW_BILLING.CUSTOMER_MASTER_HIST | ow_tp.ow_tp_invoicing_history.customer_master_hist | hist_id |
| OW_BILLING.ENTITY_ATTR_VALUE | ow_tp.ow_tp_invoicing_history.entity_attr_value | eav_id |
| OW_BILLING.INVOICE_HEADER | ow_tp.ow_tp_invoicing_history.invoice_header | invoice_id |
| OW_BILLING.INVOICE_LINE | ow_tp.ow_tp_invoicing_history.invoice_line | line_id |

Mapping: `.migration/units/billing_history/mapping_spec.json` (family oracle,
target databricks, rerun_posture first_run_baseline). Tolerances
`.migration/recon_tolerances.json` (tol-20261027-v1, live). Load posture: snapshot-only —
`extract.py` copies the tables to Parquet on the read-only principal, `--upload` lands
them on `ow_tp.ow_tp_invoicing_history.landing`, and the bundle job
`ow_tp_1793146609_snapshot_billing_history` (schedule PAUSED, target
`mig_1793146609`) recreates and overwrites the five tables. No federation/JDBC/CDC.

Type fidelity follows the oracle dialect skill's type_map (NUMBER(p,0) p<=18 -> BIGINT,
NUMBER(p,s) -> DECIMAL(p,s), DATE -> TIMESTAMP_NTZ, VARCHAR2/CHAR -> STRING); column
names are lowercased to match the mapping keys. `sql/ddl.sql` and
`target_schema.json` are generated from ALL_TAB_COLUMNS so target types are
deterministic, not inferred.

Recon: fixture-first (`--mode fixture` against the local seeded Oracle on
localhost:52521), then `--mode live` for merge evidence; evidence lands in
`.migration/recon/billing_history/`; rerun posture proven via `dbx-recon shape` +
`rerun-proof` (first_run_baseline: fresh leg only).
