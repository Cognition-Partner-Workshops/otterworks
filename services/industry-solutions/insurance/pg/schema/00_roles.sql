-- Roles and schemas for the PostgreSQL 16 target of Commission Pay.
-- Mirrors the Oracle fixture: two owners, COMMISSION_PAY (OLTP) and
-- COMMISSION_DW (OLAP), in one database. Fixture credentials match the
-- Oracle fixture and are local-only.
\set ON_ERROR_STOP on

CREATE ROLE commission_pay LOGIN PASSWORD 'commission_pay';
CREATE ROLE commission_dw  LOGIN PASSWORD 'commission_dw';

CREATE SCHEMA commission_pay AUTHORIZATION commission_pay;
CREATE SCHEMA commission_dw  AUTHORIZATION commission_dw;

ALTER ROLE commission_pay SET search_path = commission_pay;
ALTER ROLE commission_dw  SET search_path = commission_dw;

-- Oracle: GRANT SELECT ANY TABLE ON SCHEMA commission_pay TO commission_dw.
GRANT USAGE ON SCHEMA commission_pay TO commission_dw;
ALTER DEFAULT PRIVILEGES FOR ROLE commission_pay IN SCHEMA commission_pay
    GRANT SELECT ON TABLES TO commission_dw;
