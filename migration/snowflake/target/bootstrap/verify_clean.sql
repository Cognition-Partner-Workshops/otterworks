-- Lists anything that still carries the run token, by name prefix and by tag.
-- A clean account returns no rows from any statement. ACCOUNT_USAGE.TAG_REFERENCES lags
-- by up to two hours, so the name checks are the ones to trust right after a teardown.
SHOW DATABASES LIKE '${PREFIX}%';
SHOW WAREHOUSES LIKE '${PREFIX}%';
SHOW RESOURCE MONITORS LIKE '${PREFIX}%';
SHOW ROLES LIKE '${PREFIX}%';
SHOW USERS LIKE '${PREFIX}%';
SELECT domain, object_database, object_schema, object_name, column_name, tag_name, tag_value
FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES
WHERE tag_database = 'OW_UBW' AND tag_schema = 'TAGS' AND tag_name = 'RUN'
  AND tag_value = '${RUN}' AND object_deleted IS NULL
ORDER BY domain, object_database, object_schema, object_name;
