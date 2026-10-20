-- Rate change audit trail on COMMISSION_RATES (shared/compliance-kit/oracle).
-- The trigger records every change, whether it comes through COMMISSION_PKG
-- or a direct statement; RATE_AUDIT_LOG stays the package's business log.
WHENEVER SQLERROR EXIT SQL.SQLCODE

BEGIN
    audit_kit.install_row_audit('COMMISSION_RATES', 'RATE_ID');
    audit_kit.protect_append_only('AUDIT_ROW_CHANGE');
    audit_kit.protect_append_only('RATE_AUDIT_LOG');
    audit_kit.protect_append_only('RETENTION_RUN');
END;
/

-- Who changed rate X and when: one row per change, oldest first.
-- actor is the application actor COMMISSION_PKG declared (p_actor) when the
-- package issued the change, otherwise the authenticated database session.
CREATE OR REPLACE VIEW v_rate_change_history AS
SELECT c.change_id,
       TO_NUMBER(c.row_key) AS rate_id,
       c.operation,
       c.changed_at,
       COALESCE(c.app_actor,
                c.db_user || ' (' || NVL(c.os_user, '?') || '@' || NVL(c.client_host, '?') || ')') AS actor,
       CASE WHEN c.app_actor IS NOT NULL THEN 'PACKAGE' ELSE 'SESSION' END AS actor_source,
       c.db_user,
       c.os_user,
       c.client_host,
       c.client_program,
       c.via_program,
       COALESCE(JSON_VALUE(c.new_values, '$.PRODUCT_CODE'), JSON_VALUE(c.old_values, '$.PRODUCT_CODE')) AS product_code,
       TO_NUMBER(COALESCE(JSON_VALUE(c.new_values, '$.AGENT_ID'), JSON_VALUE(c.old_values, '$.AGENT_ID'))) AS agent_id,
       TO_NUMBER(JSON_VALUE(c.old_values, '$.RATE_PCT')) AS old_rate_pct,
       TO_NUMBER(JSON_VALUE(c.new_values, '$.RATE_PCT')) AS new_rate_pct,
       TO_DATE(SUBSTR(JSON_VALUE(c.old_values, '$.EFFECTIVE_FROM'), 1, 10), 'YYYY-MM-DD') AS old_effective_from,
       TO_DATE(SUBSTR(JSON_VALUE(c.new_values, '$.EFFECTIVE_FROM'), 1, 10), 'YYYY-MM-DD') AS new_effective_from,
       TO_DATE(SUBSTR(JSON_VALUE(c.old_values, '$.EFFECTIVE_TO'), 1, 10), 'YYYY-MM-DD') AS old_effective_to,
       TO_DATE(SUBSTR(JSON_VALUE(c.new_values, '$.EFFECTIVE_TO'), 1, 10), 'YYYY-MM-DD') AS new_effective_to,
       COALESCE(JSON_VALUE(c.new_values, '$.CREATED_BY'), JSON_VALUE(c.old_values, '$.CREATED_BY')) AS created_by,
       c.txn_id
  FROM audit_row_change c
 WHERE c.table_name = 'COMMISSION_RATES';

EXIT;
