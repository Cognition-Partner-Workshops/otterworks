{% macro audit_timestamp(column) -%}
date_trunc('second', cast({{ column }} as timestamp) + interval 500 milliseconds)
{%- endmacro %}
