-- Warehouse load after ledger_run.sql, as COMMISSION_DW: the legacy
-- DW_ETL_PKG merges every period into the star schema, then the summary
-- materialized view is completely refreshed.
WHENEVER SQLERROR EXIT SQL.SQLCODE
SET SERVEROUTPUT ON FEEDBACK OFF

DECLARE
    l_merged PLS_INTEGER;
BEGIN
    dw_etl_pkg.load_commission_facts(NULL, l_merged);
    DBMS_MVIEW.REFRESH('MV_AGENT_COMMISSION_SUMMARY', 'C');
    DBMS_OUTPUT.PUT_LINE('DW LOAD: ' || l_merged || ' fact rows merged, MV refreshed');
END;
/
EXIT;
