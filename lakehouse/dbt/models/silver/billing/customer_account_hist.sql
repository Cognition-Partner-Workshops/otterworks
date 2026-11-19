{{ config(pre_hook=["{{ billing_history_guard() }}", "{{ billing_history_keys() }}"]) }}
{% set previous = adapter.get_relation(database=this.database, schema=this.schema, identifier=this.identifier) if execute else none %}
with prior as (
{% if previous is not none %}
    select customer_id, valid_from_dt,
           case when valid_to_dt = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
                then date '9999-12-31' else valid_to_dt end as valid_to_dt,
           status_cd, currency_cd
    from {{ this }}
    where valid_from_dt <> to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
{% else %}
    select cast(null as bigint) customer_id, cast(null as date) valid_from_dt,
           cast(null as date) valid_to_dt, cast(null as string) status_cd,
           cast(null as string) currency_cd where false
{% endif %}
), incoming as (
    select customer_id, status_cd, currency_cd from {{ ref('stg_customer_account') }}
), changes as (
    select h.customer_id, h.valid_from_dt
    from prior h join incoming a on a.customer_id = h.customer_id
    where h.valid_to_dt = date '9999-12-31'
      and (not (lower(rtrim(a.status_cd)) <=> lower(rtrim(h.status_cd)))
        or not (lower(rtrim(a.currency_cd)) <=> lower(rtrim(h.currency_cd))))
), closed as (
    select h.customer_id, h.valid_from_dt,
           case when c.customer_id is not null
                then to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
                else h.valid_to_dt end as valid_to_dt,
           h.status_cd, h.currency_cd
    from prior h left join changes c
      on h.customer_id = c.customer_id and h.valid_from_dt = c.valid_from_dt
)
select * from closed
union all
select a.customer_id, to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd') as valid_from_dt,
       date '9999-12-31' as valid_to_dt,
       {{ legacy_text('a.status_cd', 12, true) }} as status_cd,
       {{ legacy_text('a.currency_cd', 3, true) }} as currency_cd
from incoming a
where not exists (select 1 from closed h
                  where h.customer_id = a.customer_id and h.valid_to_dt = date '9999-12-31')
