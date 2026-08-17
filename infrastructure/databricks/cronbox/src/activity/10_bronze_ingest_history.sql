DELETE FROM ow_tp.bronze.cronbox_activity_history_summary
WHERE namespace = :ns AND report_date = :ds;
DELETE FROM ow_tp.bronze.cronbox_activity_history_top_users
WHERE namespace = :ns AND report_date = :ds;

COPY INTO ow_tp.bronze.cronbox_activity_history_summary
FROM '/Volumes/ow_tp/bronze/landing/cronbox/user-activity/' || :ns || '/' || :ds || '/history-summary-0000.jsonl'
FILEFORMAT = JSON
FORMAT_OPTIONS ('inferSchema' = 'true');

COPY INTO ow_tp.bronze.cronbox_activity_history_top_users
FROM '/Volumes/ow_tp/bronze/landing/cronbox/user-activity/' || :ns || '/' || :ds || '/history-top-users-0000.jsonl'
FILEFORMAT = JSON
FORMAT_OPTIONS ('inferSchema' = 'true');
