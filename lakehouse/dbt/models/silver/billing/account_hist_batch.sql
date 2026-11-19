-- depends_on: {{ ref('customer_account_hist') }}
{{ config(pre_hook="{{ billing_history_guard() }}") }}
{% set previous = adapter.get_relation(database=this.database, schema=this.schema, identifier=this.identifier) if execute else none %}
{% if previous is not none %}
select business_dt from {{ this }}
union
{% endif %}
select to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd') as business_dt
