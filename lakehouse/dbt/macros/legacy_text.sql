{% macro legacy_text(column, length, fixed=false) -%}
{% if fixed %}rpad(substring({{ column }}, 1, {{ length }}), {{ length }}, ' ')
{% else %}substring({{ column }}, 1, {{ length }}){% endif %}
{%- endmacro %}
