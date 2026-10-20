-- Row by row, net_amount + vendor_rounding_difference is the vendor file's net: the cent is shown, never lost.
select instruction_id, net_amount, vendor_rounding_difference, vendor_net_amount
  from {{ ref('stg_claims__claim_payments') }}
 where net_amount + vendor_rounding_difference <> vendor_net_amount
