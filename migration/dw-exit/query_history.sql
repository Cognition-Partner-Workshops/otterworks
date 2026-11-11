SELECT query_id, start_time, warehouse_name,
       TRY_PARSE_JSON(query_tag):step::STRING AS step,
       execution_status, rows_produced, query_text
FROM TABLE(SFX_D1110_AFTER.INFORMATION_SCHEMA.QUERY_HISTORY(
    END_TIME_RANGE_START => DATEADD('hour', -24, CURRENT_TIMESTAMP()),
    RESULT_LIMIT => 10000))
WHERE TRY_PARSE_JSON(query_tag):run::STRING = 'sfx-d1110'
  AND TRY_PARSE_JSON(query_tag):act::STRING = 'prove'
ORDER BY start_time, query_id;
