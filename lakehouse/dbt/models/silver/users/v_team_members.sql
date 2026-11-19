{{ config(materialized='view') }}

select t.team_id, t.team_name, u.user_id, u.display_name
from {{ ref('team') }} t
join {{ ref('team_member') }} m on t.team_id = m.team_id
join {{ ref('app_user') }} u on m.user_id = u.user_id
