/* run=dbx-d1111 act=spark step=parity consumer=audit_actor_activity_join */
-- run_token=dbx-d1111 expires=2026-11-24
-- Execute only after a genuine live-adapted original result exists. Never load fixture rows here.
WITH b AS (SELECT count(*) n, sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(USER_KEY AS STRING), '<NULL>'), coalesce(cast(AUDIT_EVENT_ID AS STRING), '<NULL>'), coalesce(cast(EVENT_AT AS STRING), '<NULL>'), coalesce(cast(ACTIVITY_DATE AS STRING), '<NULL>'), coalesce(cast(ACTION_COUNT AS STRING), '<NULL>'), coalesce(cast(USER_AGENT AS STRING), '<NULL>'), coalesce(cast(LOGIN_TEXT_BYTES AS STRING), '<NULL>'))),1,15),16,10) AS DECIMAL(38,0))) h FROM cpw.dbx_d1111_parity.audit__spark_audit_actor_activity_join__spark_before),
a AS (SELECT count(*) n, sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(USER_KEY AS STRING), '<NULL>'), coalesce(cast(AUDIT_EVENT_ID AS STRING), '<NULL>'), coalesce(cast(EVENT_AT AS STRING), '<NULL>'), coalesce(cast(ACTIVITY_DATE AS STRING), '<NULL>'), coalesce(cast(ACTION_COUNT AS STRING), '<NULL>'), coalesce(cast(USER_AGENT AS STRING), '<NULL>'), coalesce(cast(LOGIN_TEXT_BYTES AS STRING), '<NULL>'))),1,15),16,10) AS DECIMAL(38,0))) h FROM cpw.dbx_d1111_after.audit__spark_audit_actor_activity_join)
SELECT b.n before_count, a.n after_count, b.h before_hash, a.h after_hash,
       b.n = a.n AND b.h <=> a.h AS parity FROM b CROSS JOIN a;

/* run=dbx-d1111 act=spark step=parity consumer=audit_actor_activity_join */
SELECT USER_KEY, AUDIT_EVENT_ID, EVENT_AT, ACTIVITY_DATE, ACTION_COUNT, USER_AGENT, LOGIN_TEXT_BYTES FROM cpw.dbx_d1111_parity.audit__spark_audit_actor_activity_join__spark_before EXCEPT ALL SELECT USER_KEY, AUDIT_EVENT_ID, EVENT_AT, ACTIVITY_DATE, ACTION_COUNT, USER_AGENT, LOGIN_TEXT_BYTES FROM cpw.dbx_d1111_after.audit__spark_audit_actor_activity_join LIMIT 20;

/* run=dbx-d1111 act=spark step=parity consumer=audit_actor_activity_join */
SELECT USER_KEY, AUDIT_EVENT_ID, EVENT_AT, ACTIVITY_DATE, ACTION_COUNT, USER_AGENT, LOGIN_TEXT_BYTES FROM cpw.dbx_d1111_after.audit__spark_audit_actor_activity_join EXCEPT ALL SELECT USER_KEY, AUDIT_EVENT_ID, EVENT_AT, ACTIVITY_DATE, ACTION_COUNT, USER_AGENT, LOGIN_TEXT_BYTES FROM cpw.dbx_d1111_parity.audit__spark_audit_actor_activity_join__spark_before LIMIT 20;

/* run=dbx-d1111 act=spark step=idempotence consumer=audit_actor_activity_join */
-- Record after each of two successful runs; compare count/hash plus operationMetrics.
SELECT count(*) n, sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(USER_KEY AS STRING), '<NULL>'), coalesce(cast(AUDIT_EVENT_ID AS STRING), '<NULL>'), coalesce(cast(EVENT_AT AS STRING), '<NULL>'), coalesce(cast(ACTIVITY_DATE AS STRING), '<NULL>'), coalesce(cast(ACTION_COUNT AS STRING), '<NULL>'), coalesce(cast(USER_AGENT AS STRING), '<NULL>'), coalesce(cast(LOGIN_TEXT_BYTES AS STRING), '<NULL>'))),1,15),16,10) AS DECIMAL(38,0))) h FROM cpw.dbx_d1111_after.audit__spark_audit_actor_activity_join;

/* run=dbx-d1111 act=spark step=idempotence consumer=audit_actor_activity_join */
DESCRIBE HISTORY cpw.dbx_d1111_after.audit__spark_audit_actor_activity_join LIMIT 2;
