select instruction_id,
       claim_number,
       value_date,
       to_char(value_date, 'YYYY-MM') as payment_period,
       indemnity_amount,
       expense_amount,
       salvage_credit,
       net_amount,
       vendor_debit_total,
       vendor_credit_total,
       vendor_debit_total - vendor_credit_total as vendor_net_amount,
       vendor_rounding_difference
  from {{ source('claims', 'claim_payments') }}
