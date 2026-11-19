{% macro documents_storage_totals(start_date, end_date) -%}
select customer_id, sum(bytes_used) as bytes_used, sum(object_count) as object_count
from {{ ref('storage_usage_daily') }}
where usage_dt >= {{ start_date }} and usage_dt < {{ end_date }}
group by customer_id
{%- endmacro %}
