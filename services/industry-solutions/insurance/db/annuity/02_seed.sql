WHENEVER SQLERROR EXIT SQL.SQLCODE

DECLARE
    v_contract NUMBER(10);
    v_status VARCHAR2(2);
    v_funds PLS_INTEGER;
    v_pct NUMBER(5,2);
    v_account NUMBER(15,2);
    v_fund_value NUMBER(15,2);
BEGIN
    FOR i IN 1..100 LOOP
        v_contract := CASE
            WHEN i <= 35 THEN 1200000 + i * 137
            WHEN i <= 70 THEN 24000000 + i * 271
            WHEN i <= 95 THEN 360000000 + i * 389
            ELSE 4700000000 + i * 503
        END;
        v_status := CASE
            WHEN i > 95 THEN 'DP'
            WHEN MOD(i, 10) = 0 THEN 'PI'
            WHEN MOD(i, 10) = 1 THEN 'LP'
            WHEN MOD(i, 10) = 2 THEN 'SR'
            WHEN MOD(i, 10) = 3 THEN 'TM'
            ELSE 'IF'
        END;
        INSERT INTO annuity_policy VALUES (
            v_contract,
            'ANN-' || TO_CHAR(MOD(i, 3) + 1),
            CASE MOD(i, 3) WHEN 0 THEN 'Flexible Growth Annuity'
                WHEN 1 THEN 'Steady Income Annuity' ELSE 'Deferred Value Annuity' END,
            CASE MOD(i, 2) WHEN 0 THEN 'FLEX' ELSE 'FIXED' END,
            CASE MOD(i, 3) WHEN 0 THEN 'IRA' WHEN 1 THEN 'NQ' ELSE 'ROTH' END,
            v_status, DATE '2015-01-01' + i * 17,
            DATE '2015-01-01' + i * 17 + 7,
            ADD_MONTHS(DATE '2015-01-01' + i * 17 + 7, 360),
            CASE MOD(i, 4) WHEN 0 THEN 'CO' WHEN 1 THEN 'AZ' WHEN 2 THEN 'OR' ELSE 'UT' END,
            'Synthetic Owner ' || TO_CHAR(i, 'FM000'),
            'Synthetic Annuitant ' || TO_CHAR(i, 'FM000'),
            'USD', CASE MOD(i, 3) WHEN 0 THEN '0' WHEN 1 THEN '1' ELSE '3' END
        );

        v_account := 50000 + i * 1250;
        INSERT INTO policy_values VALUES (
            v_contract, DATE '2026-06-30', v_account, v_account - 1500,
            v_account - 1500, 45000 + i * 1100, i * 50,
            v_account + 5000, 1500
        );

        v_funds := MOD(i - 1, 5) + 1;
        FOR j IN 1..v_funds LOOP
            v_pct := CASE WHEN j = v_funds THEN 100 - TRUNC(100 / v_funds, 2) * (v_funds - 1)
                          ELSE TRUNC(100 / v_funds, 2) END;
            v_fund_value := ROUND(v_account * v_pct / 100, 2);
            INSERT INTO fund_allocation VALUES (
                v_contract, 'FND-' || TO_CHAR(j, 'FM00'),
                CASE j WHEN 1 THEN 'Balanced Growth Fund'
                    WHEN 2 THEN 'Stable Income Fund' WHEN 3 THEN 'Broad Equity Fund'
                    WHEN 4 THEN 'Short Duration Fund' ELSE 'Diversified Reserve Fund' END,
                v_pct, v_fund_value / 10, 10, v_fund_value
            );
        END LOOP;
    END LOOP;
    COMMIT;
END;
/

EXIT;
