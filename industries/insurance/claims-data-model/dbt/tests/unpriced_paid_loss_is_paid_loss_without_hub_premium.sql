-- unpriced_paid_loss is the net paid on claims whose policy carries no premium in the claims hub, to the cent.
with expected as (
    select coalesce(sum(pay.net_amount), 0) as total
      from {{ ref('stg_claims__claim_payments') }} pay
      join {{ ref('stg_claims__claims') }} c using (claim_number)
      join {{ ref('stg_claims__policies') }} p on p.policy_no = c.policy_no
     where not (p.source_system = 'CLAIMS_HUB' and p.annual_premium is not null)
),
actual as (
    select coalesce(sum(unpriced_paid_loss), 0) as total from {{ ref('loss_ratio_by_product_period') }}
)
select expected.total as expected_total, actual.total as actual_total
  from expected cross join actual
 where expected.total <> actual.total
