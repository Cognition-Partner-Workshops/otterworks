{% macro set_table_semantics(relation_cte, model_key) %}
  {% set decision = var('set_table_decisions', {}).get(model_key) %}
  {% if decision == 'distinct' %}
    select distinct * from {{ relation_cte }}
  {% elif decision == 'keep_all' %}
    select * from {{ relation_cte }}
  {% else %}
    {{ exceptions.raise_compiler_error("SET table decision required for " ~ model_key ~ ": choose distinct or keep_all in set_table_decisions") }}
  {% endif %}
{% endmacro %}
