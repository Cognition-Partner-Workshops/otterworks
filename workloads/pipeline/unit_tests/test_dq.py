import re
from pathlib import Path

import pytest


@pytest.mark.parametrize('check', ['freshness', 'row_count', 'uniqueness', 'accepted_range', 'worked_example'])
def test_dq_check_is_tagged_and_returns_failure(check):
    tests = Path(__file__).resolve().parents[1] / 'tests'
    path = tests / ('storage_examples.sql' if check == 'worked_example' else f'dq/doc_usage_dashboard/{check}.sql')
    sql = path.read_text()
    assert re.search(r"config\(tags=\[[^\]]*'dq_doc_usage_dashboard'", sql)
    assert re.search(r'\bselect\s+.+?\bas failure\b', sql, re.IGNORECASE | re.DOTALL)


def test_landing_checks_use_export_snapshots_and_logical_counts():
    tests = Path(__file__).resolve().parents[1] / 'tests/dq/doc_usage_dashboard'
    uniqueness = (tests / 'uniqueness.sql').read_text()
    assert 'where _snapshot_date is not null and _snapshot_date in (' in uniqueness
    assert 'select payload:snapshot_date::date' in uniqueness
    assert 'listagg(distinct _row_hash' in uniqueness
    row_count = (tests / 'row_count.sql').read_text()
    assert 'count(distinct t.{{ key }})' in row_count
