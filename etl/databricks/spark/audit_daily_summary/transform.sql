/* run=dbx-d1111 act=spark step=transform consumer=audit_daily_summary */
-- run_token=dbx-d1111 expires=2026-11-24
SELECT to_date(EVENT_AT) EVENT_DATE, EVENT_TYPE, COUNT(*) EVENT_COUNT,
       COUNT(DISTINCT ACTOR_USER_ID) ACTORS
FROM AUDIT_EVENT GROUP BY to_date(EVENT_AT), EVENT_TYPE;
