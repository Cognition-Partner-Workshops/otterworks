/* run=dbx-d1111 act=spark step=parity consumer=lake_compaction_audit */
-- run_token=dbx-d1111 expires=2026-11-24
-- Execute only after a genuine live-adapted original result exists. Never load fixture rows here.
WITH b AS (SELECT count(*) n, sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(EVENT_DATE AS STRING), '<NULL>'), coalesce(cast(EVENT_TYPE AS STRING), '<NULL>'), coalesce(cast(EVENT_COUNT AS STRING), '<NULL>'), coalesce(cast(ACTORS AS STRING), '<NULL>'))),1,15),16,10) AS DECIMAL(38,0))) h FROM cpw.dbx_d1111_parity.audit__spark_lake_compaction_audit__spark_before),
a AS (SELECT count(*) n, sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(EVENT_DATE AS STRING), '<NULL>'), coalesce(cast(EVENT_TYPE AS STRING), '<NULL>'), coalesce(cast(EVENT_COUNT AS STRING), '<NULL>'), coalesce(cast(ACTORS AS STRING), '<NULL>'))),1,15),16,10) AS DECIMAL(38,0))) h FROM cpw.dbx_d1111_after.audit__spark_lake_compaction_audit)
SELECT b.n before_count, a.n after_count, b.h before_hash, a.h after_hash,
       b.n = a.n AND b.h <=> a.h AS parity FROM b CROSS JOIN a;

/* run=dbx-d1111 act=spark step=parity consumer=lake_compaction_audit */
SELECT EVENT_DATE, EVENT_TYPE, EVENT_COUNT, ACTORS FROM cpw.dbx_d1111_parity.audit__spark_lake_compaction_audit__spark_before EXCEPT ALL SELECT EVENT_DATE, EVENT_TYPE, EVENT_COUNT, ACTORS FROM cpw.dbx_d1111_after.audit__spark_lake_compaction_audit LIMIT 20;

/* run=dbx-d1111 act=spark step=parity consumer=lake_compaction_audit */
SELECT EVENT_DATE, EVENT_TYPE, EVENT_COUNT, ACTORS FROM cpw.dbx_d1111_after.audit__spark_lake_compaction_audit EXCEPT ALL SELECT EVENT_DATE, EVENT_TYPE, EVENT_COUNT, ACTORS FROM cpw.dbx_d1111_parity.audit__spark_lake_compaction_audit__spark_before LIMIT 20;

/* run=dbx-d1111 act=spark step=idempotence consumer=lake_compaction_audit */
-- Record after each of two successful runs; compare count/hash plus operationMetrics.
SELECT count(*) n, sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(EVENT_DATE AS STRING), '<NULL>'), coalesce(cast(EVENT_TYPE AS STRING), '<NULL>'), coalesce(cast(EVENT_COUNT AS STRING), '<NULL>'), coalesce(cast(ACTORS AS STRING), '<NULL>'))),1,15),16,10) AS DECIMAL(38,0))) h FROM cpw.dbx_d1111_after.audit__spark_lake_compaction_audit;

/* run=dbx-d1111 act=spark step=idempotence consumer=lake_compaction_audit */
DESCRIBE HISTORY cpw.dbx_d1111_after.audit__spark_lake_compaction_audit LIMIT 2;
