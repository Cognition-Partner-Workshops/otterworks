/* run=dbx-d1111 act=scale step=${STEP} consumer=${CONSUMER} */
WITH l AS (SELECT ${CANONICAL} FROM ${LEFT_TABLE}),
r AS (SELECT ${CANONICAL} FROM ${RIGHT_TABLE})
SELECT 'left' side, count(*) n,
sum(CAST(conv(substr(md5(concat_ws('|', ${COLUMNS})),1,15),16,10) AS DECIMAL(38,0))) hash FROM l
UNION ALL
SELECT 'right',count(*),
sum(CAST(conv(substr(md5(concat_ws('|', ${COLUMNS})),1,15),16,10) AS DECIMAL(38,0))) FROM r;
