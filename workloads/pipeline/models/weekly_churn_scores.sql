{{ config(database=database_for("churn_model"), period="week_start_date", column_ddl="week_start_date DATE, account_id VARCHAR(36), days_since_last_login NUMBER(6,0), activity_this_week NUMBER(10,0), activity_prior_4wk_avg NUMBER(10,2), activity_drop_pct NUMBER(7,2), login_points NUMBER(3,0), activity_points NUMBER(3,0), status_points NUMBER(3,0), churn_score NUMBER(3,0), risk_band VARCHAR(8), model_version VARCHAR(16)", columns_order=["week_start_date", "account_id", "days_since_last_login", "activity_this_week", "activity_prior_4wk_avg", "activity_drop_pct", "login_points", "activity_points", "status_points", "churn_score", "risk_band", "model_version"]) }}
with periods as (
  {{ report_periods("week_start_date") }}
), user_history as (
  {{ latest_rows(this.database ~ ".RAW.AUTH_USER_STATE_HISTORY", "id") }}
), status_history as (
  {{ latest_rows(this.database ~ ".RAW.ADMIN_USER_STATE_HISTORY", "id") }}
), user_state as (
  {{ weekly_state("periods", "user_history") }}
), status_state as (
  {{ weekly_state("periods", "status_history") }}
), users as (
  select week_start_date,user_id as id,created_at,last_login_at from user_state
), accounts as (
  select week_start_date,user_id as id,status from status_state
), versions as (
  {{ raw_rows("DOCUMENT_DOCUMENT_VERSIONS", "id") }}
)
select * from ({{ churn_scores("users", "accounts", "versions", "periods", true) }})
