"""Point-in-time churn features and the leakage check for churn_model.

Every feature for prediction date T reads only source rows dated before T.
The feature SQL never reads the label table (CHURN_EVENTS) or the support
notes. Search features are left out: search-service does not persist searches
(see workloads/doc_search_api.yaml), so there is no search source to read.
"""

from __future__ import annotations

from datetime import date, timedelta

SCHEMA = 'SYNTHETIC'
HORIZON_DAYS = 28
MIN_ACCOUNT_AGE_DAYS = 28
HOLDOUT_BUCKETS = 5


def _mondays(first: date, last: date) -> list[date]:
    out = []
    while first <= last:
        out.append(first)
        first += timedelta(days=7)
    return out


PERIODS = {
    'train': _mondays(date(2026, 3, 2), date(2026, 6, 29)),
    'validation': _mondays(date(2026, 7, 27), date(2026, 8, 17)),
    'holdout': _mondays(date(2026, 9, 14), date(2026, 10, 5)),
    'score': [date(2026, 11, 2)],
}

USAGE_FEATURES = [
    'days_since_last_login', 'logins_last_7d', 'logins_last_28d',
    'saves_last_7d', 'saves_prior_4wk_avg', 'save_drop_pct', 'active_days_last_28d',
    'login_ratio_7d', 'login_ratio_prev_7d', 'save_ratio_7d', 'save_ratio_prev_7d',
    'active_days_last_7d', 'active_days_ratio_7d',
    'account_age_days',
]
QUOTA_FEATURES = [
    'quota_used_pct', 'quota_used_pct_change_28d', 'quota_at_or_over_80pct',
    'tier_free', 'tier_basic', 'tier_pro',
]
FEATURES = USAGE_FEATURES + QUOTA_FEATURES
FEATURE_GROUPS = {'usage': USAGE_FEATURES, 'quota': QUOTA_FEATURES, 'search': []}
SEARCH_STATUS = 'blocked_on_source: search-service keeps searches in process memory only; no search.performed events exist'
LABEL_SOURCES = ('CHURN_EVENTS', 'SUPPORT_NOTES')


def check_split_gaps(periods: dict[str, list[date]] = PERIODS, horizon: int = HORIZON_DAYS) -> list[str]:
    """Each period's last label window must close before the next period starts."""
    order = ['train', 'validation', 'holdout', 'score']
    problems = []
    for earlier, later in zip(order, order[1:]):
        window_end = max(periods[earlier]) + timedelta(days=horizon)
        if window_end > min(periods[later]):
            problems.append(f'{earlier} labels run to {window_end}, after {later} starts {min(periods[later])}')
    return problems


def population_sql(schema: str = SCHEMA) -> str:
    """Accounts to score on each prediction date, their split and their label.

    Holdout accounts (hash bucket 0) are never used for training or for
    picking the threshold. An account is in the population on T if it is at
    least MIN_ACCOUNT_AGE_DAYS old and has not left before T. The label is 1
    if it leaves in [T, T + HORIZON_DAYS).
    """
    values = ', '.join(f"('{d.isoformat()}'::date, '{p}')" for p, ds in PERIODS.items() for d in ds)
    return f"""
create or replace table {schema}.CHURN_POPULATION as
select * from (
with dates (prediction_date, period) as (select * from values {values}),
accounts as (
 select account_id, created_at,
  iff(mod(abs(hash(account_id)), {HOLDOUT_BUCKETS}) = 0, 'holdout', 'model') as account_group
 from {schema}.ACCOUNTS)
select d.prediction_date, a.account_id, a.account_group,
 case when d.period = 'score' then 'score'
      when d.period = 'holdout' and a.account_group = 'holdout' then 'holdout'
      when d.period in ('train', 'validation') and a.account_group = 'model' then d.period end as split,
 iff(d.period = 'score', null, iff(c.churned_at >= d.prediction_date::timestamp_ntz
     and c.churned_at < dateadd(day, {HORIZON_DAYS}, d.prediction_date)::timestamp_ntz, 1, 0)) as label
from dates d
join accounts a on a.created_at < dateadd(day, -{MIN_ACCOUNT_AGE_DAYS}, d.prediction_date)::timestamp_ntz
left join {schema}.CHURN_EVENTS c on c.account_id = a.account_id
where (c.churned_at is null or c.churned_at >= d.prediction_date::timestamp_ntz)
) where split is not null
"""


def feature_select(spine: str, activity: str, snapshots: str, accounts: str, canary: bool = False) -> str:
    """One feature row per (prediction_date, account_id) in spine."""
    canary_col = ''
    if canary:
        canary_col = (",\n  sum(iff(a.activity_date >= s.prediction_date and a.activity_date < dateadd(day, 7, s.prediction_date),"
                      " a.document_saves, 0)) as saves_next_7d")
    canary_join = 'dateadd(day, 7, s.prediction_date)' if canary else 's.prediction_date'
    canary_out = ',\n coalesce(act.saves_next_7d, 0)::float as saves_next_7d' if canary else ''
    return f"""
with spine as (select prediction_date, account_id from {spine}),
act as (
 select s.prediction_date, s.account_id,
  max(iff(a.logins > 0 and a.activity_date < s.prediction_date, a.activity_date, null)) as last_login_date,
  sum(iff(a.activity_date >= dateadd(day, -7, s.prediction_date) and a.activity_date < s.prediction_date, a.logins, 0)) as logins_last_7d,
  sum(iff(a.activity_date >= dateadd(day, -28, s.prediction_date) and a.activity_date < s.prediction_date, a.logins, 0)) as logins_last_28d,
  sum(iff(a.activity_date >= dateadd(day, -7, s.prediction_date) and a.activity_date < s.prediction_date, a.document_saves, 0)) as saves_last_7d,
  sum(iff(a.activity_date >= dateadd(day, -35, s.prediction_date) and a.activity_date < dateadd(day, -7, s.prediction_date),
      a.document_saves, 0)) / 4.0 as saves_prior_4wk_avg,
  count_if(a.activity_date >= dateadd(day, -28, s.prediction_date) and a.activity_date < s.prediction_date) as active_days_last_28d,
  count_if(a.activity_date >= dateadd(day, -7, s.prediction_date) and a.activity_date < s.prediction_date) as active_days_last_7d,
  sum(iff(a.activity_date >= dateadd(day, -14, s.prediction_date) and a.activity_date < dateadd(day, -7, s.prediction_date),
      a.logins, 0)) as logins_prev_7d,
  sum(iff(a.activity_date >= dateadd(day, -14, s.prediction_date) and a.activity_date < dateadd(day, -7, s.prediction_date),
      a.document_saves, 0)) as saves_prev_7d,
  count_if(a.activity_date >= dateadd(day, -70, s.prediction_date) and a.activity_date < dateadd(day, -14, s.prediction_date)) / 8.0
      as active_days_baseline_avg,
  sum(iff(a.activity_date >= dateadd(day, -70, s.prediction_date) and a.activity_date < dateadd(day, -14, s.prediction_date),
      a.logins, 0)) / 8.0 as logins_baseline_avg,
  sum(iff(a.activity_date >= dateadd(day, -70, s.prediction_date) and a.activity_date < dateadd(day, -14, s.prediction_date),
      a.document_saves, 0)) / 8.0 as saves_baseline_avg{canary_col}
 from spine s
 join {activity} a on a.account_id = s.account_id and a.activity_date < {canary_join}
 group by 1, 2),
quota as (
 select s.prediction_date, s.account_id,
  max_by(q.used_bytes / q.quota_bytes, q.taken_at) as used_pct_now,
  max_by(iff(q.taken_at < dateadd(day, -28, s.prediction_date)::timestamp_ntz, q.used_bytes / q.quota_bytes, null),
         iff(q.taken_at < dateadd(day, -28, s.prediction_date)::timestamp_ntz, q.taken_at, null)) as used_pct_28d_ago
 from spine s
 join {snapshots} q on q.account_id = s.account_id and q.taken_at < s.prediction_date::timestamp_ntz
 group by 1, 2)
select s.prediction_date, s.account_id,
 datediff(day, coalesce(act.last_login_date, acc.created_at::date), s.prediction_date)::float as days_since_last_login,
 coalesce(act.logins_last_7d, 0)::float as logins_last_7d,
 coalesce(act.logins_last_28d, 0)::float as logins_last_28d,
 coalesce(act.saves_last_7d, 0)::float as saves_last_7d,
 coalesce(act.saves_prior_4wk_avg, 0)::float as saves_prior_4wk_avg,
 iff(coalesce(act.saves_prior_4wk_avg, 0) > 0,
     (act.saves_prior_4wk_avg - act.saves_last_7d) / act.saves_prior_4wk_avg, 0)::float as save_drop_pct,
 coalesce(act.active_days_last_28d, 0)::float as active_days_last_28d,
 iff(coalesce(act.logins_baseline_avg, 0) > 0, act.logins_last_7d / act.logins_baseline_avg, 1)::float as login_ratio_7d,
 iff(coalesce(act.logins_baseline_avg, 0) > 0, act.logins_prev_7d / act.logins_baseline_avg, 1)::float as login_ratio_prev_7d,
 iff(coalesce(act.saves_baseline_avg, 0) > 0, act.saves_last_7d / act.saves_baseline_avg, 1)::float as save_ratio_7d,
 iff(coalesce(act.saves_baseline_avg, 0) > 0, act.saves_prev_7d / act.saves_baseline_avg, 1)::float as save_ratio_prev_7d,
 coalesce(act.active_days_last_7d, 0)::float as active_days_last_7d,
 iff(coalesce(act.active_days_baseline_avg, 0) > 0, act.active_days_last_7d / act.active_days_baseline_avg, 1)::float
     as active_days_ratio_7d,
 datediff(day, acc.created_at::date, s.prediction_date)::float as account_age_days,
 coalesce(quota.used_pct_now, 0)::float as quota_used_pct,
 coalesce(quota.used_pct_now - quota.used_pct_28d_ago, 0)::float as quota_used_pct_change_28d,
 iff(coalesce(quota.used_pct_now, 0) >= 0.8, 1, 0)::float as quota_at_or_over_80pct,
 iff(acc.tier = 'free', 1, 0)::float as tier_free,
 iff(acc.tier = 'basic', 1, 0)::float as tier_basic,
 iff(acc.tier = 'pro', 1, 0)::float as tier_pro{canary_out}
from spine s
join {accounts} acc on acc.account_id = s.account_id
left join act on act.prediction_date = s.prediction_date and act.account_id = s.account_id
left join quota on quota.prediction_date = s.prediction_date and quota.account_id = s.account_id
"""


def features_sql(schema: str = SCHEMA) -> str:
    return f'create or replace table {schema}.CHURN_FEATURES as' + feature_select(
        f'{schema}.CHURN_POPULATION', f'{schema}.DAILY_ACTIVITY', f'{schema}.QUOTA_SNAPSHOTS', f'{schema}.ACCOUNTS')


def truncated_sources(schema: str, cutoff: date) -> tuple[str, str, str]:
    """The sources as they would have looked at the start of the cutoff day."""
    c = cutoff.isoformat()
    return (f"(select * from {schema}.DAILY_ACTIVITY where activity_date < '{c}'::date)",
            f"(select * from {schema}.QUOTA_SNAPSHOTS where taken_at < '{c}'::timestamp_ntz)",
            f"(select * from {schema}.ACCOUNTS where created_at < '{c}'::timestamp_ntz)")


def _hash(columns: list[str], alias: str) -> str:
    return 'hash(' + ', '.join(f'{alias}.{c}' for c in columns) + ')'


def truncation_check_sql(schema: str, cutoff: date, columns: list[str], canary: bool = False) -> str:
    """Rows on `cutoff` whose features change when every source row on or after it is removed."""
    c = cutoff.isoformat()
    spine = f"(select prediction_date, account_id from {schema}.CHURN_POPULATION where prediction_date = '{c}'::date)"
    full = feature_select(spine, f'{schema}.DAILY_ACTIVITY', f'{schema}.QUOTA_SNAPSHOTS', f'{schema}.ACCOUNTS', canary)
    cut = feature_select(spine, *truncated_sources(schema, cutoff), canary)
    return f"""
with full_rows as ({full}), cut_rows as ({cut})
select count(*) as rows_checked,
 count_if(c.account_id is null or {_hash(columns, 'f')} <> {_hash(columns, 'c')}) as mismatches
from full_rows f left join cut_rows c on c.prediction_date = f.prediction_date and c.account_id = f.account_id
"""


def stored_features_check_sql(schema: str, cutoff: date) -> str:
    """Stored CHURN_FEATURES rows that differ from features rebuilt on truncated sources."""
    c = cutoff.isoformat()
    spine = f"(select prediction_date, account_id from {schema}.CHURN_POPULATION where prediction_date = '{c}'::date)"
    cut = feature_select(spine, *truncated_sources(schema, cutoff))
    return f"""
with stored as (select * from {schema}.CHURN_FEATURES where prediction_date = '{c}'::date), cut_rows as ({cut})
select count(*) as rows_checked,
 count_if(c.account_id is null or {_hash(FEATURES, 's')} <> {_hash(FEATURES, 'c')}) as mismatches
from stored s left join cut_rows c on c.prediction_date = s.prediction_date and c.account_id = s.account_id
"""


def static_label_check(sql: str) -> list[str]:
    upper = sql.upper()
    return [name for name in LABEL_SOURCES if name in upper]
