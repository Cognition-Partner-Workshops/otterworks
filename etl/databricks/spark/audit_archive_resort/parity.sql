/* run=dbx-d1111 act=spark step=parity consumer=audit_archive_resort */
-- run_token=dbx-d1111 expires=2026-11-24
-- Execute only after a genuine live-adapted original result exists. Never load fixture rows here.
WITH b AS (SELECT count(*) n, sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(AUDIT_EVENT_ARCHIVE_ID AS STRING), '<NULL>'), coalesce(cast(ACTOR_USER_ID AS STRING), '<NULL>'), coalesce(cast(DOCUMENT_ID AS STRING), '<NULL>'), coalesce(cast(EVENT_TYPE AS STRING), '<NULL>'), coalesce(cast(EVENT_AT AS STRING), '<NULL>'), coalesce(cast(DETAILS AS STRING), '<NULL>'))),1,15),16,10) AS DECIMAL(38,0))) h FROM cpw.dbx_d1111_parity.audit__spark_audit_archive_resort__spark_before),
a AS (SELECT count(*) n, sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(AUDIT_EVENT_ARCHIVE_ID AS STRING), '<NULL>'), coalesce(cast(ACTOR_USER_ID AS STRING), '<NULL>'), coalesce(cast(DOCUMENT_ID AS STRING), '<NULL>'), coalesce(cast(EVENT_TYPE AS STRING), '<NULL>'), coalesce(cast(EVENT_AT AS STRING), '<NULL>'), coalesce(cast(DETAILS AS STRING), '<NULL>'))),1,15),16,10) AS DECIMAL(38,0))) h FROM cpw.dbx_d1111_after.audit__spark_audit_archive_resort)
SELECT b.n before_count, a.n after_count, b.h before_hash, a.h after_hash,
       b.n = a.n AND b.h <=> a.h AS parity FROM b CROSS JOIN a;

/* run=dbx-d1111 act=spark step=parity consumer=audit_archive_resort */
SELECT AUDIT_EVENT_ARCHIVE_ID, ACTOR_USER_ID, DOCUMENT_ID, EVENT_TYPE, EVENT_AT, DETAILS FROM cpw.dbx_d1111_parity.audit__spark_audit_archive_resort__spark_before EXCEPT ALL SELECT AUDIT_EVENT_ARCHIVE_ID, ACTOR_USER_ID, DOCUMENT_ID, EVENT_TYPE, EVENT_AT, DETAILS FROM cpw.dbx_d1111_after.audit__spark_audit_archive_resort LIMIT 20;

/* run=dbx-d1111 act=spark step=parity consumer=audit_archive_resort */
SELECT AUDIT_EVENT_ARCHIVE_ID, ACTOR_USER_ID, DOCUMENT_ID, EVENT_TYPE, EVENT_AT, DETAILS FROM cpw.dbx_d1111_after.audit__spark_audit_archive_resort EXCEPT ALL SELECT AUDIT_EVENT_ARCHIVE_ID, ACTOR_USER_ID, DOCUMENT_ID, EVENT_TYPE, EVENT_AT, DETAILS FROM cpw.dbx_d1111_parity.audit__spark_audit_archive_resort__spark_before LIMIT 20;

/* run=dbx-d1111 act=spark step=idempotence consumer=audit_archive_resort */
-- Record after each of two successful runs; compare count/hash plus operationMetrics.
SELECT count(*) n, sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(AUDIT_EVENT_ARCHIVE_ID AS STRING), '<NULL>'), coalesce(cast(ACTOR_USER_ID AS STRING), '<NULL>'), coalesce(cast(DOCUMENT_ID AS STRING), '<NULL>'), coalesce(cast(EVENT_TYPE AS STRING), '<NULL>'), coalesce(cast(EVENT_AT AS STRING), '<NULL>'), coalesce(cast(DETAILS AS STRING), '<NULL>'))),1,15),16,10) AS DECIMAL(38,0))) h FROM cpw.dbx_d1111_after.audit__spark_audit_archive_resort;

/* run=dbx-d1111 act=spark step=idempotence consumer=audit_archive_resort */
DESCRIBE HISTORY cpw.dbx_d1111_after.audit__spark_audit_archive_resort LIMIT 2;
