{% macro billing_history_guard() -%}
{% set batch = adapter.get_relation(database=this.database, schema=this.schema, identifier='account_hist_batch') if execute else none %}
{% if batch is not none %}
{% set guard %}
select assert_true(
    not exists (select 1 from {{ batch }}
                where business_dt > to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')),
    'A completed later account-history business date already exists')
{% endset %}
{% set result = run_query(guard) %}
{% endif %}
select 1
{%- endmacro %}

{% macro billing_history_keys() -%}
{% if execute %}
{% set guard %}
select assert_true(
    not exists (select customer_id from {{ ref('stg_customer_account') }}
                group by customer_id having customer_id is null or count(*) > 1),
    'Account history requires nonnull unique customer IDs')
{% endset %}
{% set result = run_query(guard) %}
{% endif %}
select 1
{%- endmacro %}

{% test billing_history_invariants(model) %}
with intervals as (
    select *, lag(valid_to_dt) over (partition by customer_id order by valid_from_dt) as previous_end
    from {{ model }}
)
select * from intervals
where valid_from_dt >= valid_to_dt
   or previous_end > valid_from_dt
{% endtest %}

{% test billing_history_key(model) %}
select customer_id, valid_from_dt from {{ model }}
group by customer_id, valid_from_dt having count(*) > 1
{% endtest %}

{% test billing_snapshot_count(model, staging) %}
select 1 as mismatch
where (select count(*) from {{ model }}) <> (select count(*) from {{ ref(staging) }})
{% endtest %}
