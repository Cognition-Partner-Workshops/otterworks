{% macro business_date() -%}
  {%- if var("business_date", none) -%}
    '{{ var("business_date") }}'::date
  {%- else -%}
    dateadd(day, -1, current_date())
  {%- endif -%}
{%- endmacro %}

{% macro to_business_date(ts) -%}
  to_date({{ ts }})
{%- endmacro %}

{% macro for_business_date(col) -%}
  {{ col }} = {{ business_date() }}
{%- endmacro %}
