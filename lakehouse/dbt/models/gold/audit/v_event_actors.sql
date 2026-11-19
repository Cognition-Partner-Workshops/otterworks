{{ config(materialized='view') }}
select e.event_id, e.event_ts, e.event_type, u.user_id, u.display_name
from {{ ref('audit_event') }} e join {{ ref('audit_input_app_user') }} u on e.actor_user_id=u.user_id
