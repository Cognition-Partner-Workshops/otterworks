CREATE VIEW dw.v_claim_audit AS
SELECT e.claim_id,
       e.event_type,
       DATEPART(weekday, e.event_at) AS event_weekday,
       CAST(e.event_at AS DATE)      AS event_date,
       COUNT(*)                      AS event_count
  FROM audit.claim_event e
 GROUP BY e.claim_id, e.event_type, DATEPART(weekday, e.event_at), CAST(e.event_at AS DATE);
GO
