import re
from pathlib import Path

import pytest
import yaml


WORKLOADS = ['doc_usage_dashboard', 'doc_search_api', 'churn_model']


@pytest.mark.parametrize('workload', WORKLOADS)
@pytest.mark.parametrize('check', ['freshness', 'row_count', 'uniqueness', 'accepted_range', 'worked_example'])
def test_dq_check_is_tagged_and_returns_failure(workload, check):
    tests = Path(__file__).resolve().parents[1] / 'tests'
    example = {'doc_usage_dashboard': 'storage_examples.sql', 'doc_search_api': 'search_examples.sql', 'churn_model': 'churn_examples.sql'}
    prefix = '' if workload == 'doc_usage_dashboard' else f'{workload}_'
    path = tests / (example[workload] if check == 'worked_example' else f'dq/{workload}/{prefix}{check}.sql')
    sql = path.read_text()
    assert re.search(rf"config\(tags=\[[^\]]*'dq_{workload}'", sql)
    assert re.search(r'\bselect\s+.+?\bas failure\b', sql, re.IGNORECASE | re.DOTALL)


@pytest.mark.parametrize('workload', WORKLOADS)
def test_landing_checks_use_export_snapshots_and_logical_counts(workload):
    tests = Path(__file__).resolve().parents[1] / f'tests/dq/{workload}'
    prefix = '' if workload == 'doc_usage_dashboard' else f'{workload}_'
    uniqueness = (tests / f'{prefix}uniqueness.sql').read_text()
    assert 'select payload:snapshot_date::date' in uniqueness
    assert 'listagg(distinct _row_hash' in uniqueness
    row_count = (tests / f'{prefix}row_count.sql').read_text()
    assert 'count(distinct t.{{ key }})' in row_count


def test_search_row_counts_compare_each_account_in_both_sources():
    tests = Path(__file__).resolve().parents[1] / 'tests/dq/doc_search_api'
    sql = (tests / 'doc_search_api_row_count.sql').read_text()
    assert "{% for source in ['manifest','landed'] %}" in sql
    assert 'select account_id, sum(n) as n' in sql
    assert 'select account_id, count(*) as n' in sql
    assert 'full outer join actual a on e.account_id is not distinct from a.account_id' in sql
    assert 'where coalesce(e.n,0)<>coalesce(a.n,0)' in sql
    assert "' expected='" in sql and "' actual='" in sql


def test_churn_gate_keeps_all_example_values_and_columns_exact():
    pipeline = Path(__file__).resolve().parents[1]
    spec = yaml.safe_load((pipeline.parent / 'churn_model/spec.yaml').read_text())
    sql = (pipeline / 'tests/churn_examples.sql').read_text()
    for column in spec['output']['columns']:
        assert f"as {column['name']}" in sql
    for row in spec['examples']['rows']:
        assert f"'{row['week_start_date']}'" in sql
        assert f"'{row['model_version']}'" in sql
        values = [row[key] for key in row if key not in ('week_start_date', 'model_version')]
        expected = '(' + ','.join(f"'{v}'" if isinstance(v, str) else f'{v:g}' for v in values) + ')'
        normalized = re.sub(r'(?<=\d)\.00(?=[,)])', '', sql)
        assert expected in normalized
    assert 'select * from actual minus select * from expected' in sql
    assert 'select * from expected minus select * from actual' in sql
    assert 'requires authoritative history before week end' in sql


def test_churn_ranges_reject_null_metrics_and_preserve_the_recall_gate():
    tests = Path(__file__).resolve().parents[1] / 'tests/dq/churn_model'
    ranges = (tests / 'churn_model_accepted_range.sql').read_text()
    for column in ['days_since_last_login', 'activity_this_week', 'activity_prior_4wk_avg',
                   'login_points', 'activity_points', 'status_points', 'churn_score',
                   'risk_band', 'model_version', 'recall', 'precision', 'auc']:
        assert f'{column} is null' in ranges
    assert 'recall not between 0.50 and 1' in ranges
    assert "coalesce(cause,'evaluation metrics unavailable or outside accepted bounds')" in ranges
    assert 'activity_drop_pct is distinct from round(' in ranges
    assert 'churn_score is distinct from login_points+activity_points+status_points' in ranges
    assert "risk_band not in ('low','medium','high')" in ranges
    assert 's.score is null or s.score not between 0 and 1' in ranges
    assert 'training depends on sufficient source history' in ranges
    for threshold in [25, 50, 75]:
        assert f'100*(activity_prior_4wk_avg-activity_this_week)/nullif(activity_prior_4wk_avg,0)>={threshold}' in ranges
        assert f'when activity_drop_pct>={threshold}' not in ranges


def test_churn_row_counts_use_both_sources_and_strict_history_cutoff():
    tests = Path(__file__).resolve().parents[1] / 'tests/dq/churn_model'
    sql = (tests / 'churn_model_row_count.sql').read_text()
    assert "{% for source in ['manifest','landed'] %}" in sql
    assert 'u.effective_at<dateadd(day,7,e.week_start_date)' in sql
    assert 's.effective_at<dateadd(day,7,e.week_start_date)' in sql
    assert 'order by u.effective_at desc,u.id desc' in sql
    assert 'u.created_at<=dateadd(day,-28,e.week_start_date)' in sql
    assert "coalesce(s.status,'active')<>'deleted'" in sql
    assert 'not coalesce(u.is_deleted,false)' in sql
    assert "('AUTH_USERS',2000)" in sql and "('DOCUMENT_DOCUMENTS',50000)" in sql


@pytest.mark.parametrize('workload', WORKLOADS)
def test_freshness_rejects_failed_latest_attempt_and_unprocessed_export(workload):
    tests = Path(__file__).resolve().parents[1] / f'tests/dq/{workload}'
    prefix = '' if workload == 'doc_usage_dashboard' else f'{workload}_'
    sql = (tests / f'{prefix}freshness.sql').read_text()
    assert 'SCHEDULED_TIME_RANGE_END=>CURRENT_TIMESTAMP()' in sql
    assert 'order by scheduled_time desc, attempt_number desc' in sql
    assert "state not in ('SCHEDULED','EXECUTING')" in sql
    assert "from latest_attempt where state<>'SUCCEEDED'" in sql
    assert "convert_timezone('UTC',r.completed_time)::timestamp_ntz<e.exported_at" in sql
    assert 'completed_time<=dateadd(hour,-2,current_timestamp())' in sql


def test_retained_score_completeness_uses_evaluated_run_cohort_not_weekly_output():
    tests = Path(__file__).resolve().parents[1] / 'tests/dq/churn_model'
    sql = (tests / 'churn_model_row_count.sql').read_text()
    assert 'APP.CHURN_MODEL_EVALUATION e' in sql and 'APP.CHURN_MODEL_RUNS r on r.run_id=e.run_id' in sql
    assert 'p.payload:exported_at::timestamp_ntz<=r.started_at' in sql
    assert "[('users','AUTH_USERS'),('auth','AUTH_USER_STATE_HISTORY'),('admin','ADMIN_USER_STATE_HISTORY')]" in sql
    assert 'coalesce(u.created_at,h.created_at,h.effective_at)' in sql
    assert 'a.created_at<dateadd(day,-28,r.prediction_date)' in sql
    assert 's.effective_at<r.prediction_date' in sql
    assert "coalesce(s.status,'active') not in ('suspended','deleted')" in sql
    assert 'retained model scores are empty for evaluated run=' in sql
    assert 'from expected_scores e full outer join actual_scores a' in sql
    assert 'a.run_id=e.run_id and a.account_id=e.account_id and a.prediction_date=e.prediction_date' in sql
    assert 'where e.run_id is null or a.run_id is null or a.n<>1' in sql
