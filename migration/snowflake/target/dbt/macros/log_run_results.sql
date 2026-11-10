{#- Replaces dbo.usp_log_run: one OPS.ETL_RUN_LOG row per model, with the rows it holds for the date. -#}
{% macro log_run_results(results) %}
  {%- if execute -%}
    {%- for result in results if result.node.resource_type == 'model' and result.node.config.materialized == 'table' -%}
      {%- set succeeded = result.status == 'success' -%}
      insert into {{ target.database }}.OPS.ETL_RUN_LOG
          (RUN_TOKEN, BUSINESS_DATE, JOB_NAME, STEP_NAME, STATUS, ROW_COUNT, MESSAGE, STARTED_AT, COMPLETED_AT)
      select
          '{{ env_var("UBW_RUN", "") }}', {{ business_date() }}, 'dbt', '{{ result.node.name }}',
          '{{ "SUCCESS" if succeeded else "FAILED" }}',
          {% if succeeded %}(select count(*) from {{ result.node.relation_name }}){% else %}null{% endif %},
          '', current_timestamp()::timestamp_ntz, current_timestamp()::timestamp_ntz;
    {% endfor -%}
  {%- endif -%}
{% endmacro %}
