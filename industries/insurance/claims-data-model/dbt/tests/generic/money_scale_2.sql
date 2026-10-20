{% test money_scale_2(model, column_name) %}
-- Fails for any value that carries more than two decimals (money is numeric scale 2 end to end).
select {{ column_name }} from {{ model }} where {{ column_name }} <> round({{ column_name }}, 2)
{% endtest %}
