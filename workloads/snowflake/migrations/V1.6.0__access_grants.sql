-- ANALYST: landed inputs and outputs of every workload.
GRANT USAGE ON DATABASE {{ db_doc_usage_dashboard }} TO ROLE {{ analyst_role }};
GRANT USAGE ON DATABASE {{ db_doc_search_api }} TO ROLE {{ analyst_role }};
GRANT USAGE ON DATABASE {{ db_churn_model }} TO ROLE {{ analyst_role }};
GRANT USAGE ON ALL SCHEMAS IN DATABASE {{ db_doc_usage_dashboard }} TO ROLE {{ analyst_role }};
GRANT USAGE ON ALL SCHEMAS IN DATABASE {{ db_doc_search_api }} TO ROLE {{ analyst_role }};
GRANT USAGE ON ALL SCHEMAS IN DATABASE {{ db_churn_model }} TO ROLE {{ analyst_role }};
GRANT SELECT ON ALL TABLES IN DATABASE {{ db_doc_usage_dashboard }} TO ROLE {{ analyst_role }};
GRANT SELECT ON ALL TABLES IN DATABASE {{ db_doc_search_api }} TO ROLE {{ analyst_role }};
GRANT SELECT ON ALL TABLES IN DATABASE {{ db_churn_model }} TO ROLE {{ analyst_role }};

-- READER: workload outputs.
GRANT USAGE ON DATABASE {{ db_doc_usage_dashboard }} TO ROLE {{ reader_role }};
GRANT USAGE ON DATABASE {{ db_doc_search_api }} TO ROLE {{ reader_role }};
GRANT USAGE ON DATABASE {{ db_churn_model }} TO ROLE {{ reader_role }};
GRANT USAGE ON SCHEMA {{ db_doc_usage_dashboard }}.ANALYTICS TO ROLE {{ reader_role }};
GRANT USAGE ON SCHEMA {{ db_doc_search_api }}.ANALYTICS TO ROLE {{ reader_role }};
GRANT USAGE ON SCHEMA {{ db_churn_model }}.ANALYTICS TO ROLE {{ reader_role }};
-- Future grants need MANAGE GRANTS, which the builder lacks: see migrations_accountadmin/V1.1.0__future_grants.sql.
GRANT USAGE ON SCHEMA {{ db_churn_model }}.RAW TO ROLE {{ reader_role }};
GRANT SELECT ON TABLE {{ db_churn_model }}.RAW.AUTH_USERS TO ROLE {{ reader_role }};

-- Each role queries a workload on that workload's own warehouse.
GRANT USAGE ON WAREHOUSE {{ wh_doc_usage_dashboard }} TO ROLE {{ analyst_role }};
GRANT USAGE ON WAREHOUSE {{ wh_doc_search_api }} TO ROLE {{ analyst_role }};
GRANT USAGE ON WAREHOUSE {{ wh_churn_model }} TO ROLE {{ analyst_role }};
GRANT USAGE ON WAREHOUSE {{ wh_doc_usage_dashboard }} TO ROLE {{ reader_role }};
GRANT USAGE ON WAREHOUSE {{ wh_doc_search_api }} TO ROLE {{ reader_role }};
GRANT USAGE ON WAREHOUSE {{ wh_churn_model }} TO ROLE {{ reader_role }};
