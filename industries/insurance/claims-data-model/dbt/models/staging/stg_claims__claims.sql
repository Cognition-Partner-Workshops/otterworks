select claim_number,
       policy_no,
       policyholder_id,
       line_of_business,
       loss_cause,
       loss_date,
       to_char(loss_date, 'YYYY-MM') as loss_period,
       reported_date,
       estimated_amount,
       net_exposure,
       reserve_estimate,
       triage_outcome,
       entered_claims_system
  from {{ source('claims', 'claims') }}
