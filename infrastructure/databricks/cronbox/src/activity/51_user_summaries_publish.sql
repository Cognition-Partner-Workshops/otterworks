INSERT INTO ow_tp.gold.user_activity_user_summaries
WITH rows AS (
  SELECT namespace, report_date, COALESCE(user_id, 'unknown') user_id, total_actions,
         action_counts, first_seq, report_date first_seen_date
  FROM ow_tp.gold.analytics_daily_top_users
  WHERE namespace = :ns AND report_date BETWEEN DATE_SUB(DATE':ds', 29) AND DATE':ds'
), grouped AS (
  SELECT namespace, report_date, user_id, SUM(total_actions) total_actions, COUNT(*) active_days,
         MAP_FROM_ENTRIES(COLLECT_LIST(STRUCT(k, v))) actions_by_type,
         MAX(first_seen_date) first_seen_date,
         MIN(first_seq) first_seen_seq
  FROM rows LATERAL VIEW EXPLODE(action_counts) e AS k, v
  GROUP BY namespace, report_date, user_id
), ranked AS (
  SELECT *, CAST(ROW_NUMBER() OVER (ORDER BY total_actions DESC, first_seen_date DESC,
    COALESCE(first_seen_seq, 9223372036854775807) ASC) AS INT) user_ordinal
  FROM grouped
)
SELECT report_date, namespace, user_id, total_actions, active_days, actions_by_type,
       user_ordinal, user_ordinal <= 20, first_seen_date, first_seen_seq, current_timestamp()
FROM ranked WHERE user_ordinal <= 500;
