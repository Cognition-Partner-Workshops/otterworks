CREATE ROLE IF NOT EXISTS {{ ops_role_doc_usage_dashboard }}
 COMMENT = 'doc_usage_dashboard runtime ops: freshness, task history, drill switch';

GRANT USAGE ON DATABASE {{ db_doc_usage_dashboard }} TO ROLE {{ ops_role_doc_usage_dashboard }};
GRANT USAGE ON SCHEMA {{ ops_schema_doc_usage_dashboard }} TO ROLE {{ ops_role_doc_usage_dashboard }};
GRANT USAGE ON SCHEMA {{ db_doc_usage_dashboard }}.ANALYTICS TO ROLE {{ ops_role_doc_usage_dashboard }};
GRANT USAGE, MONITOR ON WAREHOUSE {{ wh_doc_usage_dashboard }} TO ROLE {{ ops_role_doc_usage_dashboard }};

GRANT SELECT ON VIEW {{ ops_schema_doc_usage_dashboard }}.WORKLOAD_FRESHNESS TO ROLE {{ ops_role_doc_usage_dashboard }};
GRANT SELECT ON TABLE {{ ops_schema_doc_usage_dashboard }}.REFRESH_LOG TO ROLE {{ ops_role_doc_usage_dashboard }};
GRANT SELECT ON TABLE {{ ops_schema_doc_usage_dashboard }}.REFRESH_TABLES TO ROLE {{ ops_role_doc_usage_dashboard }};
GRANT SELECT ON TABLE {{ ops_schema_doc_usage_dashboard }}.FAULT_SWITCH TO ROLE {{ ops_role_doc_usage_dashboard }};
GRANT UPDATE ON TABLE {{ ops_schema_doc_usage_dashboard }}.FAULT_SWITCH TO ROLE {{ ops_role_doc_usage_dashboard }};

GRANT OPERATE, MONITOR ON TASK {{ task_doc_usage_dashboard }} TO ROLE {{ ops_role_doc_usage_dashboard }};
GRANT ROLE {{ ops_role_doc_usage_dashboard }} TO USER {{ svc_user_doc_usage_dashboard }};
GRANT ROLE {{ ops_role_doc_usage_dashboard }} TO ROLE {{ builder_role }};
