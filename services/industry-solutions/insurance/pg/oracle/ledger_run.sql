-- Ledger run on the Oracle fixture, as COMMISSION_PAY. The seed ships no
-- ledger rows, so before a migration is reconciled the legacy COMMISSION_PKG
-- calculates every in-force policy with a split allocation for each month
-- from its issue month through 2026-03. The range crosses the AUTO-STD
-- default rate change of 2026-01-01 written by the OLTP suite.
WHENEVER SQLERROR EXIT SQL.SQLCODE
SET SERVEROUTPUT ON FEEDBACK OFF

DECLARE
    l_calls PLS_INTEGER := 0;
BEGIN
    FOR p IN (SELECT po.policy_id, TRUNC(po.issued_date, 'MM') AS first_month
                FROM policies po
               WHERE po.status = 'IN_FORCE'
                 AND EXISTS (SELECT 1 FROM commission_splits s WHERE s.policy_id = po.policy_id)
               ORDER BY po.policy_id) LOOP
        FOR m IN 0 .. MONTHS_BETWEEN(DATE '2026-03-01', p.first_month) LOOP
            commission_pkg.calculate_policy_commission(
                p.policy_id, TO_CHAR(ADD_MONTHS(p.first_month, m), 'YYYY-MM'), 'ledger-run');
            l_calls := l_calls + 1;
        END LOOP;
    END LOOP;
    DBMS_OUTPUT.PUT_LINE('LEDGER RUN: ' || l_calls || ' policy-periods calculated');
END;
/
EXIT;
