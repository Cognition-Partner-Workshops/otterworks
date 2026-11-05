{{ config(tags=['doc_usage_dashboard']) }}
{% for workload in ['doc_usage_dashboard','doc_search_api','churn_model'] %}
select '{{ workload }}' as workload
where not exists (
  select 1 from {{ database_for(workload) }}.APP.PIPELINE_REFRESH_RUNS
  where execution_role='{{ var("run_token") }}_ANALYST'
)
or exists (
  select 1 from {{ database_for(workload) }}.APP.PIPELINE_REFRESH_RUNS
  where execution_role<>'{{ var("run_token") }}_ANALYST'
)
{% if not loop.last %}union all{% endif %}
{% endfor %}
