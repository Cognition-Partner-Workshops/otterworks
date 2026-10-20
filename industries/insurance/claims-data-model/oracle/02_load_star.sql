-- Loads every ledger period into the star schema with DW_ETL_PKG and refreshes the reporting MV
-- the commission-by-agent mart is checked against.
WHENEVER SQLERROR EXIT SQL.SQLCODE
SET SERVEROUTPUT ON FEEDBACK OFF HEADING OFF PAGESIZE 0
DECLARE
    l_merged PLS_INTEGER;
BEGIN
    dw_etl_pkg.load_commission_facts(NULL, l_merged);
    DBMS_MVIEW.REFRESH('MV_AGENT_COMMISSION_SUMMARY', 'C');
    DBMS_OUTPUT.PUT_LINE('facts merged=' || l_merged);
END;
/
EXIT;
