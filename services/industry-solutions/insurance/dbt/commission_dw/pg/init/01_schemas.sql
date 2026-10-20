-- Schemas mirror the Oracle owners in FREEPDB1:
--   commission_pay  landed sources (COMMISSION_PAY, OLTP system of record)
--   commission_dw   dbt models     (COMMISSION_DW, star schema + MV)
CREATE SCHEMA IF NOT EXISTS commission_pay AUTHORIZATION CURRENT_USER;
CREATE SCHEMA IF NOT EXISTS commission_dw AUTHORIZATION CURRENT_USER;
