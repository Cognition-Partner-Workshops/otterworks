"""Build linked audit evidence from Git, GitHub and optional live scanner reports."""

import argparse
import hashlib
import importlib.util
import json
import math
import re
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
import xml.etree.ElementTree as ET

import yaml

from parsers import (
    exception, parse_commented_list, parse_nosemgrep, parse_trivyignore,
    parse_workflow, runtime_images,
)

ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = 'Cognition-Partner-Workshops/otterworks'
WEB = f'https://github.com/{REPOSITORY}'
SEVERITIES = ['critical', 'high', 'medium', 'low', 'unknown']
FINDING_PATTERN = r'OW-SEC-4\d\d|DAST-[A-Z0-9-]+|CVE-\d{4}-\d+|GHSA-[a-z0-9-]+'


def command(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


class GitSource:
    def __init__(self, branch):
        self.branch = branch
        self.sha = command('git', 'rev-parse', f'origin/{branch}')
        self.files = command('git', 'ls-tree', '-r', '--name-only', self.sha).splitlines()

    def read(self, path):
        return command('git', 'show', f'{self.sha}:{path}')

    def link(self, path, line=1, sha=None):
        return f'{WEB}/blob/{sha or self.sha}/{quote(path)}#L{line}'


class GitHub:
    def __init__(self, cache, refresh=False):
        self.cache = cache
        self.cache.mkdir(parents=True, exist_ok=True)
        self.refresh = refresh
        self.errors = []
        self.sources = []

    def api(self, endpoint, paginate=False, required=False):
        key = hashlib.sha256((endpoint + str(paginate)).encode()).hexdigest()
        path = self.cache / f'{key}.json'
        if path.exists() and not self.refresh:
            self.sources.append({'endpoint': endpoint, 'cached': True,
                                 'fetched_at': datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()})
            return json.loads(path.read_text())
        args = ['gh', 'api', endpoint]
        if paginate:
            args += ['--paginate', '--slurp']
        result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
        if result.returncode:
            message = f'{endpoint}: {result.stderr.strip()}'
            if required:
                raise RuntimeError(message)
            self.errors.append(message)
            return []
        data = json.loads(result.stdout)
        if paginate:
            data = [item for page in data for item in page]
        path.write_text(json.dumps(data))
        self.sources.append({'endpoint': endpoint, 'cached': False,
                             'fetched_at': datetime.now(timezone.utc).isoformat()})
        return data

    def commit_prs(self, sha):
        if not sha:
            return []
        associated = self.api(f'repos/{REPOSITORY}/commits/{sha}/pulls?per_page=100', True)
        merged = sorted([p for p in associated if p.get('merged_at')], key=lambda p: p['merged_at'])
        exact = [p for p in merged if p.get('merge_commit_sha') == sha]
        selected = exact or merged[:1]
        return [{'number': pr['number'], 'url': pr['html_url'], 'title': pr['title']}
                for pr in selected]


def controls_for(text, mapping, source=None, cwes=()):
    controls = set(mapping.get('sources', {}).get(source, []))
    for cwe in cwes:
        if cwe in mapping['cwe_to_control']:
            controls.add(mapping['cwe_to_control'][cwe])
    for name, values in mapping['named_findings'].items():
        if name in text:
            controls.update(values)
    for rule in mapping['rule_patterns']:
        if re.search(rule['pattern'], text, re.I):
            controls.update(rule['controls'])
    if re.search(r'CVE-\d|GHSA-', text):
        controls.add('SSC-11')
    return sorted(controls or {'OUT-OF-CATALOG'})


def find_line(text, token):
    return next((i for i, line in enumerate(text.splitlines(), 1) if token in line), 1)


def collect_exceptions(src, mapping):
    rows = parse_trivyignore(src.read('.trivyignore'))
    for row in rows:
        row.update(kind='trivy', controls=['SSC-11'], provenance_token=row['id'])
    for row in parse_commented_list(src.read('.gitleaksignore'), '.gitleaksignore'):
        row.update(kind='gitleaks', controls=['SSC-03'], provenance_token=row['id'])
        rows.append(row)
    extensions = ['*.py', '*.tf', '*.java', '*.ts', '*.js', '*.go', '*.rb', '*.rs', '*.sql', '*.kt', '*.cs']
    result = subprocess.run(['git', 'grep', '-l', '-I', 'nosemgrep', src.sha, '--', *extensions],
                            cwd=ROOT, text=True, capture_output=True)
    for name in result.stdout.splitlines():
        path = name.split(':', 1)[1]
        for row in parse_nosemgrep(src.read(path), path):
            row.update(kind='nosemgrep', provenance_token=row['id'],
                       controls=controls_for(row['id'] + ' ' + row['comment_block'], mapping,
                                             source='infrastructure' if path.endswith('.tf') else None))
            if path.endswith('.tf'):
                row['controls'] = ['OUT-OF-CATALOG']
            rows.append(row)
    workflow = '.github/workflows/security-scan.yml'
    text = src.read(workflow)
    token = '--skip-dirs services/report-service'
    if token in text:
        row = exception('services/report-service', workflow, find_line(text, token),
                        'Intentional legacy Java 8 service for upgrade exercise (.trivyignore header).')
        row.update(kind='skip-dirs', controls=['SSC-11'], provenance_token=token)
        rows.append(row)
    path = 'security/dast/zap/zap-baseline.conf'
    for number, line in enumerate(src.read(path).splitlines(), 1):
        match = re.match(r'(\d+)\s+(IGNORE|WARN)\s*(.*)', line)
        if match:
            row = exception(match[1], path, number, match[3])
            row.update(kind='zap-' + match[2], controls=controls_for(line, mapping),
                       provenance_token=match[1])
            rows.append(row)
    path = 'security/dast/baseline.json'
    text = src.read(path)
    accepted = json.loads(text).get('accepted', [])
    if isinstance(accepted, dict):
        accepted = [dict(id=key, **value) if isinstance(value, dict) else
                    {'id': key, 'reason': value} for key, value in accepted.items()]
    for item in accepted:
        item = item if isinstance(item, dict) else {'id': item}
        identifier = item.get('id', item.get('finding_id', 'unknown'))
        row = exception(identifier, path, find_line(text, identifier), str(item.get('reason', '')),
                        item.get('expires_at', item.get('revisit_date')))
        row.update(kind='dast-accepted', controls=controls_for(identifier, mapping),
                   provenance_token=identifier)
        rows.append(row)
    path = '.github/codeql/codeql-config.yml'
    text = src.read(path)
    for pattern in yaml.safe_load(text).get('paths-ignore', []):
        row = exception(pattern, path, find_line(text, pattern))
        row.update(kind='codeql-path', controls=['SSC-01', 'SSC-02', 'SSC-04', 'SSC-07', 'SSC-08', 'SSC-09'],
                   provenance_token=pattern)
        rows.append(row)
    path = 'security/deps/modules.yaml'
    text = src.read(path)
    for item in yaml.safe_load(text).get('exempt', []):
        row = exception(item['path'], path, find_line(text, item['path']), item.get('reason', ''))
        row.update(kind='deps-exempt', controls=['SSC-11'], provenance_token=item['path'])
        rows.append(row)
    path = 'services/report-service/checkstyle-suppressions.xml'
    text = src.read(path)
    for item in ET.fromstring(text).findall('suppress'):
        identifier = item.attrib['files'] + ':' + item.attrib['checks']
        row = exception(identifier, path, find_line(text, item.attrib['files']),
                        'Pre-existing golden-app sources are exempt; style checks only.', security=False)
        row.update(kind='checkstyle (non-security)', controls=[], provenance_token=item.attrib['files'])
        rows.append(row)
    return rows


def add_provenance(rows, src, github):
    cache = {}
    for row in rows:
        row['file_url'] = src.link(row['path'], row['line'])
        token = row.pop('provenance_token')
        key = row['path'], token
        if key not in cache:
            commits = command('git', 'log', src.sha, '--format=%H', f'-S{token}', '--', row['path']).splitlines()
            added = None
            for sha in commits:
                diff = command('git', 'show', '--format=', '--first-parent', sha, '--', row['path'])
                if any(token in line for line in diff.splitlines() if line.startswith('+') and not line.startswith('+++')):
                    added = sha
                    break
            if added:
                message = command('git', 'show', '-s', '--format=%B', added)
                patch = command('git', 'show', '--format=', '--first-parent', added, '--', 'services/*/Dockerfile')
                changes = [line for line in patch.splitlines() if re.match(r'[-+]FROM\s', line)]
                cache[key] = {'added_commit': added, 'added_message': message,
                              'prs': github.commit_prs(added), 'runtime_changes_in_commit': changes}
            else:
                cache[key] = {'added_commit': None, 'prs': [], 'provenance_note': 'addition not resolved'}
        row.update(cache[key])
        if re.search(r'\[skip ci\]|\[ci skip\]|skip-checks:\s*true', row.get('added_message', ''), re.I):
            row['flags'].append('ADDED_WITH_SKIP_CI')


def load_live(directory, src, images):
    warnings, reports = [], {}
    for name, aliases in {'fs-no-ignore': ['fs-no-ignore.json', 'fs-no-ignore-offline.json'],
                          'fs-with-ignore': ['fs-with-ignore.json', 'fs-with-ignore-offline.json'],
                          'report-service': ['report-service.json', 'report-service-offline.json'],
                          'gitleaks-no-ignore': ['gitleaks-no-ignore.json'],
                          'gitleaks-with-ignore': ['gitleaks-with-ignore.json']}.items():
        for alias in aliases:
            path = directory / alias
            if path.exists():
                reports[name] = json.loads(path.read_text())
                break
    metadata_path = directory / 'scan-metadata.json'
    metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
    status_path = directory / 'status.tsv'
    if status_path.exists():
        metadata['exit_statuses'] = dict(line.split('\t') for line in status_path.read_text().splitlines())
    if metadata.get('sha') != src.sha:
        warnings.append(f'Live scans are not attested to target SHA {src.sha}; metadata: {metadata or "missing"}.')
    findings = []
    for name in ['fs-no-ignore', 'report-service']:
        for result in reports.get(name, {}).get('Results', []):
            for vuln in result.get('Vulnerabilities', []):
                findings.append({'scope': name, 'Target': result['Target'], **vuln})
    scanned = set()
    for row in images:
        if row['image'] == 'scratch':
            continue
        path = directory / f"image-{row['key']}.json"
        if path.exists():
            scanned.add(row['image'])
            for result in json.loads(path.read_text()).get('Results', []):
                for vuln in result.get('Vulnerabilities', []):
                    findings.append({'scope': 'image', 'image': row['image'], 'dockerfile': row['dockerfile'],
                                     'Target': result['Target'], **vuln})
        else:
            warnings.append(f"Runtime image not checked: {row['dockerfile']} ({row['image']}).")
    if 'fs-no-ignore' not in reports:
        warnings.append('Root FS live status not checked (no successful no-ignore JSON).')
    for name in ['report-service', 'gitleaks-no-ignore', 'gitleaks-with-ignore', 'fs-with-ignore']:
        if name not in reports:
            warnings.append(f'{name}: not checked (no successful JSON).')
    return reports, findings, metadata, warnings, scanned


def attach_live(rows, reports, findings):
    leaks = {v['Fingerprint'] for v in reports.get('gitleaks-no-ignore', [])}
    for row in rows:
        if row['kind'] == 'trivy':
            row['findings'] = [compact_finding(v) for v in findings if v['VulnerabilityID'] == row['id']]
            if 'fs-no-ignore' in reports:
                row['live'] = bool(row['findings'])
                if not row['findings']:
                    row['live_note'] = 'No observed exact-ID match; runtime/transitive coverage may be incomplete.'
        elif row['kind'] == 'skip-dirs' and 'report-service' in reports:
            row['findings'] = [compact_finding(v) for v in findings if v['scope'] == 'report-service']
            row['live'] = bool(row['findings'])
        elif row['kind'] == 'gitleaks' and 'gitleaks-no-ignore' in reports:
            row['live'] = row['id'] in leaks
            if not row['live']:
                row['flags'].append('STALE_NOT_NEEDED')
        if row['live'] is True:
            row['flags'].append('LIVE')
        severities = [str(v.get('Severity', 'unknown')).lower() for v in row['findings']]
        row['severity'] = min(severities, key=lambda s: SEVERITIES.index(s) if s in SEVERITIES else 4) if severities else 'unknown'


def compact_finding(v):
    fields = ['scope', 'image', 'dockerfile', 'Target', 'VulnerabilityID', 'PkgName',
              'InstalledVersion', 'FixedVersion', 'Severity']
    return {key: v[key] for key in fields if key in v}


def runtime_regressions(rows, directory):
    for row in rows:
        row['runtime_regressions'] = []
        changes = row.get('runtime_changes_in_commit', [])
        previous = [line.split()[1] for line in changes if line.startswith('-FROM ')]
        following = [line.split()[1] for line in changes if line.startswith('+FROM ')]
        for old, new in zip(previous, following):
            name = re.sub(r'[^\w.-]', '-', old)
            path = directory / f'image-{name}.json'
            if not path.exists():
                continue
            old_ids = {v['VulnerabilityID'] for result in json.loads(path.read_text()).get('Results', [])
                       for v in result.get('Vulnerabilities', [])}
            if row['id'] not in old_ids and any(v.get('image') == new for v in row['findings']):
                row['runtime_regressions'].append({'previous_image': old, 'new_image': new,
                                                   'id_absent_in_previous_scan': row['id'],
                                                   'evidence_file': str(path)})


def alert_row(alert, kind, mapping):
    if kind == 'Dependabot':
        advisory = alert.get('security_advisory') or {}
        identifier = advisory.get('cve_id') or advisory.get('ghsa_id') or str(alert['number'])
        controls = controls_for(identifier, mapping, 'dependency')
        severity = advisory.get('severity', 'unknown')
    else:
        rule = alert.get('rule', {})
        identifier = rule.get('id', str(alert['number']))
        cwes = ['CWE-' + number for tag in rule.get('tags', [])
                for number in re.findall(r'cwe[-/](\d+)', tag, re.I)]
        controls = controls_for(identifier, mapping, cwes=cwes)
        severity = rule.get('security_severity_level') or 'unknown'
    return {'kind': kind, 'number': alert['number'], 'id': identifier,
            'state': alert['state'], 'severity': severity, 'controls': controls,
            'url': alert['html_url'], 'created_at': alert['created_at'],
            'fixed_at': alert.get('fixed_at'), 'dismissed_at': alert.get('dismissed_at'),
            'auto_dismissed_at': alert.get('auto_dismissed_at'),
            'dismissed_reason': alert.get('dismissed_reason'),
            'dismissed_comment': alert.get('dismissed_comment'),
            'manifest': alert.get('dependency', {}).get('manifest_path')}


def collect_alerts(github, src, mapping):
    deps = github.api(f'repos/{REPOSITORY}/dependabot/alerts?per_page=100', True, required=True)
    code = []
    for state in ['open', 'fixed', 'dismissed']:
        code += github.api(f'repos/{REPOSITORY}/code-scanning/alerts?per_page=100&ref=refs/heads/main&state={state}', True)
    code = [a for a in code if a.get('tool', {}).get('name', '').lower() == 'codeql']
    alerts = [alert_row(a, 'Dependabot', mapping) for a in deps]
    alerts += [alert_row(a, 'CodeQL', mapping) for a in code]
    closed, dismissed = [], []
    fixed_cache = {}
    for alert in alerts:
        if alert['state'] in ['dismissed', 'auto_dismissed']:
            row = exception(alert['id'], '', 0,
                            'reason: ' + str(alert['dismissed_comment'] or alert['dismissed_reason'] or '')
                            if alert['dismissed_comment'] or alert['dismissed_reason'] else '')
            row.update(kind=alert['kind'] + '-' + alert['state'], controls=alert['controls'],
                       file_url=alert['url'], prs=[], added_commit=None, severity=alert['severity'],
                       live='not checked', alert=alert)
            dismissed.append(row)
            if alert['kind'] == 'CodeQL':
                closed.append({**alert, 'resolution': 'dismissed, not proven fixed', 'prs': []})
        elif alert['state'] == 'fixed':
            prs, sha = [], None
            if alert['manifest'] and alert['fixed_at']:
                key = alert['manifest'], alert['fixed_at']
                if key not in fixed_cache:
                    fixed_cache[key] = command('git', 'log', 'origin/main', '-1', '--format=%H',
                                                '--until=' + alert['fixed_at'], '--', alert['manifest'])
                sha = fixed_cache[key]
                prs = github.commit_prs(sha)
            closed.append({**alert, 'prs': prs, 'fix_candidate_commit': sha,
                           'attribution': 'heuristic: last main commit touching manifest before fixed_at; not proof of fix'})
    return alerts, closed, dismissed


def collect_prs(github, branch, mapping):
    data = github.api(f'repos/{REPOSITORY}/pulls?state=closed&per_page=100&sort=updated&direction=desc', True, required=True)
    rows = []
    for pr in data:
        text = pr['title'] + '\n' + (pr.get('body') or '')
        identifiers = sorted(set(re.findall(FINDING_PATTERN, text, re.I)))
        if pr.get('merged_at') and identifiers:
            rows.append({'kind': 'merged-security-PR', 'number': pr['number'], 'id': ', '.join(identifiers),
                         'title': pr['title'], 'url': pr['html_url'], 'base': pr['base']['ref'],
                         'created_at': pr['created_at'], 'merged_at': pr['merged_at'],
                         'controls': controls_for(text, mapping),
                         'resolution': 'named finding referenced by merged PR; closure not independently proven'})
    return rows


def collect_skip_commits(src, github):
    commits = command('git', 'log', src.sha, '--format=%H', '--regexp-ignore-case',
                      '--grep=\\[skip ci\\]', '--grep=\\[ci skip\\]', '--grep=skip-checks: true').splitlines()
    rows = []
    for sha in commits:
        paths = command('git', 'diff-tree', '--no-commit-id', '--name-only', '-r', '--root', sha).splitlines()
        relevant = [p for p in paths if p.endswith('Dockerfile') or p.endswith('.tf') or p.startswith('security/') or
                    p.startswith('.github/workflows/') or 'ignore' in Path(p).name or
                    p in ['security/dast/baseline.json', 'security/deps/modules.yaml']]
        if not relevant:
            continue
        patch = command('git', 'show', '--format=', sha, '--', *relevant)
        changes = [line for line in patch.splitlines() if line.startswith(('+', '-')) and
                   not line.startswith(('+++', '---')) and re.search(
                       r'FROM\s|publicly_accessible|storage_encrypted|CVE-|GHSA-|skip-dirs|'
                       r'ignorefile|nosemgrep|exp:|branches:|continue-on-error', line)]
        rows.append({'sha': sha, 'url': f'{WEB}/commit/{sha}',
                     'message': command('git', 'show', '-s', '--format=%s', sha),
                     'date': command('git', 'show', '-s', '--format=%cI', sha),
                     'paths': relevant, 'changes': changes, 'prs': github.commit_prs(sha)})
    return rows


def timestamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def stats(values):
    values = sorted(values)
    return {'n': len(values), 'median_days': round(statistics.median(values), 2) if values else None,
            'p90_days': round(values[math.ceil(len(values) * .9) - 1], 2) if values else None,
            'max_days': round(max(values), 2) if values else None}


def metrics(alerts, prs, mapping, now):
    result, slow = [], []
    for severity in SEVERITIES:
        selected = [a for a in alerts if a['kind'] == 'Dependabot' and a['severity'] == severity]
        fixed = [(timestamp(a['fixed_at']) - timestamp(a['created_at'])).total_seconds() / 86400
                 for a in selected if a['state'] == 'fixed' and a['fixed_at']]
        ages = [(now - timestamp(a['created_at'])).total_seconds() / 86400
                for a in selected if a['state'] == 'open']
        sla = mapping['remediation_sla_days'].get(severity)
        result.append({'severity': severity, 'fixed': stats(fixed), 'open': stats(ages), 'sla_days': sla,
                       'past_sla': sum(age > sla for age in ages) if sla else None})
        if ages and sla and max(ages) > sla:
            slow.append(f"{severity}: {sum(age > sla for age in ages)}/{len(ages)} open past the assumed "
                        f"{sla}-day SLA (median age {statistics.median(ages):.1f} days; oldest {max(ages):.1f}).")
    code_open = [{**a, 'age_days': round((now - timestamp(a['created_at'])).total_seconds() / 86400, 2)}
                 for a in alerts if a['kind'] == 'CodeQL' and a['state'] == 'open']
    code_summary = [{'severity': s, **stats([a['age_days'] for a in code_open if a['severity'] == s])}
                    for s in SEVERITIES]
    durations = [(timestamp(p['merged_at']) - timestamp(p['created_at'])).total_seconds() / 86400 for p in prs]
    return {'dependabot': result, 'codeql_open': code_open, 'codeql_summary': code_summary,
            'merged_security_pr_open_to_merge': stats(durations),
            'where_slow': ' '.join(slow) or 'No observed open Dependabot age exceeds the assumed SLAs.',
            'earliest_alert_date': min((a['created_at'] for a in alerts), default=None)}


def priority(row):
    flags = row['flags']
    lead = row['live'] is True and ('NO_REASON' in flags or 'NO_REVISIT_DATE' in flags)
    both = 'NO_REASON' in flags and 'NO_REVISIT_DATE' in flags
    return (not lead, not both, SEVERITIES.index(row.get('severity', 'unknown')),
            'ADDED_WITH_SKIP_CI' not in flags, row['id'], row['path'], row['line'])


def coverage(catalog, exceptions, closed, gates):
    rows = []
    for control in catalog:
        identifier = control['id']
        findings = [f for f in closed if identifier in f['controls']]
        items = [e for e in exceptions if identifier in e['controls']]
        mapped_gates = [g for g in gates if identifier in g['controls']]
        links = sorted({f.get('url') or f.get('file_url') for f in [*findings, *items]
                        if f.get('url') or f.get('file_url')})
        active = [g for g in mapped_gates if not g.get('scope') and
                  any(not v.startswith('no ') for v in g['events'].values())]
        rows.append({'control': identifier, 'text': control['text'], 'closed_count': len(findings),
                     'exception_count': len(items), 'flagged_count': sum(bool(e['flags']) for e in items),
                     'gates': [g['job'] for g in mapped_gates], 'branch_eligible_gates': [g['job'] for g in active],
                     'evidence_links': links,
                     'gaps': ([] if active else ['NO_BRANCH_ELIGIBLE_GATE']) +
                             ([] if links else ['NO_FINDING_OR_EXCEPTION_EVIDENCE'])})
    return rows


def md_table(headers, rows):
    def escape(value):
        return str(value if value is not None else '—').replace('|', '\\|').replace('\n', '<br>').replace('\r', '')
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(escape(v) for v in row) + ' |' for row in rows])


def pr_links(row):
    return ', '.join(f"[#{p['number']}]({p['url']})" for p in row.get('prs', [])) or 'No PR resolved'


def finding_detail(row):
    return '; '.join(f"{v.get('image', v['Target'])}: {v['VulnerabilityID']} "
                     f"{v['PkgName']} {v['InstalledVersion']} → {v.get('FixedVersion') or 'no fix listed'} "
                     f"({v['Severity']})" for v in row['findings'])


def render(pack):
    exceptions = pack['exceptions']
    flagged = sorted([e for e in exceptions if e['flags']], key=priority)
    lines = ['# CISO auditor evidence pack', '', '## Exceptions needing action', '',
             f"Target `{pack['branch']}` at `{pack['sha']}`. Generated {pack['generated_at']}.", '',
             '**LIVE means scanner-observed presence, not exploitability. Not checked is not clean.**', '']
    if flagged:
        first = flagged[0]
        lines += [f"**Lead: {first['id']}** — {', '.join(first['flags'])}. "
                  f"[Source]({first['file_url']}); {pr_links(first)}.",
                  finding_detail(first),
                  'Runtime changes in adding commit: ' + '; '.join(first.get('runtime_changes_in_commit', [])), '']
        if first.get('section_claim'):
            lines += ['**Header claim:** ' + first['section_claim'], '']
        for regression in first.get('runtime_regressions', []):
            lines += [f"**Runtime regression:** {first['id']} was absent in the available "
                      f"`{regression['previous_image']}` scan and is present in "
                      f"`{regression['new_image']}` after the adding commit's base-image change.", '']
    lines.append(md_table(['Exception / evidence', 'Control', 'Live', 'Flags', 'Added by PR'],
                          [[f"[{e['id']}]({e['file_url']})", ', '.join(e['controls']) or 'non-security',
                            e['live'], ', '.join(e['flags']), pr_links(e)] for e in flagged]))
    lines += ['', '## Sources, scope and assumptions', '',
              'Dependabot and CodeQL track the **default branch (main)**, not demo-ciso. '
              'PR metrics cover all merged PRs whose title/body references a named security finding; '
              'this is not independent proof each finding was closed. Counts are evidence records, not deduplicated vulnerabilities.',
              f"Data window: earliest alert {pack['metrics']['earliest_alert_date']} through {pack['generated_at']}.",
              f"GitHub API fetch/cache timestamps: {min(s['fetched_at'] for s in pack['github_sources'])} "
              f"to {max(s['fetched_at'] for s in pack['github_sources'])}; endpoint inventory is in JSON.",
              pack['sla_assumption'],
              'Percentile convention: nearest-rank p90; all durations are elapsed UTC days. '
              'Missing/restricted API data is reported, never interpreted as zero evidence.',
              'Reason detection is a transparent text heuristic; dates are entry-local or inherited section dates, '
              'not inherited from a preceding entry. Mapping is curated but **requires human sign-off**. '
              'This generator cannot certify a human review.',
              f"Live scan metadata: `{json.dumps(pack['live_metadata'], sort_keys=True)}`.",
              *['- ' + warning for warning in pack['warnings']], '',
              '## Exception register', '',
              'ID globbing in .trivyignore is ineffective (Trivy 0.71.0 matches exact IDs). '
              'A Q4 comment is not a revisit date. Raw inline comments are evidence, not an endorsement.', '']
    lines.append(md_table(['Kind / ID', 'Location at target SHA', 'Controls', 'Reason?', 'Comment block',
                           'Revisit', 'Live / severity', 'Findings', 'Flags', 'Added commit / PR'],
                          [[e['kind'] + ': ' + e['id'], f"[{e['path'] or 'GitHub alert'}:{e['line']}]({e['file_url']})",
                            ', '.join(e['controls']) or 'non-security', e['has_reason'], e['comment_block'],
                            e['revisit_date'], f"{e['live']} / {e.get('severity', 'unknown')}", finding_detail(e),
                            ', '.join(e['flags']),
                            (f"[{e['added_commit'][:10]}]({WEB}/commit/{e['added_commit']}) "
                             if e.get('added_commit') else '') + pr_links(e)] for e in exceptions]))
    lines += ['', '### Catalog coverage gaps', '',
              md_table(['Exception', 'Evidence'], [[e['id'], e['file_url']] for e in exceptions
                                                  if 'OUT-OF-CATALOG' in e['controls']]), '',
              '## Closed findings / merged named-finding PRs', '',
              'Fixing PR attribution for Dependabot is **heuristic**: last commit on main touching '
              'the manifest before fixed_at, then GitHub commit→PR association. Dismissed is not fixed.', '',
              md_table(['Source / ID', 'State / resolution', 'Controls', 'Evidence', 'Fix candidate PR'],
                       [[c['kind'] + ': ' + c['id'], c.get('resolution', c.get('state', 'merged')),
                         ', '.join(c['controls']), f"[record]({c['url']})", pr_links(c)] for c in pack['closed_findings']]),
              '', '## Gates', '',
              'Static YAML analysis, not observed workflow runs or branch-protection proof. '
              'PR branches filters refer to the base branch; paths filters refer to changed files. '
              'Conditional jobs and shell error-handling signals require review.', '',
              md_table(['Workflow / job', 'Enforces / controls', 'Push to target', 'PR to target',
                         'Triggers (branches/paths)', 'Blocking or informational', 'Signals'],
                       [[f"[{g['workflow']} / {g['job']}]({g['url']})", g['enforces'] + ' / ' + ', '.join(g['controls']),
                         g['events']['push'], g['events']['pull_request'], json.dumps(g['triggers']),
                         g['enforcement'], json.dumps(g['signals'])] for g in pack['gates']]),
              '', '### Security-relevant commits carrying CI-skip markers', '',
              md_table(['Commit / PR', 'Message', 'Security paths', 'Changed lines'],
                       [[f"[{c['sha'][:10]}]({c['url']}) / {pr_links(c)}", c['message'], ', '.join(c['paths']),
                         '\n'.join(c['changes'])] for c in pack['skip_ci_commits']]), '',
              '## Control coverage matrix', '',
              md_table(['Control', 'Closed records', 'Exceptions (flagged)', 'Mapped gates',
                         'Branch-eligible gates', 'Evidence', 'Gaps'],
                       [[c['control'], c['closed_count'], f"{c['exception_count']} ({c['flagged_count']})",
                         ', '.join(c['gates']), ', '.join(c['branch_eligible_gates']),
                         ', '.join(f'[evidence {i}]({link})' for i, link in enumerate(c['evidence_links'], 1)),
                         ', '.join(c['gaps'])] for c in pack['coverage']]), '',
              '## Remediation time per severity', '',
              md_table(['Severity', 'Fixed n', 'Median days', 'p90 days', 'Max days', 'Open n',
                         'Median age days', 'Oldest days', 'SLA days (assumed)', 'Open past SLA'],
                       [[r['severity'], r['fixed']['n'], r['fixed']['median_days'], r['fixed']['p90_days'],
                         r['fixed']['max_days'], r['open']['n'], r['open']['median_days'], r['open']['max_days'],
                         r['sla_days'], r['past_sla']] for r in pack['metrics']['dependabot']]), '',
              '**Where we are slow:** ' + pack['metrics']['where_slow'], '',
              '### Open CodeQL alerts (default branch)', '',
              md_table(['Severity', 'Count', 'Median age days', 'Oldest days'],
                       [[r['severity'], r['n'], r['median_days'], r['max_days']]
                        for r in pack['metrics']['codeql_summary']]), '',
              md_table(['Alert', 'Severity', 'Age days', 'Controls'],
                       [[f"[{r['id']}]({r['url']})", r['severity'], r['age_days'], ', '.join(r['controls'])]
                        for r in pack['metrics']['codeql_open']]), '',
              '### Merged security PR open→merge time (all bases)', '',
              md_table(['n', 'Median days', 'p90 days', 'Max days'],
                       [[pack['metrics']['merged_security_pr_open_to_merge'][key]
                         for key in ['n', 'median_days', 'p90_days', 'max_days']]])]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--branch', default='demo-ciso')
    parser.add_argument('--live-dir', type=Path, default=ROOT / 'compliance/evidence/out')
    parser.add_argument('--out', type=Path, default=ROOT / 'compliance/evidence/evidence-pack.md')
    parser.add_argument('--json', type=Path, default=ROOT / 'compliance/evidence/evidence-pack.json')
    parser.add_argument('--refresh', action='store_true', help='Refresh cached GitHub API data')
    parser.add_argument('--runtime-images', action='store_true', help='Print final-stage images from working tree only')
    args = parser.parse_args()
    if args.runtime_images:
        print(json.dumps(runtime_images([(str(p.relative_to(ROOT)), p.read_text())
                                        for p in sorted(ROOT.glob('services/*/Dockerfile'))]), indent=2))
        return
    if command('git', 'rev-parse', '--is-shallow-repository') == 'true':
        raise SystemExit('Full Git history required; run git fetch --unshallow first.')
    src = GitSource(args.branch)
    mapping = yaml.safe_load((Path(__file__).with_name('control-map.yaml')).read_text())
    spec = importlib.util.spec_from_file_location('catalog', ROOT / 'compliance/control-catalogs/validate_catalog.py')
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    catalog = validator.validate_catalog(yaml.safe_load(src.read('compliance/control-catalogs/secure-software-controls.yaml')))
    github = GitHub(args.live_dir / 'github-cache', args.refresh)
    rows = collect_exceptions(src, mapping)
    add_provenance(rows, src, github)
    images = runtime_images([(p, src.read(p)) for p in src.files if re.fullmatch(r'services/[^/]+/Dockerfile', p)])
    reports, findings, metadata, warnings, _ = load_live(args.live_dir, src, images)
    attach_live(rows, reports, findings)
    runtime_regressions(rows, args.live_dir)
    alerts, closed, dismissed = collect_alerts(github, src, mapping)
    rows += dismissed
    prs = collect_prs(github, args.branch, mapping)
    closed += prs
    gates = []
    for entry in mapping['gates']:
        gates.append({**entry, **parse_workflow(src.read(entry['workflow']), entry['job'], args.branch, entry.get('step')),
                      'url': src.link(entry['workflow'])})
    now = datetime.now(timezone.utc)
    pack = {'branch': args.branch, 'sha': src.sha, 'generated_at': now.isoformat(),
            'repository': REPOSITORY, 'default_branch': 'main', 'live_metadata': metadata,
            'mapping_review_status': mapping['review_status'],
            'exceptions': sorted(rows, key=priority), 'closed_findings': closed, 'gates': gates,
            'skip_ci_commits': collect_skip_commits(src, github), 'runtime_images': images,
            'metrics': metrics(alerts, prs, mapping, now), 'alerts': alerts,
            'sla_assumption': mapping['remediation_sla_days']['assumption'],
            'github_sources': github.sources,
            'warnings': warnings + github.errors}
    pack['coverage'] = coverage(catalog, rows, closed, gates)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(pack))
    args.json.write_text(json.dumps(pack, indent=2) + '\n')
    print(f"Wrote {args.out} and {args.json}: {len(rows)} exceptions, {len(closed)} closed/merged records, {len(gates)} gates.")
    for warning in pack['warnings']:
        print('WARNING: ' + warning)


if __name__ == '__main__':
    main()
