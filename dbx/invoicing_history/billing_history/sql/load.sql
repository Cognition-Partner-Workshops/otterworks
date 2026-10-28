-- billing_history snapshot load: landing volume -> Delta (idempotent full overwrite).
-- The parquet under landing/billing_history/ is produced by extract.py from the
-- OW_BILLING read-only snapshot; INSERT OVERWRITE rewrites each table atomically so a
-- rerun converges to the latest landed extract.

INSERT OVERWRITE TABLE ow_tp.ow_tp_invoicing_history.customer_master
SELECT * FROM parquet.`/Volumes/ow_tp/ow_tp_invoicing_history/landing/billing_history/customer_master.parquet`;

INSERT OVERWRITE TABLE ow_tp.ow_tp_invoicing_history.customer_master_hist
SELECT * FROM parquet.`/Volumes/ow_tp/ow_tp_invoicing_history/landing/billing_history/customer_master_hist.parquet`;

INSERT OVERWRITE TABLE ow_tp.ow_tp_invoicing_history.entity_attr_value
SELECT * FROM parquet.`/Volumes/ow_tp/ow_tp_invoicing_history/landing/billing_history/entity_attr_value.parquet`;

INSERT OVERWRITE TABLE ow_tp.ow_tp_invoicing_history.invoice_header
SELECT * FROM parquet.`/Volumes/ow_tp/ow_tp_invoicing_history/landing/billing_history/invoice_header.parquet`;

INSERT OVERWRITE TABLE ow_tp.ow_tp_invoicing_history.invoice_line
SELECT * FROM parquet.`/Volumes/ow_tp/ow_tp_invoicing_history/landing/billing_history/invoice_line.parquet`;
