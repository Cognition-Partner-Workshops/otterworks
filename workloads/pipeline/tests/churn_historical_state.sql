{{ config(tags=['churn_model']) }}
with periods as (
 select column1::date as week_start_date from values ('2026-10-26'),('2026-11-02')
), user_history as (
 select column1::number as id,column2::varchar as user_id,
  column3::timestamp_ntz as effective_at,column4::timestamp_ntz as created_at,
  column5::timestamp_ntz as last_login_at,(column1 in (11,13)) as is_deleted
 from values
 (1,'login','2026-11-01','2026-01-01','2026-09-25'),
 (2,'login','2026-11-02T08:00:00','2026-01-01','2026-11-02T08:00:00'),
 (3,'activate','2026-11-01','2026-01-01','2026-09-25'),
 (4,'delete','2026-11-01','2026-01-01','2026-09-25'),
 (5,'undelete','2026-11-01','2026-01-01','2026-09-25'),
 (6,'boundary','2026-11-01T23:59:59.999999','2026-01-01','2026-11-01T23:59:59.999999'),
 (7,'boundary','2026-11-02T00:00:00','2026-01-01','2026-11-02T00:00:00'),
 (8,'never','2026-11-01','2026-01-01',null),
 (9,'unknown','2026-11-02','2026-01-01','2026-09-25'),
 (10,'physical_delete','2026-11-01','2026-01-01','2026-09-25'),
 (11,'physical_delete','2026-11-02','2026-01-01','2026-09-25'),
 (12,'physical_restore','2026-11-01','2026-01-01','2026-09-25'),
 (13,'physical_restore','2026-11-02','2026-01-01','2026-09-25'),
 (14,'physical_restore','2026-11-03','2026-01-01','2026-09-25')
), status_history as (
 select column1::number as id,column2::varchar as user_id,
  column3::timestamp_ntz as effective_at,column4::varchar as status
 from values
 (1,'login','2026-11-01','active'),
 (2,'activate','2026-11-01','suspended'),
 (3,'activate','2026-11-02T09:00:00','active'),
 (4,'delete','2026-11-01','active'),
 (5,'delete','2026-11-02T09:00:00','deleted'),
 (6,'undelete','2026-11-01','deleted'),
 (7,'undelete','2026-11-02T09:00:00','active'),
 (8,'boundary','2026-11-01T23:59:59.999999','active'),
 (9,'boundary','2026-11-02T00:00:00','deleted'),
 (10,'never','2026-11-01','active'),
 (11,'unknown','2026-11-02','active')
), user_state as ({{ weekly_state('periods','user_history') }}),
status_state as ({{ weekly_state('periods','status_history') }}),
users as (select week_start_date,user_id as id,created_at,last_login_at from user_state where not is_deleted),
accounts as (select week_start_date,user_id as id,status from status_state),
versions as (select null::varchar as created_by,null::timestamp_ntz as created_at where false),
report as ({{ churn_scores('users','accounts','versions','periods',true) }}),
expected as (
 select column1::date as week_start_date,column2::varchar as account_id,
  column3::number as days_since_last_login,column4::number as login_points,
  column5::number as status_points,column6::number as churn_score
 from values
 ('2026-10-26','login',37,40,0,70),
 ('2026-10-26','activate',37,40,20,90),
 ('2026-10-26','delete',37,40,0,70),
 ('2026-10-26','boundary',0,0,0,30),
 ('2026-10-26','never',304,40,0,70),
 ('2026-10-26','physical_delete',37,40,0,70),
 ('2026-10-26','physical_restore',37,40,0,70),
 ('2026-11-02','login',6,0,0,30),
 ('2026-11-02','activate',44,40,0,70),
 ('2026-11-02','undelete',44,40,0,70),
 ('2026-11-02','never',311,40,0,70),
 ('2026-11-02','unknown',44,40,0,70)
 ,('2026-11-02','physical_restore',44,40,0,70)
), actual as (
 select week_start_date,account_id,days_since_last_login,login_points,status_points,churn_score from report
)
select 'incorrect historical state' as failure from (select * from expected minus select * from actual)
union all
select 'unexpected historical state' from (select * from actual minus select * from expected)
