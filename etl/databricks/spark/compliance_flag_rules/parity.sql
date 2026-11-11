/* run=dbx-d1111 act=spark step=parity consumer=compliance_flag_rules */
-- run_token=dbx-d1111 expires=2026-11-24
-- Execute only after a genuine live-adapted original result exists. Never load fixture rows here.
WITH b AS (SELECT count(*) n, sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(FLAG_ID AS STRING), '<NULL>'), coalesce(cast(DOCUMENT_ID AS STRING), '<NULL>'), coalesce(cast(SEVERITY AS STRING), '<NULL>'), coalesce(cast(DISPOSITION AS STRING), '<NULL>'))),1,15),16,10) AS DECIMAL(38,0))) h FROM cpw.dbx_d1111_parity.audit__spark_compliance_flag_rules__spark_before),
a AS (SELECT count(*) n, sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(FLAG_ID AS STRING), '<NULL>'), coalesce(cast(DOCUMENT_ID AS STRING), '<NULL>'), coalesce(cast(SEVERITY AS STRING), '<NULL>'), coalesce(cast(DISPOSITION AS STRING), '<NULL>'))),1,15),16,10) AS DECIMAL(38,0))) h FROM cpw.dbx_d1111_after.audit__spark_compliance_flag_rules)
SELECT b.n before_count, a.n after_count, b.h before_hash, a.h after_hash,
       b.n = a.n AND b.h <=> a.h AS parity FROM b CROSS JOIN a;

/* run=dbx-d1111 act=spark step=parity consumer=compliance_flag_rules */
SELECT FLAG_ID, DOCUMENT_ID, SEVERITY, DISPOSITION FROM cpw.dbx_d1111_parity.audit__spark_compliance_flag_rules__spark_before EXCEPT ALL SELECT FLAG_ID, DOCUMENT_ID, SEVERITY, DISPOSITION FROM cpw.dbx_d1111_after.audit__spark_compliance_flag_rules LIMIT 20;

/* run=dbx-d1111 act=spark step=parity consumer=compliance_flag_rules */
SELECT FLAG_ID, DOCUMENT_ID, SEVERITY, DISPOSITION FROM cpw.dbx_d1111_after.audit__spark_compliance_flag_rules EXCEPT ALL SELECT FLAG_ID, DOCUMENT_ID, SEVERITY, DISPOSITION FROM cpw.dbx_d1111_parity.audit__spark_compliance_flag_rules__spark_before LIMIT 20;

/* run=dbx-d1111 act=spark step=idempotence consumer=compliance_flag_rules */
-- Record after each of two successful runs; compare count/hash plus operationMetrics.
SELECT count(*) n, sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(FLAG_ID AS STRING), '<NULL>'), coalesce(cast(DOCUMENT_ID AS STRING), '<NULL>'), coalesce(cast(SEVERITY AS STRING), '<NULL>'), coalesce(cast(DISPOSITION AS STRING), '<NULL>'))),1,15),16,10) AS DECIMAL(38,0))) h FROM cpw.dbx_d1111_after.audit__spark_compliance_flag_rules;

/* run=dbx-d1111 act=spark step=idempotence consumer=compliance_flag_rules */
DESCRIBE HISTORY cpw.dbx_d1111_after.audit__spark_compliance_flag_rules LIMIT 2;
