-- Needs MANAGE GRANTS (ACCOUNTADMIN or SECURITYADMIN): the builder owns these schemas but cannot
-- define future grants on them. Tables the workloads create later become readable without a new grant.
GRANT SELECT ON FUTURE TABLES IN SCHEMA {{ db_doc_usage_dashboard }}.RAW TO ROLE {{ analyst_role }};
GRANT SELECT ON FUTURE TABLES IN SCHEMA {{ db_doc_usage_dashboard }}.ANALYTICS TO ROLE {{ analyst_role }};
GRANT SELECT ON FUTURE TABLES IN SCHEMA {{ db_doc_search_api }}.RAW TO ROLE {{ analyst_role }};
GRANT SELECT ON FUTURE TABLES IN SCHEMA {{ db_doc_search_api }}.ANALYTICS TO ROLE {{ analyst_role }};
GRANT SELECT ON FUTURE TABLES IN SCHEMA {{ db_churn_model }}.RAW TO ROLE {{ analyst_role }};
GRANT SELECT ON FUTURE TABLES IN SCHEMA {{ db_churn_model }}.ANALYTICS TO ROLE {{ analyst_role }};
GRANT SELECT ON FUTURE TABLES IN SCHEMA {{ db_doc_usage_dashboard }}.ANALYTICS TO ROLE {{ reader_role }};
GRANT SELECT ON FUTURE TABLES IN SCHEMA {{ db_doc_search_api }}.ANALYTICS TO ROLE {{ reader_role }};
GRANT SELECT ON FUTURE TABLES IN SCHEMA {{ db_churn_model }}.ANALYTICS TO ROLE {{ reader_role }};
GRANT SELECT ON FUTURE VIEWS IN SCHEMA {{ db_doc_usage_dashboard }}.ANALYTICS TO ROLE {{ reader_role }};
GRANT SELECT ON FUTURE VIEWS IN SCHEMA {{ db_doc_search_api }}.ANALYTICS TO ROLE {{ reader_role }};
GRANT SELECT ON FUTURE VIEWS IN SCHEMA {{ db_churn_model }}.ANALYTICS TO ROLE {{ reader_role }};
