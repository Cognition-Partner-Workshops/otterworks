-- Earned premium in the mart equals round(annual_premium / 12, 2) for every in-force policy-month.
with expected as (
    select sum(round(p.annual_premium / 12, 2)) as total
      from {{ ref('stg_commission__policies') }} p
      join {{ ref('int_period_spine') }} s on s.period_month >= to_char(p.issued_date, 'YYYY-MM')
     where p.status = 'IN_FORCE'
),
actual as (select sum(earned_premium) as total from {{ ref('loss_ratio_by_product_period') }})
select expected.total as expected_total, actual.total as actual_total
  from expected, actual where expected.total <> actual.total
