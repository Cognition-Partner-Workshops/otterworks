select t.team_id, t.team_name, count(m.team_member_id) as member_count
from {{ ref('team') }} t
left join {{ ref('team_member') }} m on t.team_id = m.team_id
group by t.team_id, t.team_name
