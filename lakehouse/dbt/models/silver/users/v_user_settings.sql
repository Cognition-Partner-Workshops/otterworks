{{ config(materialized='view') }}

select u.user_id, u.display_name, p.pref_name, p.pref_value
from {{ ref('app_user') }} u
join {{ ref('user_pref') }} p on u.user_id = p.user_id
