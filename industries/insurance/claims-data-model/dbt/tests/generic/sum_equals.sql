{% test sum_equals(model, column_name, to, to_column) %}
-- Fails when the column total differs from the total of to.to_column, to the cent.
with a as (select coalesce(sum({{ column_name }}), 0) as total from {{ model }}),
     b as (select coalesce(sum({{ to_column }}), 0) as total from {{ to }})
select a.total as model_total, b.total as compared_total
  from a cross join b
 where a.total <> b.total
{% endtest %}
