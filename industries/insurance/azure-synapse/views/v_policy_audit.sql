CREATE VIEW dw.v_policy_audit AS
SELECT e.policy_number,
       DATEPART(weekday, e.event_at) AS event_weekday,
       COUNT(*)                      AS event_count,
       MAX(e.event_at)               AS last_event_at
  FROM audit.policy_event e
 GROUP BY e.policy_number, DATEPART(weekday, e.event_at);
GO
