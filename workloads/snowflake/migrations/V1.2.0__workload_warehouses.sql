-- One warehouse per workload (README rule 6). Resource monitors need ACCOUNTADMIN and are
-- created and attached by migrations_accountadmin/V1.0.0__resource_monitors.sql.
CREATE WAREHOUSE IF NOT EXISTS {{ wh_doc_usage_dashboard }} WITH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Run SFNFR_20261104: doc_usage_dashboard only';

CREATE WAREHOUSE IF NOT EXISTS {{ wh_doc_search_api }} WITH
  WAREHOUSE_SIZE = 'LARGE'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Run SFNFR_20261104: doc_search_api only';

CREATE WAREHOUSE IF NOT EXISTS {{ wh_churn_model }} WITH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Run SFNFR_20261104: churn_model only';

ALTER WAREHOUSE {{ wh_doc_usage_dashboard }} SET TAG {{ tag_fqn }} = 'cs_doc_usage_dashboard_account_usage';
ALTER WAREHOUSE {{ wh_doc_search_api }} SET TAG {{ tag_fqn }} = 'cs_doc_search_api_top_items';
ALTER WAREHOUSE {{ wh_churn_model }} SET TAG {{ tag_fqn }} = 'cs_churn_model_account_score';
