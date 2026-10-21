CREATE OR REPLACE VIEW DW.V_CLAIM_AUDIT AS
SELECT e.claim_id,
       e.event_type,
       DAYOFWEEKISO(e.event_at) % 7 + 1 AS event_weekday,
       CAST(e.event_at AS DATE)         AS event_date,
       COUNT(*)                         AS event_count
  FROM AUDIT.CLAIM_EVENT e
 GROUP BY e.claim_id, e.event_type, DAYOFWEEKISO(e.event_at) % 7 + 1, CAST(e.event_at AS DATE);
