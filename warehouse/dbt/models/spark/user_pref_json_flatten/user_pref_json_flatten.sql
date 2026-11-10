{{ config(alias='USER_PREF_JSON_FLATTEN', tags=['sfx-d1110', 'user_pref_json_flatten']) }}

with preferences as (
    select USER_PREF_ID, USER_ID, PREF_JSON,
           try_parse_json(coalesce(nullif(PREF_JSON, ''), '{}')) as parsed
    from {{ source('spark_users', 'USER_PREF') }}
)
select USER_PREF_ID, USER_ID, PREF_JSON,
{% for key in ['theme', 'notifications', 'locale'] %}
       case
           when parsed is null then null
           when parsed:{{ key }} is null then ''
           when is_null_value(parsed:{{ key }}) then 'None'
           when typeof(parsed:{{ key }}) = 'BOOLEAN'
               then iff(parsed:{{ key }}::boolean, 'True', 'False')
           else parsed:{{ key }}::varchar
       end as {{ key | upper }}{{ ',' if not loop.last }}
{% endfor %}
from preferences
