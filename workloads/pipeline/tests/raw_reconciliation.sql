{{ config(tags=['doc_usage_dashboard']) }}
{% for workload in ['doc_usage_dashboard','doc_search_api','churn_model'] %}
{% for table,key in [('AUTH_USERS','id'),('ADMIN_ADMIN_USERS','id'),('ADMIN_STORAGE_QUOTAS','user_id'),('DOCUMENT_DOCUMENTS','id'),('DOCUMENT_DOCUMENT_VERSIONS','id'),('ANALYTICS_ANALYTICS_EVENTS','event_id'),('AUTH_USER_STATE_HISTORY','id'),('ADMIN_USER_STATE_HISTORY','id')] %}
select '{{ workload }}.{{ table }}' as source from {{ database_for(workload) }}.RAW.{{ table }}
where _snapshot_date is not null group by _snapshot_date,{{ key }}
having count(*)<>1 or {{ key }} is null
{% if not loop.last %}union all{% endif %}
{% endfor %}
{% if not loop.last %}union all{% endif %}
{% endfor %}
