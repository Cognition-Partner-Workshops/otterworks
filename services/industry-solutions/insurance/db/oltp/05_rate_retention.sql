-- Rate audit retention (services/industry-solutions/insurance/RETENTION.md).
-- A rate's audit rows are kept for p_retention_years (default 7) after the
-- later of the rate's effective_to and the last commission_ledger period
-- that used it, and never while the rate is open. The row itself must also
-- be at least that old. A deleted rate's clock starts at its deletion.
-- rate_audit_log has no rate_id, so its RATE_UPSERT / RATE_END rows are kept
-- while any rate in the same product/agent scope is still retained; its
-- SPLIT_SET and COMMISSION_CALC rows are policy records, outside this rule.
WHENEVER SQLERROR EXIT SQL.SQLCODE

-- clock_start is NULL while the rate is open: never eligible.
CREATE OR REPLACE VIEW v_rate_retention AS
SELECT r.rate_id,
       r.product_code,
       r.agent_id,
       r.effective_to,
       l.last_ledger_period_end,
       CASE WHEN r.effective_to IS NOT NULL
            THEN GREATEST(r.effective_to, NVL(l.last_ledger_period_end, r.effective_to)) END AS clock_start
  FROM commission_rates r
  LEFT JOIN (SELECT rate_id, MAX(LAST_DAY(TO_DATE(period_month, 'YYYY-MM'))) AS last_ledger_period_end
               FROM commission_ledger GROUP BY rate_id) l
    ON l.rate_id = r.rate_id;

CREATE OR REPLACE PACKAGE rate_retention_pkg AS
    c_policy CONSTANT VARCHAR2(64) := 'rate-audit-7y';

    -- Rows matched across audit_row_change and rate_audit_log. Dry run by
    -- default; every call writes two retention_run rows.
    FUNCTION purge (
        p_as_of           IN DATE    DEFAULT TRUNC(SYSDATE),
        p_retention_years IN NUMBER  DEFAULT 7,
        p_dry_run         IN BOOLEAN DEFAULT TRUE
    ) RETURN NUMBER;
END rate_retention_pkg;
/

CREATE OR REPLACE PACKAGE BODY rate_retention_pkg AS
    FUNCTION purge (
        p_as_of           IN DATE    DEFAULT TRUNC(SYSDATE),
        p_retention_years IN NUMBER  DEFAULT 7,
        p_dry_run         IN BOOLEAN DEFAULT TRUE
    ) RETURN NUMBER IS
        l_cutoff VARCHAR2(64);
        l_n      NUMBER := 0;
    BEGIN
        IF p_retention_years IS NULL OR p_retention_years < 7 OR p_retention_years <> TRUNC(p_retention_years) THEN
            RAISE_APPLICATION_ERROR(-20910, 'Rate audit retention is a whole number of years, at least 7');
        END IF;
        l_cutoff := 'ADD_MONTHS(:as_of, -' || TO_CHAR(12 * p_retention_years) || ')';

        l_n := l_n + retention_kit.purge(c_policy, 'AUDIT_ROW_CHANGE',
               'table_name = ''COMMISSION_RATES'' AND changed_at <= ' || l_cutoff
            || ' AND (EXISTS (SELECT 1 FROM v_rate_retention v WHERE v.rate_id = TO_NUMBER(audit_row_change.row_key)'
            || '              AND v.clock_start <= ' || l_cutoff || ')'
            || '  OR (NOT EXISTS (SELECT 1 FROM commission_rates r WHERE r.rate_id = TO_NUMBER(audit_row_change.row_key))'
            || '      AND EXISTS (SELECT 1 FROM audit_row_change d WHERE d.table_name = ''COMMISSION_RATES'''
            || '                  AND d.row_key = audit_row_change.row_key AND d.operation = ''DELETE'''
            || '                  AND d.changed_at <= ' || l_cutoff || ')))',
            p_as_of, p_dry_run);

        l_n := l_n + retention_kit.purge(c_policy, 'RATE_AUDIT_LOG',
               'action IN (''RATE_UPSERT'', ''RATE_END'') AND logged_at <= ' || l_cutoff
            || ' AND NOT EXISTS (SELECT 1 FROM v_rate_retention v WHERE v.product_code = rate_audit_log.product_code'
            || '     AND NVL(v.agent_id, -1) = NVL(rate_audit_log.agent_id, -1)'
            || '     AND (v.clock_start IS NULL OR v.clock_start > ' || l_cutoff || '))',
            p_as_of, p_dry_run);
        RETURN l_n;
    END purge;
END rate_retention_pkg;
/

EXIT;
