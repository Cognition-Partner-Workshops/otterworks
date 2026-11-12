-- Ledger triggers (owner: COMMISSION_PAY).
WHENEVER SQLERROR EXIT SQL.SQLCODE

CREATE OR REPLACE TRIGGER trg_ledger_monthly_cap
BEFORE INSERT ON commission_ledger
FOR EACH ROW
WHEN (NEW.entry_type = 'COMMISSION')
DECLARE
    c_monthly_cap CONSTANT NUMBER := 2500;
    l_paid        NUMBER;
BEGIN
    SELECT NVL(SUM(commission_amt), 0)
      INTO l_paid
      FROM commission_ledger
     WHERE agent_id = :NEW.agent_id
       AND period_month = :NEW.period_month
       AND entry_type = 'COMMISSION'
       AND policy_id <> :NEW.policy_id;

    IF l_paid + :NEW.commission_amt > c_monthly_cap THEN
        :NEW.commission_amt := GREATEST(c_monthly_cap - l_paid, 0);
    END IF;
END;
/

EXIT;
