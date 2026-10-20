select po.policy_id,
       po.policy_no,
       po.product_code,
       pr.line_of_business,
       po.annual_premium,
       po.issued_date,
       po.status
  from {{ source('commission', 'policies') }} po
  join {{ source('commission', 'products') }} pr using (product_code)
