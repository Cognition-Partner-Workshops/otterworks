select agent_id, agent_code, full_name, status
  from {{ source('commission', 'agents') }}
