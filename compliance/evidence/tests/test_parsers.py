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


def test_action_groups_hide_dismissals_and_group_patterns():
    import build_evidence_pack as builder

    def entry(identifier, kind, flags, live, path='ignore'):
        return dict(id=identifier, kind=kind, flags=flags, live=live, path=path,
                    line=1, security=True, severity='high')

    rows = [entry('CVE-1', 'trivy', ['LIVE', 'NO_REVISIT_DATE'], True),
            entry('CVE-2', 'trivy', ['LIVE', 'NO_REVISIT_DATE'], True),
            entry('CVE-3', 'Dependabot-auto_dismissed', ['NO_REASON'], 'not checked', ''),
            entry('CVE-4', 'trivy', ['NO_REASON'], False)]
    groups = builder.action_groups(rows)
    assert len(groups) == 1
    assert 'CVE-1, CVE-2' in groups[0][0]
    assert groups[0][1] == 'Yes'
    assert builder.action_groups([]) == []
    assert [builder.live_label(value) for value in [True, False, 'not checked']] == ['Yes', 'No', 'not checked']


def test_weekly_evidence_absent_and_cwe_mapping(tmp_path):
    import json
    import build_evidence_pack as builder

    mapping = {'cwe_to_control': {'CWE-89': 'SSC-08'}, 'named_findings': {}, 'rule_patterns': []}
    advisory, sonar = builder.weekly_evidence(tmp_path, mapping)
    assert advisory['verdict'] == 'not measured / inconclusive'
    assert sonar['clusters'] == []
    (tmp_path / 'weekly-status.json').write_text(json.dumps({'wide_scan': {'download': {'exit_code': 0}}}))
    (tmp_path / 'wide-scan').mkdir()
    (tmp_path / 'wide-scan/clusters.json').write_text(json.dumps([
        {'cluster': 'one', 'rules': ['sql'], 'count': 5, 'cwes': ['CWE-89']}]))
    _, sonar = builder.weekly_evidence(tmp_path, mapping)
    assert sonar['clusters'][0]['controls'] == ['SSC-08']


def test_exact_line_provenance_uses_oldest_addition(monkeypatch):
    import build_evidence_pack as builder

    calls = []

    class Source:
        sha = 'target'

        def read(self, path):
            return 'CVE-2020-1 exp:2027-01-01'

        def link(self, path, line):
            return 'source'

    class GitHub:
        def commit_prs(self, sha):
            return [{'number': 1, 'url': 'pr'}]

    def command(*args):
        calls.append(args)
        if args[1] == 'log':
            return 'oldest\nnewest'
        if '--first-parent' in args:
            return '+CVE-2020-1 exp:2027-01-01'
        return ''

    monkeypatch.setattr(builder, 'command', command)
    rows = [dict(id='CVE-2020-1', path='.trivyignore', line=1, provenance_token='CVE-2020-1', flags=[])]
    builder.add_provenance(rows, Source(), GitHub())
    assert rows[0]['added_commit'] == 'oldest'
    assert '--reverse' in calls[0] and '--diff-filter=AM' in calls[0]
    assert '-SCVE-2020-1 exp:2027-01-01' in calls[0]


def test_weekly_summary_counts_distinct_alerts():
    import weekly_refresh as weekly

    rows = [dict(kind='dismissed', path='', line=None, id='CVE-1', security=True,
                 flags=['NO_REASON'], alert={'number': number}) for number in [1, 2]]
    pack = dict(exceptions=rows, sha='head', branch='demo', generated_at='now',
                metrics={'dependabot': [dict(severity='critical', past_sla=1, sla_days=7,
                                             open={'n': 2, 'median_days': 8})]},
                wide_scan={'clusters': []}, advisory_exposure={'verdict': 'inconclusive'})
    status = {key: {'exit_code': 0} for key in ['live_check', 'deps_inventory', 'deps_gate']}
    status['wide_scan'] = {'dispatch': {'exit_code': 1}, 'collection_error': 'unavailable'}
    rendered = weekly.summary(pack, status, {'exceptions': rows[:1]})
    assert 'Flagged exceptions: 2; new identities vs last committed pack: 1.' in rendered
    assert 'Wide scan limitation: unavailable' in rendered
    assert len(rendered.splitlines()) <= 40
    pack['exceptions'] = []
    rendered = weekly.summary(pack, status, {})
    assert 'Lead exception: none.' in rendered
    assert 'Flagged exceptions: 0; new identities vs last committed pack: not computable.' in rendered


def test_weekly_dispatch_failure_is_recorded(monkeypatch, tmp_path):
    import weekly_refresh as weekly

    monkeypatch.setattr(weekly, 'gh_json', lambda args: [])
    monkeypatch.setattr(weekly, 'run_step', lambda *args: {'exit_code': 1})
    result = weekly.wide_scan('demo', tmp_path)
    assert result['dispatch']['exit_code'] == 1
    assert 'watch' not in result and 'download' not in result


def test_advisory_rate_limit_retries_and_ci_label(monkeypatch, tmp_path):
    import json
    import weekly_refresh as weekly
    import build_evidence_pack as builder

    monkeypatch.setattr(weekly, 'ROOT', tmp_path)
    monkeypatch.setattr(weekly, 'configure_mirror', lambda out: None)
    monkeypatch.setattr(weekly, 'central_block', lambda: 'Maven repository HTTP 429 (rate limited)')
    delays = []
    monkeypatch.setattr(weekly.time, 'sleep', delays.append)
    ci = dict(conclusion='failure', url='https://example/run/1', headSha='previous', createdAt='now')
    monkeypatch.setattr(weekly, 'dependency_ci', lambda branch: ci)
    status = {}
    weekly.advisory_steps(status, tmp_path, 'demo')
    assert delays == [120, 300]
    assert len(status['deps_gate']['attempts']) == 3
    assert status['deps_gate']['exit_code'] == 75
    (tmp_path / 'weekly-status.json').write_text(json.dumps(status))
    advisory, _ = builder.weekly_evidence(tmp_path, {})
    assert advisory['verdict'].startswith('CI run evidence (local run blocked:')
    assert 'failure' in advisory['verdict'] and 'previous' in advisory['verdict']
    status['advisory_ci'] = None
    (tmp_path / 'weekly-status.json').write_text(json.dumps(status))
    advisory, _ = builder.weekly_evidence(tmp_path, {})
    assert 'no matching completed CI run available' in advisory['verdict']


def test_advisory_normal_run_does_not_retry(monkeypatch, tmp_path):
    import weekly_refresh as weekly

    monkeypatch.setattr(weekly, 'ROOT', tmp_path)
    monkeypatch.setattr(weekly, 'configure_mirror', lambda out: None)
    monkeypatch.setattr(weekly, 'central_block', lambda: None)
    calls = []

    def run(name, args, out):
        calls.append(args)
        log = out / (name + '.log')
        log.write_text('measured')
        return dict(exit_code=0, log=log.name, started_at='2026-11-13T00:00:00+00:00')

    monkeypatch.setattr(weekly, 'run_step', run)
    status = {}
    weekly.advisory_steps(status, tmp_path, 'demo')
    assert calls == [['make', 'deps-inventory'], ['make', 'deps-gate']]
    assert 'advisory_ci' not in status


def test_dependency_ci_selects_latest_branch_run(monkeypatch):
    import weekly_refresh as weekly

    runs = [dict(id=n, head_branch='demo', head_sha=str(n), conclusion='success',
                 created_at='2026-01-01', updated_at=f'2026-02-0{n}', html_url='run') for n in [1, 2]]

    def gh(args):
        if '/pulls?' in args[-1]:
            return [[]]
        if '/compare/' in args[-1]:
            return {'status': 'ahead'}
        return [{'workflow_runs': runs}]

    monkeypatch.setattr(weekly, 'gh_json', gh)
    result = weekly.dependency_ci('demo')
    assert result['headSha'] == '2'
    assert result['evidence_scope'] == 'target branch'
    assert result['head_sha_in_target'] is True


def test_dependency_ci_all_pr_heads_paginated(monkeypatch, tmp_path):
    import json
    import weekly_refresh as weekly
    import build_evidence_pack as builder

    def gh(args):
        if '/compare/' in args[-1]:
            return {'status': 'diverged'}
        assert '--paginate' in args and '--slurp' in args
        if '/pulls?' in args[-1]:
            assert 'base=demo' in args[-1]
            return [[dict(number=2901, state='open', head={'ref': 'new-pr'})],
                    [dict(number=2854, state='closed', merged_at='then', head={'ref': 'older-pr'}),
                     dict(number=2855, state='closed', merged_at=None, head={'ref': 'abandoned'})]]

        def run(number, branch, completed):
            return dict(id=number, head_branch=branch, head_sha='pr-sha', conclusion='success',
                        created_at='2026-11-13T13:39:42Z', updated_at=completed, html_url='https://example/run')

        return [{'workflow_runs': [run(1, 'demo', '2026-11-13T13:40:00Z')]},
                {'workflow_runs': [run(43435588623, 'older-pr', '2026-11-13T13:44:18Z'),
                                   run(3, 'unrelated', '2026-11-13T14:00:00Z'),
                                   run(4, 'abandoned', '2026-11-13T14:01:00Z')]}]

    monkeypatch.setattr(weekly, 'gh_json', gh)
    result = weekly.dependency_ci('demo')
    assert result['databaseId'] == 43435588623
    assert result['pr_numbers'] == [2854]
    assert result['evidence_scope'] == 'PR-head'
    assert result['head_sha_in_target'] is False
    (tmp_path / 'weekly-status.json').write_text(json.dumps(
        dict(advisory_blocked_reason='HTTP 429', advisory_ci=result)))
    advisory, _ = builder.weekly_evidence(tmp_path, {})
    assert 'PR-head evidence (PR #2854)' in advisory['verdict']
    assert 'head SHA in demo: No' in advisory['verdict']


def test_dependency_ci_empty_and_ancestry_unavailable(monkeypatch):
    import weekly_refresh as weekly

    monkeypatch.setattr(weekly, 'gh_json', lambda args: [[]] if '/pulls?' in args[-1] else [{'workflow_runs': []}])
    assert weekly.dependency_ci('demo') is None

    def gh(args):
        if '/pulls?' in args[-1]:
            return [[]]
        if '/compare/' in args[-1]:
            raise RuntimeError('comparison unavailable')
        return [{'workflow_runs': [dict(id=1, head_branch='demo', head_sha='sha', conclusion='success',
                                       created_at='then', updated_at='now', html_url='run')]}]

    monkeypatch.setattr(weekly, 'gh_json', gh)
    result = weekly.dependency_ci('demo')
    assert result['head_sha_in_target'] is None
    assert result['ancestry_error'] == 'comparison unavailable'


def test_mirror_unset_and_invalid(monkeypatch, tmp_path):
    import weekly_refresh as weekly

    monkeypatch.delenv('MAVEN_MIRROR_URL', raising=False)
    weekly.configure_mirror(tmp_path)
    assert not (tmp_path / 'toolchain').exists()
    monkeypatch.setenv('MAVEN_MIRROR_URL', 'http://untrusted')
    with pytest.raises(ValueError, match='HTTPS'):
        weekly.configure_mirror(tmp_path)


def test_mirror_configuration_is_isolated(monkeypatch, tmp_path):
    import weekly_refresh as weekly
    import xml.etree.ElementTree as xml

    monkeypatch.setenv('MAVEN_MIRROR_URL', 'https://mirror.example/maven')
    monkeypatch.setenv('PATH', '/usr/bin')
    monkeypatch.setenv('MAVEN_ARGS', '')
    monkeypatch.setenv('GRADLE_USER_HOME', '')
    monkeypatch.setattr(weekly.shutil, 'which', lambda *args, **kwargs: '/usr/bin/mvn')
    weekly.configure_mirror(tmp_path)
    settings = tmp_path / 'toolchain/settings.xml'
    assert xml.parse(settings).findtext('mirrors/mirror/url') == 'https://mirror.example/maven'
    assert '-s ' in weekly.os.environ['MAVEN_ARGS']
    assert 'mirror.example' in (tmp_path / 'toolchain/gradle-home/init.d/mirror.gradle').read_text()
    assert (tmp_path / 'toolchain/mvn').stat().st_mode & 0o100
