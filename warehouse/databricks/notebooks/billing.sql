-- Databricks notebook source
-- Scaffold only. The migration supplies converted expressions; baseline data is never the target.
/* run=dbx-d1111 act=prove step=invoice-table consumer=billing */
CREATE TABLE IF NOT EXISTS cpw.dbx_d1111_after.invoice_revenue (
  invoice_id BIGINT, customer_id BIGINT, currency_cd STRING, total_amount DECIMAL(14,2)
) USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24';

-- COMMAND ----------
/* run=dbx-d1111 act=prove step=invoice-view consumer=billing */
CREATE OR REPLACE VIEW cpw.dbx_d1111_after.v_invoice_revenue
COMMENT 'run_token=dbx-d1111 expires=2026-11-24'
AS SELECT invoice_id, customer_id, currency_cd, total_amount
FROM cpw.dbx_d1111_after.invoice_revenue;
