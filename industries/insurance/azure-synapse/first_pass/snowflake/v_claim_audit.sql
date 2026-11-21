-- First-pass conversion output: dw.v_claim_audit
CREATE OR REPLACE VIEW DW.V_CLAIM_AUDIT AS
-- FP-WARN 0612: DATEPART(weekday, ...) mapped to DAYOFWEEK
SELECT e.claim_id, e.event_type, DAYOFWEEK(e.event_at) AS event_weekday,
       CAST(e.event_at AS DATE) AS event_date, COUNT(*) AS event_count
  FROM AUDIT.CLAIM_EVENT e
 -- FP-WARN 0612: DATEPART(weekday, ...) mapped to DAYOFWEEK
 GROUP BY e.claim_id, e.event_type, DAYOFWEEK(e.event_at), CAST(e.event_at AS DATE);
