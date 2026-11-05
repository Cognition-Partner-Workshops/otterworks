import re
from pathlib import Path

import pytest


@pytest.mark.parametrize('workload', ['doc_usage_dashboard', 'doc_search_api'])
@pytest.mark.parametrize('check', ['freshness', 'row_count', 'uniqueness', 'accepted_range', 'worked_example'])
def test_dq_check_is_tagged_and_returns_failure(workload, check):
    tests = Path(__file__).resolve().parents[1] / 'tests'
    example = {'doc_usage_dashboard': 'storage_examples.sql', 'doc_search_api': 'search_examples.sql'}
    prefix = 'doc_search_api_' if workload == 'doc_search_api' else ''
    path = tests / (example[workload] if check == 'worked_example' else f'dq/{workload}/{prefix}{check}.sql')
    sql = path.read_text()
    assert re.search(rf"config\(tags=\[[^\]]*'dq_{workload}'", sql)
    assert re.search(r'\bselect\s+.+?\bas failure\b', sql, re.IGNORECASE | re.DOTALL)


@pytest.mark.parametrize('workload', ['doc_usage_dashboard', 'doc_search_api'])
def test_landing_checks_use_export_snapshots_and_logical_counts(workload):
    tests = Path(__file__).resolve().parents[1] / f'tests/dq/{workload}'
    prefix = 'doc_search_api_' if workload == 'doc_search_api' else ''
    uniqueness = (tests / f'{prefix}uniqueness.sql').read_text()
    assert 'where _snapshot_date is not null and _snapshot_date in (' in uniqueness
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
