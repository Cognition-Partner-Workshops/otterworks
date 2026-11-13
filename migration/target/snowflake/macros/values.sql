{% macro warehouse_hash(columns) -%}
  md5(
  {%- for column in columns %}
    case when {{ column }} is null then 'N;'
         else 'V' || cast(length(cast({{ column }} as {{ dbt.type_string() }})) as {{ dbt.type_string() }})
              || ':' || cast({{ column }} as {{ dbt.type_string() }}) || ';' end
    {%- if not loop.last %} || {% endif %}
  {%- endfor %})
{%- endmacro %}

{% macro safe_numeric(expression, precision=18, scale=4) -%}
  {% if precision < 1 or precision > 38 or scale < 0 or scale > precision %}
    {{ exceptions.raise_compiler_error('Invalid decimal precision or scale') }}
  {% endif %}
  {{ return(adapter.dispatch('safe_numeric', 'warehouse_target')(expression, precision, scale)) }}
{%- endmacro %}

{% macro duckdb__safe_numeric(expression, precision, scale) -%}
  try_cast({{ expression }} as decimal({{ precision }}, {{ scale }}))
{%- endmacro %}

{% macro snowflake__safe_numeric(expression, precision, scale) -%}
  try_to_decimal(cast({{ expression }} as varchar), {{ precision }}, {{ scale }})
{%- endmacro %}

{% macro empty_string(expression, policy='preserve') -%}
  {% if policy == 'preserve' %}
    {{ expression }}
  {% elif policy == 'nullify' %}
    nullif({{ expression }}, '')
  {% else %}
    {{ exceptions.raise_compiler_error('Empty-string policy must be preserve or nullify') }}
  {% endif %}
{%- endmacro %}
