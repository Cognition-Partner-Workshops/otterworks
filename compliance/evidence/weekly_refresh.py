"""Unattended weekly evidence collection; failures remain explicit evidence."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import shlex
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from xml.sax.saxutils import escape
from datetime import datetime, timezone

from build_evidence_pack import REPOSITORY, ROOT, repo_actions


def run_step(name, args, out, timeout=900):
    log = out / f'{name}.log'
    started = datetime.now(timezone.utc).isoformat()
    with log.open('w') as handle:
        try:
            code = subprocess.run(args, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT,
                                  timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            code = 124
            handle.write(f'\nTimed out after {timeout} seconds.\n')
        except OSError as exc:
            code = 127
            handle.write(str(exc) + '\n')
    print(f'{name}: exit {code}; {log}', flush=True)
    return {'exit_code': code, 'log': str(log.relative_to(ROOT)), 'started_at': started}


def gh_json(args):
    result = subprocess.run(['gh', *args], cwd=ROOT, text=True, capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return json.loads(result.stdout)


def configure_mirror(out):
    mirror = os.environ.get('MAVEN_MIRROR_URL')
    if not mirror:
        return
    if not mirror.startswith('https://'):
        raise ValueError('MAVEN_MIRROR_URL must use HTTPS')
    directory = out / 'toolchain'
    directory.mkdir(exist_ok=True)
    settings = directory / 'settings.xml'
    settings.write_text('<settings><mirrors><mirror><id>weekly</id><mirrorOf>central</mirrorOf>'
                        f'<url>{escape(mirror)}</url></mirror></mirrors></settings>')
    executable = shutil.which('mvn', path=os.pathsep.join(
        p for p in os.environ['PATH'].split(os.pathsep) if p != str(directory)))
    if not executable:
        raise RuntimeError('Maven provisioning did not provide mvn')
    shim = directory / 'mvn'
    shim.write_text(f'#!/bin/sh\nexec {shlex.quote(executable)} -s {shlex.quote(str(settings))} "$@"\n')
    shim.chmod(0o700)
    os.environ['MAVEN_ARGS'] = '-s ' + shlex.quote(str(settings))
    os.environ['PATH'] = str(directory) + ':' + os.environ['PATH']
    gradle = directory / 'gradle-home'
    init = gradle / 'init.d'
    init.mkdir(parents=True, exist_ok=True)
    (init / 'mirror.gradle').write_text('allprojects { repositories.all { repo ->\n'
                                      'if (repo instanceof org.gradle.api.artifacts.repositories.MavenArtifactRepository '
                                      '&& repo.url.host in ["repo.maven.apache.org", "repo1.maven.org"]) '
                                      f'{{ repo.setUrl({json.dumps(mirror)}) }}\n' + '} }\n')
    os.environ['GRADLE_USER_HOME'] = str(gradle)


def central_block():
    base = os.environ.get('MAVEN_MIRROR_URL', 'https://repo.maven.apache.org/maven2')
    try:
        with urlopen(base.rstrip('/') + '/org/apache/commons/commons-text/1.9/commons-text-1.9.pom', timeout=30):
            return None
    except HTTPError as exc:
        return 'Maven repository HTTP 429 (rate limited)' if exc.code == 429 else None
    except (URLError, TimeoutError):
        return None


def dependency_ci(branch):
    fields = 'databaseId,conclusion,url,headSha,headBranch,event,createdAt'
    args = ['run', 'list', '-R', REPOSITORY, '-w', 'deps-remediation.yml', '--status', 'completed',
            '--limit', '100', '--json', fields]
    runs = gh_json([*args, '--branch', branch])
    if not runs:
        prs = gh_json(['api', f'repos/{REPOSITORY}/pulls?state=all&base={branch}&sort=created&direction=desc&per_page=1'])
        if prs:
            pr = prs[0]
            candidates = gh_json([*args, '--branch', pr['head']['ref']])
            for run in candidates:
                associations = gh_json(['api', f'repos/{REPOSITORY}/actions/runs/{run["databaseId"]}'])
                if any(p['number'] == pr['number'] for p in associations.get('pull_requests', [])):
                    runs.append(run)
    return max(runs, key=lambda r: r['createdAt']) if runs else None


def advisory_steps(status, out, branch):
    configure_mirror(out)
    blocked = None
    for attempt in range(3):
        if attempt:
            time.sleep([120, 300][attempt - 1])
        blocked = central_block()
        for key, target in [('deps_inventory', 'deps-inventory'), ('deps_gate', 'deps-gate')]:
            if blocked:
                print(f'{target}: attempt {attempt + 1}/3 blocked: {blocked}', flush=True)
                log = out / f'{target}-attempt-{attempt + 1}.log'
                log.write_text(blocked + '\nPreflight blocked; make was not invoked.\n')
                step = {'exit_code': 75, 'log': str(log.relative_to(ROOT)),
                        'started_at': datetime.now(timezone.utc).isoformat(), 'blocked_reason': blocked}
            else:
                step = run_step(f'{target}-attempt-{attempt + 1}', ['make', target], out)
            status.setdefault(key, {'attempts': []})['attempts'].append(step)
            status[key].update(step)
            report = ROOT / 'security/deps/reports' / ('inventory.json' if key == 'deps_inventory' else 'gate.json')
            if not blocked and report.exists() and report.stat().st_mtime >= datetime.fromisoformat(step['started_at']).timestamp():
                destination = out / 'advisory'
                destination.mkdir(exist_ok=True)
                shutil.copyfile(report, destination / report.name)
        evidence = '\n'.join((ROOT / status[k]['log']).read_text() for k in ['deps_inventory', 'deps_gate'])
        for name in ['inventory.json', 'gate.json']:
            path = out / 'advisory' / name
            if path.exists():
                evidence += path.read_text()
        if '429' not in evidence:
            break
        blocked = 'Maven repository HTTP 429 (rate limited)'
    if blocked:
        status['advisory_blocked_reason'] = blocked
        try:
            status['advisory_ci'] = dependency_ci(branch)
        except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
            status['advisory_ci_error'] = str(exc)


def wide_scan(branch, out):
    result = {'controls_source': 'cluster CWE → control-map.yaml', 'branch': branch}
    listing = ['run', 'list', '-R', REPOSITORY, '--workflow', 'sonarqube-banking.yml',
               '--branch', branch, '--event', 'workflow_dispatch', '--limit', '20',
               '--json', 'databaseId,url,createdAt']
    try:
        previous = {r['databaseId'] for r in gh_json(listing)}
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        result['discovery_error'] = str(exc)
        previous = None
    result['dispatch'] = run_step('sonar-dispatch', ['gh', 'workflow', 'run', 'sonarqube-banking.yml',
                                                  '-R', REPOSITORY, '--ref', branch], out)
    if result['dispatch']['exit_code'] or previous is None:
        return result
    deadline = time.monotonic() + 5400
    discovery_deadline = time.monotonic() + 120
    try:
        while time.monotonic() < discovery_deadline:
            candidates = [r for r in gh_json(listing) if r['databaseId'] not in previous]
            if len(candidates) > 1:
                result['discovery_error'] = 'Concurrent dispatches: refusing ambiguous run attribution.'
                return result
            if candidates:
                result.update(run_id=candidates[0]['databaseId'], run_url=candidates[0]['url'])
                break
            time.sleep(5)
        if 'run_id' not in result:
            result['discovery_error'] = 'No new workflow_dispatch run appeared within 120 seconds.'
            return result
        result['watch'] = run_step('sonar-watch', ['gh', 'run', 'watch', str(result['run_id']),
                                                 '-R', REPOSITORY, '--exit-status', '--interval', '20', '--compact'],
                                   out, max(1, deadline - time.monotonic()))
        result['run'] = gh_json(['run', 'view', str(result['run_id']), '-R', REPOSITORY,
                                 '--json', 'status,conclusion,url'])
        destination = out / 'wide-scan'
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir()
        result['download'] = run_step('sonar-download', ['gh', 'run', 'download', str(result['run_id']),
                                                       '-R', REPOSITORY, '--name', 'sonarqube-banking',
                                                       '--dir', str(destination)], out, 120)
        artifacts = gh_json(['api', f'repos/{REPOSITORY}/actions/runs/{result["run_id"]}/artifacts'])
        result['artifact_urls'] = [result['run_url'] + '/artifacts/' + str(a['id'])
                                   for a in artifacts.get('artifacts', []) if a['name'] == 'sonarqube-banking']
        result['clusters_json'] = str((destination / 'clusters.json').relative_to(ROOT))
        result['clusters_markdown'] = str((destination / 'clusters.md').relative_to(ROOT))
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
        result['collection_error'] = str(exc)
    return result


def summary(pack, status, baseline):
    actions = repo_actions(pack['exceptions'])
    lead = actions[0] if actions else None
    def identity(entry):
        return entry['kind'], entry['path'], entry['line'], entry['id'], entry.get('alert', {}).get('number')

    before = {identity(e) for e in baseline.get('exceptions', []) if e['flags']}
    after = {identity(e) for e in pack['exceptions'] if e['flags']}
    critical = next(r for r in pack['metrics']['dependabot'] if r['severity'] == 'critical')
    sonar = pack['wide_scan']
    lines = ['# Weekly CISO evidence summary', '',
             f"Snapshot: `{pack['sha']}`; target `{pack['branch']}`; {pack['generated_at']}.",
             f"Lead exception: **{lead['id']}** — {', '.join(lead['flags'])}." if lead else 'Lead exception: none.',
             f"Flagged exceptions: {len(after)}; new identities vs last committed pack: "
             + (str(len(after - before)) if baseline else 'not computable') + '.',
             f"Live check: exit {status['live_check']['exit_code']} (scanner-level codes in out/status.tsv).",
             f"Advisory inventory: exit {status['deps_inventory']['exit_code']}; "
             f"gate: exit {status['deps_gate']['exit_code']} — {pack['advisory_exposure']['verdict']} (SSC-11).",
             f"Wide scan dispatch: exit {status['wide_scan']['dispatch']['exit_code']}; "
             f"watch: {status['wide_scan'].get('watch', {}).get('exit_code', 'not run')}; "
             f"artifact download: {status['wide_scan'].get('download', {}).get('exit_code', 'not run')}.",
             f"Run: {sonar.get('run_url', 'not available')}",
             'Artifacts: ' + ', '.join(sonar.get('artifact_urls', [])),
             'Top wide-scan clusters:']
    for cluster in sorted(sonar.get('clusters', []), key=lambda c: -c.get('count', 0))[:5]:
        lines.append(f"- {cluster['cluster']}: {cluster['count']} findings; "
                     f"{', '.join(cluster.get('cwes', []))}; {', '.join(cluster['controls'])}.")
    if not sonar.get('clusters'):
        lines.append('- Not measured / no downloaded clusters; inspect dispatch/watch/download logs.')
    lines += [f"Remediation: {critical['past_sla']}/{critical['open']['n']} open criticals past assumed "
              f"{critical['sla_days']}-day SLA; median age {critical['open']['median_days']} days.",
              'Pack: [Markdown](../evidence-pack.md) · [JSON](../evidence-pack.json).',
              'Logs: live_check.log, deps-*-attempt-*.log, sonar-*.log, build-pack.log.',
              'Status: [weekly-status.json](weekly-status.json).']
    for key in ['discovery_error', 'collection_error']:
        if status['wide_scan'].get(key):
            lines.append(f"Wide scan limitation: {status['wide_scan'][key]}")
    return '\n'.join(lines[:40]) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--branch', default='demo-ciso', help='Remote workflow ref and gate target branch')
    parser.add_argument('--out', type=Path, default=ROOT / 'compliance/evidence/out')
    parser.add_argument('--deps-only', action='store_true', help='Reuse recorded scans and Sonar evidence')
    args = parser.parse_args()
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    status_path = args.out / 'weekly-status.json'
    retained = json.loads(status_path.read_text()) if args.deps_only and status_path.exists() else {}
    if args.deps_only and not retained:
        parser.error('--deps-only requires a previous weekly-status.json')
    for path in [args.out / 'advisory/inventory.json', args.out / 'advisory/gate.json']:
        path.unlink(missing_ok=True)
    os.environ['PATH'] = str(Path.home() / 'bin') + ':' + str(Path.home() / '.local/bin') + ':' + os.environ['PATH']
    previous = subprocess.run(['git', 'show', 'HEAD:compliance/evidence/evidence-pack.json'],
                              cwd=ROOT, text=True, capture_output=True)
    baseline = json.loads(previous.stdout) if previous.returncode == 0 else {}
    status = retained or {'branch': args.branch, 'sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()}
    for key in ['deps_inventory', 'deps_gate', 'advisory_ci', 'advisory_ci_error', 'advisory_blocked_reason']:
        status.pop(key, None)
    if not args.deps_only:
        status['live_check'] = run_step('live_check', ['bash', 'compliance/evidence/live_check.sh', str(args.out)], args.out, 3600)
    advisory_steps(status, args.out, args.branch)
    if not args.deps_only:
        status['wide_scan'] = wide_scan(args.branch, args.out)
    status_path = args.out / 'weekly-status.json'
    status_path.write_text(json.dumps(status, indent=2) + '\n')
    status['build_pack'] = run_step('build-pack', ['python3', 'compliance/evidence/build_evidence_pack.py',
                                                '--branch', args.branch, '--source-ref', status['sha'],
                                                '--live-dir', str(args.out), '--refresh'], args.out, 900)
    status_path.write_text(json.dumps(status, indent=2) + '\n')
    if status['build_pack']['exit_code']:
        (args.out / 'weekly-summary.md').write_text('# Weekly evidence collection failed\n\nSee weekly-status.json and build-pack.log.\n')
        raise SystemExit(status['build_pack']['exit_code'])
    pack = json.loads((ROOT / 'compliance/evidence/evidence-pack.json').read_text())
    (args.out / 'weekly-summary.md').write_text(summary(pack, status, baseline))
    print((args.out / 'weekly-summary.md').read_text())


if __name__ == '__main__':
    main()
