-- Search was declared LARGE but needs XSMALL; query acceleration is essentially unused.
-- Keep the 60-second org standard: Snowflake bills at least 60 seconds per resume.
ALTER WAREHOUSE IF EXISTS {{ wh_doc_usage_dashboard }} SET
  WAREHOUSE_SIZE = 'XSMALL' AUTO_SUSPEND = 60 AUTO_RESUME = TRUE ENABLE_QUERY_ACCELERATION = FALSE;

ALTER WAREHOUSE IF EXISTS {{ wh_doc_search_api }} SET
  WAREHOUSE_SIZE = 'XSMALL' AUTO_SUSPEND = 60 AUTO_RESUME = TRUE ENABLE_QUERY_ACCELERATION = FALSE;

ALTER WAREHOUSE IF EXISTS {{ wh_churn_model }} SET
  WAREHOUSE_SIZE = 'XSMALL' AUTO_SUSPEND = 60 AUTO_RESUME = TRUE ENABLE_QUERY_ACCELERATION = FALSE;
