{% macro grant_reports_schema_to_reader() -%}
  {#- The run's ENGINEER role creates REPORTS through dbt and owns it, so it can open the schema to
      the run's READER role (account.sql grants READER the four bootstrap schemas only). -#}
  {%- if execute and graph.nodes.values() | selectattr('config.schema', 'equalto', 'REPORTS') | list -%}
    grant usage on schema {{ target.database }}.REPORTS to role {{ target.database }}_READER
  {%- else -%}
    select 1
  {%- endif -%}
{%- endmacro %}
