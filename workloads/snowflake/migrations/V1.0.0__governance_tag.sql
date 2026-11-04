-- DEVIN_CSID object tag (workloads/attribution/README.md rule 8), created once per account.
CREATE SCHEMA IF NOT EXISTS {{ governance_db }}.TAGS
  COMMENT = 'Object tags used for consumption attribution';

CREATE SCHEMA IF NOT EXISTS {{ governance_db }}.POLICIES
  COMMENT = 'Masking and row access policies shared by the workload databases';

CREATE TAG IF NOT EXISTS {{ tag_fqn }}
  ALLOWED_VALUES 'cs_doc_usage_dashboard_account_usage', 'cs_doc_search_api_top_items', 'cs_churn_model_account_score'
  COMMENT = 'Client-side ID(s) of the workload that owns the object, sorted and comma-joined';
