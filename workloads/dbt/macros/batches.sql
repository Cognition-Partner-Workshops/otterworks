{% macro latest_batches(relation, date_expression) %}
select _export_id, {{ date_expression }} as snapshot_date
from {{ relation }}
where _exported_at is not null
{% if is_incremental() %}
  and {{ date_expression }} in (
    select {{ date_expression }} from {{ relation }}
    where _loaded_at >= dateadd(day, -{{ var('load_lookback_days', 7) }}, current_timestamp())
  )
{% endif %}
qualify row_number() over (
  partition by {{ date_expression }} order by _exported_at desc, _export_id desc
) = 1
{% endmacro %}

{% macro clear_changed_dates(driver, date_column) %}
{% if is_incremental() %}
  {% if date_column == 'snapshot_date' %}
    {% set expression = "convert_timezone('UTC', _exported_at)::date" %}
  {% elif date_column == 'window_end_date' %}
    {% set expression = "dateadd(day,-1,convert_timezone('UTC', _exported_at)::date)::date" %}
  {% else %}
    {% set expression = "dateadd(day,-7,date_trunc('week',convert_timezone('UTC', _exported_at)::date))::date" %}
  {% endif %}
  delete from {{ this }} where {{ date_column }} in (
    select snapshot_date from ({{ latest_batches(ref(driver), expression) }})
  )
{% else %}
  select 1
{% endif %}
{% endmacro %}

{% macro output_grants() %}
grant select on {{ 'view' if config.get('materialized') == 'view' else 'table' }} {{ this }} to role {{ var('reader_role') }};
grant select on {{ 'view' if config.get('materialized') == 'view' else 'table' }} {{ this }} to role {{ var('analyst_role') }};
{% endmacro %}

{% test grain(model, columns) %}
select {{ columns | join(', ') }} from {{ model }}
group by {{ columns | join(', ') }} having count(*) > 1
{% endtest %}
