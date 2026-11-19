with landed as (
    select
        cast(activity_id as bigint) as activity_id,
        cast(user_id as bigint) as user_id,
        cast(activity_dt as date) as activity_dt,
        cast(login_count as int) as login_count,
        cast(document_count as int) as document_count
    from {{ users_snapshot('user_activity_daily') }}
), calculated as (
    select
        10000000000L + user_id as activity_id,
        user_id,
        to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd') as activity_dt,
        cast(count(*) as int) as login_count,
        0 as document_count
    from {{ ref('login_event') }}
    where cast(login_ts as date) = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
    group by user_id
)
select * from landed where activity_id < 10000000000L
union all
select * from calculated
