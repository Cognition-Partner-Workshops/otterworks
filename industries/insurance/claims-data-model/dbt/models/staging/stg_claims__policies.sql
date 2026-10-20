select policy_no, source_system, policyholder_id, line_of_business, product_code, status,
       effective_date, expiration_date, annual_premium, deductible, coverage_limit
  from {{ source('claims', 'policies') }}
