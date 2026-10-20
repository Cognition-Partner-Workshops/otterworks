select request_id, claim_number, region, severity, requested_date, estimated_amount,
       adjuster_id, sla_due_date, escalated
  from {{ source('claims', 'adjuster_assignments') }}
