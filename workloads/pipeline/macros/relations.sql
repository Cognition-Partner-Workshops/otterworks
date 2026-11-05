{% macro database_for(workload) -%}
DB_{{ workload | upper }}_{{ var('run_token') }}
{%- endmacro %}

{% macro generate_schema_name(custom_schema_name, node) -%}
{{ custom_schema_name or target.schema }}
{%- endmacro %}

{% macro latest_rows(relation, key, per_snapshot=false) %}
select *
from {{ relation }}
qualify row_number() over (
  partition by {% if per_snapshot %}_snapshot_date, {% endif %}{{ key }}
  order by _snapshot_date desc, _exported_at desc, _row_hash desc
) = 1
{% endmacro %}

{% macro weekly_snapshot(periods, exports) %}
select p.week_start_date, e.payload
from {{ periods }} p join {{ exports }} e
 on e.payload:snapshot_date::date >= dateadd(day,7,p.week_start_date)
 and e.payload:snapshot_date::date < dateadd(day,14,p.week_start_date)
qualify row_number() over (partition by p.week_start_date
 order by e.payload:snapshot_date::date, e.payload:exported_at::timestamp_ntz,
 sha2(to_json(e.payload),256) desc) = 1
{% endmacro %}

{% macro snapshot_table(snapshots, table, columns, key) %}
select s.week_start_date,
{% for column, datatype in columns.items() %}
 f.value:{{ column }}::{{ datatype }} as {{ column }}{% if not loop.last %},{% endif %}
{% endfor %}
from {{ snapshots }} s, lateral flatten(input=>s.payload:tables:{{ table }}) f
qualify row_number() over (partition by s.week_start_date, f.value:{{ key }}::varchar
 order by sha2(to_json(f.value),256) desc) = 1
{% endmacro %}

{% macro raw_rows(table, key, per_snapshot=false) %}
{{ latest_rows(
  "(select t.* from " ~ this.database ~ ".RAW." ~ table ~ " t join (select payload:snapshot_date::date as snapshot_date, max(payload:exported_at::timestamp_ntz) as exported_at from " ~ this.database ~ ".RAW.PIPELINE_EXPORTS group by 1) e on t._snapshot_date=e.snapshot_date and t._exported_at=e.exported_at" ~ ("" if per_snapshot else " where e.snapshot_date=(select max(payload:snapshot_date::date) from " ~ this.database ~ ".RAW.PIPELINE_EXPORTS)") ~ ")",
  key, per_snapshot
) }}
{% endmacro %}

{% macro report_periods(kind) %}
select distinct
{% if kind == 'snapshot_date' %}
payload:snapshot_date::date as snapshot_date
{% elif kind == 'window_end_date' %}
dateadd(day,-1,payload:snapshot_date::date)::date as window_end_date
{% else %}
dateadd(day,-7, dateadd(day, 1-dayofweekiso(payload:snapshot_date::date), payload:snapshot_date::date))::date as week_start_date
{% endif %}
from {{ this.database }}.RAW.PIPELINE_EXPORTS
{% endmacro %}
