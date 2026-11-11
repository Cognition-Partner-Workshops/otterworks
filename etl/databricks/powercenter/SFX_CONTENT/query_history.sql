/* run=dbx-d1111 act=scale step=history consumer=SFX_CONTENT */
SELECT statement_id,execution_status,start_time,end_time,query_source
FROM system.query.history
WHERE statement_text LIKE '/* run=dbx-d1111 act=scale%'
  AND (statement_text LIKE '%consumer=SFX_CONTENT%'
       OR statement_text RLIKE 'consumer=m_SFX_(STG_APP_USER|APP_USER|STG_DOCUMENT|DOCUMENT|DOC_SHARE) ')
  AND start_time >= current_timestamp()-INTERVAL 8 HOURS;
