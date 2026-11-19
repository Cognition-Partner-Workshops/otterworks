{% test billing_journal_balance(model) %}
select lower(rtrim(currency_cd)) from {{ model }} group by lower(rtrim(currency_cd))
having sum(debit_amount) <> sum(credit_amount)
{% endtest %}

{% test billing_monthly_amounts(model) %}
select * from {{ model }} where total_amount <> subtotal_amount + tax_amount
  and invoice_id in (
      select h.invoice_id from {{ ref('invoice_hdr') }} h
      join {{ ref('subscription') }} s on h.subscription_id = s.subscription_id
      join {{ ref('plan_catalog') }} p on lower(rtrim(s.plan_code)) = lower(rtrim(p.plan_code))
      join {{ ref('tax_rate') }} t on h.tax_rate_id = t.tax_rate_id
      where h.invoice_dt <= to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd'))
{% endtest %}
