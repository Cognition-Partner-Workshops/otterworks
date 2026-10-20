{#- Fails unless the relation has exactly `expected` rows. -#}
{% test row_count_equals(model, expected) %}
select actual_rows
from (select count(*) as actual_rows from {{ model }}) counted
where actual_rows <> {{ expected }}
{% endtest %}
