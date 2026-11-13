"""Offline evidence parser contracts; no API, scanner or repository state needed."""

import importlib.util
from pathlib import Path
import sys
from datetime import datetime, timezone

import pytest

EVIDENCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVIDENCE))
spec = importlib.util.spec_from_file_location('evidence_parsers', EVIDENCE / 'parsers.py')
parsers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parsers)


def test_trivy_entry_local_reason_and_date():
    text = '''# --- Debian: no fixed package in distro yet ---
# Each entry carries its reason and an exp date.
# zlib: no service links minizip. Revisit by 2027-02-28.
CVE-2023-45853 exp:2027-02-28
CVE-2024-6119
# perl: CPAN never runs in runtime. Revisit by 2027-02-28.
CVE-2023-31484 exp:2027-02-28
'''
    rows = parsers.parse_trivyignore(text)
    # Shared heading is not a package-specific justification for the next entry.
    assert rows[0]['has_reason']
    assert rows[0]['revisit_date'] == '2027-02-28'
    assert rows[1]['revisit_date'] is None
    assert not rows[1]['has_reason']
    assert 'Each entry carries' in rows[1]['section_claim']
    assert 'zlib' not in rows[1]['comment_block']
    assert rows[2]['revisit_date'] == '2027-02-28'


def test_trivy_missing_reason_glob_and_expired():
    rows = parsers.parse_trivyignore('''# Bulk ignore — revisit in Q4
CVE-2021-*
CVE-2020-1 exp:2001-01-01
''')
    assert rows[0]['glob']
    assert {'NO_REASON', 'NO_REVISIT_DATE', 'VAGUE_DATE', 'GLOB_INEFFECTIVE'} <= set(rows[0]['flags'])
    assert 'EXPIRED' in rows[1]['flags']
    assert 'NO_REVISIT_DATE' not in rows[1]['flags']


def test_trivy_invalid_date_and_empty():
    assert parsers.parse_trivyignore('# just a comment\n') == []
    row = parsers.parse_trivyignore('CVE-2020-1 exp:2026-99-01')[0]
    assert 'INVALID_DATE' in row['flags']


def test_nosemgrep_nearby_reason_multiple_rules():
    text = '''# SQL is an intentional lab fixture.
# Refactor removes the suppression.
# nosemgrep: python.sqlalchemy.text, python.sql.injection
execute(query)
x = 1 # nosemgrep: python.foo.bar
'''
    rows = parsers.parse_nosemgrep(text, 'app.py')
    assert [r['id'] for r in rows] == ['python.sqlalchemy.text', 'python.sql.injection', 'python.foo.bar']
    assert rows[0]['has_reason']
    assert rows[0]['line'] == 3
    assert 'NO_REASON' in rows[2]['flags']


def test_nosemgrep_empty_bare_and_inline():
    assert parsers.parse_nosemgrep('nosemgrep is documentation', 'doc.py') == []
    row = parsers.parse_nosemgrep('x = 1 # nosemgrep', 'app.py')[0]
    assert row['id'] == 'ALL-RULES'
    row = parsers.parse_nosemgrep('x = 1 // nosemgrep: java.foo.bar -- reason: fixture', 'app.java')[0]
    assert row['has_reason']


WORKFLOW = '''name: Test
on:
  push:
    branches: [main, 'workshop-**']
  pull_request:
    branches: [main]
    paths: ['services/**']
jobs:
  scan:
    if: github.event_name == 'pull_request'
    steps:
      - name: Scan
        run: tool --error
'''


def test_workflow_on_not_lost_to_yaml_boolean():
    row = parsers.parse_workflow(WORKFLOW, 'scan', 'demo-ciso')
    assert 'push' in row['triggers']
    assert row['events']['push'] == 'no (branch filter)'
    assert row['events']['pull_request'] == 'no (branch filter)'
    assert row['enforcement'].startswith('blocking')


def test_workflow_job_conditions_and_paths():
    row = parsers.parse_workflow(WORKFLOW, 'scan', 'main')
    assert row['events']['push'] == 'no (job event condition)'
    assert row['events']['pull_request'] == 'eligible; path-filtered'


def test_workflow_fail_open_and_reusable():
    text = '''on: workflow_call
jobs:
  scan:
    steps:
      - name: Scan
        continue-on-error: true
        run: tool || true
'''
    row = parsers.parse_workflow(text, 'scan', 'demo-ciso')
    assert row['events']['push'] == 'no (event absent)'
    assert row['enforcement'].startswith('informational')
    assert row['signals'][0]['markers'] == ['continue-on-error', '|| true']


def test_workflow_missing_job_and_malformed():
    with pytest.raises(ValueError, match='job not found'):
        parsers.parse_workflow(WORKFLOW, 'absent', 'main')
    with pytest.raises(ValueError, match='step not found'):
        parsers.parse_workflow(WORKFLOW, 'scan', 'main', 'absent')
    with pytest.raises(Exception):
        parsers.parse_workflow('jobs: [broken', 'scan', 'main')


def test_workflow_set_plus_e_does_not_make_error_flag_blocking():
    text = '''on: push
jobs:
  scan:
    steps:
      - run: |
          set +e
          semgrep --error
          rc=$?
          set -e
          echo "::warning::findings"
'''
    assert parsers.parse_workflow(text, 'scan', 'main')['enforcement'].startswith('informational')


def test_runtime_final_stage_alias_and_args():
    rows = parsers.runtime_images([('services/a/Dockerfile', '''ARG BASE=alpine:3.18.0
FROM golang:1.23 AS build
FROM --platform=$TARGETPLATFORM ${BASE} AS runtime
FROM runtime AS final
''')])
    assert rows[0]['image'] == 'alpine:3.18.0'
    assert rows[0]['resolved']
    assert parsers.runtime_images([]) == []
    assert not parsers.runtime_images([('Dockerfile', 'FROM ${UNSET}')])[0]['resolved']


def test_commented_fingerprint_group():
    rows = parsers.parse_commented_list('# Mock test data fixture.\nfingerprint1\nfingerprint2', '.gitleaksignore')
    assert all(row['has_reason'] for row in rows)


def test_builder_metrics_empty_and_known_durations():
    import build_evidence_pack as builder

    mapping = {'remediation_sla_days': {'critical': 7, 'high': 30, 'medium': 90, 'low': 180}}
    now = datetime(2026, 11, 13, tzinfo=timezone.utc)
    assert builder.metrics([], [], mapping, now)['dependabot'][0]['fixed']['n'] == 0
    alerts = [{'kind': 'Dependabot', 'severity': 'critical', 'state': 'fixed',
               'created_at': '2026-11-01T00:00:00Z', 'fixed_at': '2026-11-03T00:00:00Z'},
              {'kind': 'Dependabot', 'severity': 'critical', 'state': 'open',
               'created_at': '2026-11-01T00:00:00Z'}]
    result = builder.metrics(alerts, [], mapping, now)
    assert result['dependabot'][0]['fixed']['median_days'] == 2
    assert result['dependabot'][0]['open']['median_days'] == 12
    assert result['dependabot'][0]['past_sla'] == 1
    assert builder.stats([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])['p90_days'] == 9


def test_builder_missing_live_and_exact_id_matching(tmp_path):
    import build_evidence_pack as builder

    class Source:
        sha = 'target'

    reports, findings, _, warnings, _ = builder.load_live(tmp_path, Source(), [])
    rows = parsers.parse_trivyignore('CVE-2021-*')
    rows[0]['kind'] = 'trivy'
    builder.attach_live(rows, reports, findings)
    assert rows[0]['live'] == 'not checked'
    assert warnings
    finding = {'VulnerabilityID': 'CVE-2021-1', 'Severity': 'HIGH', 'scope': 'fs-no-ignore',
               'Target': 'lock', 'PkgName': 'pkg', 'InstalledVersion': '1'}
    builder.attach_live(rows, {'fs-no-ignore': {}}, [finding])
    assert rows[0]['live'] is False


def test_github_failure_is_not_clean(tmp_path, monkeypatch):
    import build_evidence_pack as builder
    from types import SimpleNamespace

    monkeypatch.setattr(builder.subprocess, 'run', lambda *a, **k:
                        SimpleNamespace(returncode=1, stderr='HTTP 403', stdout=''))
    github = builder.GitHub(tmp_path)
    assert github.api('alerts') == []
    assert 'HTTP 403' in github.errors[0]
    with pytest.raises(RuntimeError, match='HTTP 403'):
        github.api('alerts', required=True)
