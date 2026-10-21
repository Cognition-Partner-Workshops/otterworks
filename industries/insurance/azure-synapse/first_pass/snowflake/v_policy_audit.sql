CREATE OR REPLACE VIEW DW.V_POLICY_AUDIT AS
SELECT e.policy_number,
       MOD(DAYOFWEEKISO(e.event_at), 7) + 1 AS event_weekday,
       COUNT(*)                             AS event_count,
       MAX(e.event_at)                      AS last_event_at
  FROM AUDIT.POLICY_EVENT e
 GROUP BY e.policy_number, MOD(DAYOFWEEKISO(e.event_at), 7) + 1;
