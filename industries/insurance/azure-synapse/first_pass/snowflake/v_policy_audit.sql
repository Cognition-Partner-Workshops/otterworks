-- First-pass conversion output: dw.v_policy_audit
CREATE OR REPLACE VIEW DW.V_POLICY_AUDIT AS
SELECT e.policy_number, DAYOFWEEK(e.event_at) AS event_weekday, COUNT(*) AS event_count,
       MAX(e.event_at) AS last_event_at
  FROM AUDIT.POLICY_EVENT e
 GROUP BY e.policy_number, DAYOFWEEK(e.event_at);
