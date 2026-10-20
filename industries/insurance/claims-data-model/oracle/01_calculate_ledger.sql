-- Writes the commission ledger with the legacy logic itself: COMMISSION_PKG.calculate_policy_commission
-- for every in-force policy that has a split allocation, every month 2025-06 (the period the fixture's own
-- suite calculates) to 2026-10 (the month the claims corpus payments are value-dated). Re-running replaces
-- the same rows (the procedure is idempotent per policy and period).
WHENEVER SQLERROR EXIT SQL.SQLCODE
SET SERVEROUTPUT ON FEEDBACK OFF HEADING OFF PAGESIZE 0
BEGIN
    FOR p IN (SELECT po.policy_id
                FROM policies po
               WHERE po.status = 'IN_FORCE'
                 AND EXISTS (SELECT 1 FROM commission_splits s WHERE s.policy_id = po.policy_id)
               ORDER BY po.policy_id) LOOP
        FOR m IN 0 .. 16 LOOP
            commission_pkg.calculate_policy_commission(
                p.policy_id, TO_CHAR(ADD_MONTHS(DATE '2025-06-01', m), 'YYYY-MM'), 'claims-data-model');
        END LOOP;
    END LOOP;
END;
/
SELECT 'ledger rows=' || COUNT(*) || ' commission=' || TO_CHAR(SUM(commission_amt), 'FM999999990.00')
  FROM commission_ledger;
EXIT;
