-- The loss ratio never divides hub losses by Commission Pay premium: it is null in every row of a line of
-- business whose claims hub policies carry no premium.
select m.line_of_business, m.period_month, m.loss_ratio
  from {{ ref('loss_ratio_by_product_period') }} m
 where m.loss_ratio is not null
   and not exists (select 1 from {{ ref('stg_claims__policies') }} p
                    where p.source_system = 'CLAIMS_HUB' and p.annual_premium is not null
                      and p.line_of_business = m.line_of_business)
