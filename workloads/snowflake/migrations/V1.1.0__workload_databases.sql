-- One database per workload, each with RAW (landed inputs) and ANALYTICS (outputs).
CREATE DATABASE IF NOT EXISTS {{ db_doc_usage_dashboard }}
  COMMENT = 'Run SFNFR_20261104: workload doc_usage_dashboard';
CREATE SCHEMA IF NOT EXISTS {{ db_doc_usage_dashboard }}.RAW
  COMMENT = 'Postgres tables landed for doc_usage_dashboard, RAW.<SERVICE>_<TABLE>';
CREATE SCHEMA IF NOT EXISTS {{ db_doc_usage_dashboard }}.ANALYTICS
  COMMENT = 'doc_usage_dashboard output, task and Streamlit app';

CREATE DATABASE IF NOT EXISTS {{ db_doc_search_api }}
  COMMENT = 'Run SFNFR_20261104: workload doc_search_api';
CREATE SCHEMA IF NOT EXISTS {{ db_doc_search_api }}.RAW
  COMMENT = 'Postgres tables landed for doc_search_api, RAW.<SERVICE>_<TABLE>';
CREATE SCHEMA IF NOT EXISTS {{ db_doc_search_api }}.ANALYTICS
  COMMENT = 'doc_search_api output and task';

CREATE DATABASE IF NOT EXISTS {{ db_churn_model }}
  COMMENT = 'Run SFNFR_20261104: workload churn_model';
CREATE SCHEMA IF NOT EXISTS {{ db_churn_model }}.RAW
  COMMENT = 'Postgres tables landed for churn_model, RAW.<SERVICE>_<TABLE>';
CREATE SCHEMA IF NOT EXISTS {{ db_churn_model }}.ANALYTICS
  COMMENT = 'churn_model output and task';

ALTER DATABASE {{ db_doc_usage_dashboard }} SET TAG {{ tag_fqn }} = 'cs_doc_usage_dashboard_account_usage';
ALTER DATABASE {{ db_doc_search_api }} SET TAG {{ tag_fqn }} = 'cs_doc_search_api_top_items';
ALTER DATABASE {{ db_churn_model }} SET TAG {{ tag_fqn }} = 'cs_churn_model_account_score';
