"""Unattended weekly evidence collection; failures remain explicit evidence."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
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
              'Logs: live_check.log, deps-inventory.log, deps-gate.log, sonar-*.log, build-pack.log.',
              'Status: [weekly-status.json](weekly-status.json).']
    for key in ['discovery_error', 'collection_error']:
        if status['wide_scan'].get(key):
            lines.append(f"Wide scan limitation: {status['wide_scan'][key]}")
    return '\n'.join(lines[:40]) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--branch', default='demo-ciso', help='Remote workflow ref and gate target branch')
    parser.add_argument('--out', type=Path, default=ROOT / 'compliance/evidence/out')
    args = parser.parse_args()
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    for path in [args.out / 'weekly-status.json', args.out / 'advisory/inventory.json', args.out / 'advisory/gate.json']:
        path.unlink(missing_ok=True)
    os.environ['PATH'] = str(Path.home() / 'bin') + ':' + str(Path.home() / '.local/bin') + ':' + os.environ['PATH']
    previous = subprocess.run(['git', 'show', 'HEAD:compliance/evidence/evidence-pack.json'],
                              cwd=ROOT, text=True, capture_output=True)
    baseline = json.loads(previous.stdout) if previous.returncode == 0 else {}
    status = {'branch': args.branch, 'sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()}
    status['live_check'] = run_step('live_check', ['bash', 'compliance/evidence/live_check.sh', str(args.out)], args.out, 3600)
    status['deps_inventory'] = run_step('deps-inventory', ['make', 'deps-inventory'], args.out)
    status['deps_gate'] = run_step('deps-gate', ['make', 'deps-gate'], args.out)
    destination = args.out / 'advisory'
    destination.mkdir(exist_ok=True)
    for name in ['inventory.json', 'gate.json']:
        path = ROOT / 'security/deps/reports' / name
        if path.exists() and path.stat().st_mtime >= datetime.fromisoformat(status['deps_inventory']['started_at']).timestamp():
            shutil.copyfile(path, destination / name)
    status['wide_scan'] = wide_scan(args.branch, args.out)
    status_path = args.out / 'weekly-status.json'
    status_path.write_text(json.dumps(status, indent=2) + '\n')
    status['build_pack'] = run_step('build-pack', ['python3', 'compliance/evidence/build_evidence_pack.py',
                                                '--branch', args.branch, '--source-ref', 'HEAD',
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
