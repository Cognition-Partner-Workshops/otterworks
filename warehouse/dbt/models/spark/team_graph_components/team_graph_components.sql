{{ config(materialized='table') }}

with memberships as (
    select distinct team_id, user_id
    from {{ source('spark_users', 'TEAM_MEMBER') }}
), eligible_teams as (
    select team_id
    from memberships
    group by team_id
    having count(*) > 1
), members as (
    select m.team_id, m.user_id
    from memberships m
    join eligible_teams t on t.team_id = m.team_id
), labels_0 as (
    select distinct user_id, user_id as component_id
    from members
)
{% for iteration in range(1, 7) %}
, team_labels_{{ iteration }} as (
    select m.team_id, min(l.component_id) as component_id
    from members m
    join labels_{{ iteration - 1 }} l on l.user_id = m.user_id
    group by m.team_id
), labels_{{ iteration }} as (
    select m.user_id, min(t.component_id) as component_id
    from members m
    join team_labels_{{ iteration }} t on t.team_id = m.team_id
    group by m.user_id
)
{% endfor %}
select user_id, component_id
from labels_6
