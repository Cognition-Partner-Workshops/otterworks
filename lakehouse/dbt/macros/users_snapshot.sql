{% macro users_snapshot(table) -%}
{{ source('bronze_users', table) }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
{%- endmacro %}
