{{ config(tags=['churn_model']) }}
with exports as (
 select parse_json('{"snapshot_date":"2026-11-02","exported_at":"2026-11-02T00:00:00Z","tables":{"AUTH_USERS":[{"id":"account","created_at":"2026-01-01","last_login_at":"2026-09-25"}],"ADMIN_ADMIN_USERS":[{"id":"account","status":"suspended"}]}}') as payload
 union all
 select parse_json('{"snapshot_date":"2026-11-05","exported_at":"2026-11-05T00:00:00Z","tables":{"AUTH_USERS":[{"id":"account","created_at":"2026-01-01","last_login_at":"2026-11-05"}],"ADMIN_ADMIN_USERS":[{"id":"account","status":"active"}]}}')
), periods as (select '2026-10-26'::date as week_start_date),
state as ({{ weekly_snapshot('periods','exports') }}),
users as ({{ snapshot_table('state','AUTH_USERS',{'id':'varchar','created_at':'timestamp_ntz','last_login_at':'timestamp_ntz'},'id') }}),
accounts as ({{ snapshot_table('state','ADMIN_ADMIN_USERS',{'id':'varchar','status':'varchar'},'id') }}),
versions as (select null::varchar as created_by,null::timestamp_ntz as created_at where false),
report as ({{ churn_scores('users','accounts','versions','periods',true) }})
select 'later login or status change rewrote the completed week' as failure
where (select count(*) from report where days_since_last_login=37 and login_points=40 and status_points=20 and churn_score=90)<>1
