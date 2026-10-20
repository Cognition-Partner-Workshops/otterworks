{#- Fails unless sum(column_name) equals `expected` exactly (numeric, no tolerance). -#}
{% test column_total_equals(model, column_name, expected) %}
select actual_total
from (select coalesce(sum({{ column_name }}), 0) as actual_total from {{ model }}) summed
where actual_total <> {{ expected }}::numeric
{% endtest %}
