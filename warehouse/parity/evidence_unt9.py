"""UNT-9 evidence: wf_SFX_AUDIT_DAILY PowerCenter oracle, two dbt workflow replays, one Task DAG run."""
import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

from .evidence import BOOTSTRAP, ESTATE, OUT, cell, dump, full_compare, sha, snapshot
from .evidence_unt3 import load
from .inventory import ROOT

DEST = OUT / 'unt9'
ACCEPTED = Path(os.environ.get('UNT9_ACCEPTED_ORACLE', Path.home() / 'unt9/ev/unt2p2/out/evidence'))
MANIFEST = Path(os.environ.get('UNT9_MANIFEST', Path.home() / 'attachments/1c299b4d-6dde-4108-8946-1d68e128b511/manifest.json'))
SCHEMA = 'PC_FX_UNT9_AUDIT_WF'
FQ_SCHEMA = 'SFX_D1110_AFTER.' + SCHEMA
LANDING = ('AUDIT_EVENT', 'SECURITY_ALERT')
# Enabled wf_SFX_AUDIT_DAILY sessions: mapping, PostgreSQL target, Snowflake table, business key.
TARGETS = {
    's_m_SFX_STG_AUDIT_EVENT': ('m_SFX_STG_AUDIT_EVENT', 'sfx_audit.stg_audit_event', 'STG_AUDIT_EVENT', ['EVENT_ID']),
    's_m_SFX_AUDIT_EVENT': ('m_SFX_AUDIT_EVENT', 'sfx_audit.audit_event', 'AUDIT_EVENT', ['EVENT_ID']),
    's_m_SFX_AUDIT_DAILY_SUMMARY': ('m_SFX_AUDIT_DAILY_SUMMARY', 'sfx_audit.audit_daily_summary', 'AUDIT_DAILY_SUMMARY',
                                    ['SUMMARY_ID']),
    's_m_SFX_SECURITY_ALERT': ('m_SFX_SECURITY_ALERT', 'sfx_audit.security_alert', 'SECURITY_ALERT', ['ALERT_ID']),
}
ARCHIVE_PG = 'sfx_audit.audit_event_archive'


def binding():
    dirty = subprocess.check_output(['git', 'status', '--porcelain', '--', 'warehouse', 'etl/informatica'],
                                    cwd=ROOT, text=True)
    if dirty:
        raise ValueError('Refusing execution with a dirty tree')
    paths = subprocess.check_output(['git', 'ls-files', 'warehouse', 'etl/informatica'], cwd=ROOT, text=True).splitlines()
    return {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'sha256': {p: sha(ROOT / p) for p in paths if (ROOT / p).is_file()}}


def fresh(path):
    if path.exists():
        raise ValueError('Refusing to overwrite evidence: ' + str(path))
    path.mkdir(parents=True)
    dump(path / 'implementation.json', binding())


def utc():
    return datetime.now(timezone.utc).isoformat()


def frozen_inputs():
    manifest = json.loads(MANIFEST.read_text())
    files = {Path(f['path']).parent.name: f for f in manifest['landing'] if Path(f['path']).parts[-3] == 'audit'}
    checks = {'bootstrap': manifest['bootstrap_sha256'] == sha(BOOTSTRAP),
              'parameter_file': manifest['parameter_file']['sha256'] == sha(Path(manifest['parameter_file']['path'])),
              'runner_commit_unchanged': not subprocess.run(
                  ['git', 'diff', '--quiet', manifest['runner_git_commit'], 'HEAD', '--', 'etl/informatica'],
                  cwd=ROOT).returncode}
    for name in LANDING:
        path = ESTATE / 'tests/fixture/landing/audit' / name / '20261109.psv'
        checks[name] = files[name]['sha256'] == sha(path) and \
            files[name]['row_count'] == len(path.read_text().splitlines()) - 1
    if not all(checks.values()):
        raise ValueError('Frozen input manifest mismatch: ' + json.dumps(checks))
    return {'manifest_sha256': sha(MANIFEST), 'business_date': manifest['business_date'], 'checks': checks,
            'initial_tables': {k: len(v['rows']) for k, v in manifest['initial_tables'].items() if k.startswith('SFX_AUDIT.')}}


def sessions(root, run_id=None):
    with (root / 'REP_SESS_LOG.psv').open() as stream:
        rows = [r for r in csv.DictReader(stream, delimiter='|') if r['WORKFLOW_NAME'] == 'wf_SFX_AUDIT_DAILY']
    last = run_id or max(r['WORKFLOW_RUN_ID'] for r in rows)
    return [r for r in rows if r['WORKFLOW_RUN_ID'] == last]


def oracle():
    """Run the PowerCenter emulator's wf_SFX_AUDIT_DAILY twice on a fresh PostgreSQL database."""
    import psycopg
    path = DEST / 'oracle'
    fresh(path)
    dump(path / 'frozen_inputs.json', frozen_inputs())
    db = 'unt9_wf_' + uuid.uuid4().hex[:12]
    params = dict(host='127.0.0.1', port=int(os.environ.get('UNT9_PG_PORT', '56042')), user='postgres')
    root = (path / db).resolve()
    for name in LANDING:
        staged = root / 'landing/audit' / name
        staged.mkdir(parents=True)
        shutil.copy2(ESTATE / 'tests/fixture/landing/audit' / name / '20261109.psv', staged / '20261109.psv')
    command = [sys.executable, '-m', 'runner', 'startworkflow', '-f', 'SFX_AUDIT', 'wf_SFX_AUDIT_DAILY']
    env = {k: v for k, v in os.environ.items() if not k.startswith(('SNOWFLAKE_', 'TD_'))}
    env.update(TD_HOST=params['host'], TD_PORT=str(params['port']), TD_USER='postgres', TD_PASSWORD='',
               TD_DB=db, PMROOTDIR=str(root), LANDING_DIR=str(root / 'landing'))
    with psycopg.connect(dbname='postgres', autocommit=True, **params) as admin:
        admin.execute('CREATE DATABASE ' + db)
    with psycopg.connect(dbname=db, autocommit=True, **params) as pg:
        pg.execute(BOOTSTRAP.read_text())
        initial = {s: snapshot(pg, t[1]) for s, t in TARGETS.items()}
        initial['archive'] = snapshot(pg, ARCHIVE_PG)
        dump(path / 'initial_targets.json', initial)
        if any(s['rows'] for s in initial.values()):
            raise ValueError('Oracle initial state is not empty')
        dump(path / 'lineage.json', {'command': command, 'database': db, 'cwd': str(ESTATE)})
        for number in (1, 2):
            dest = path / f'run{number}'
            dest.mkdir()
            start = utc()
            result = subprocess.run(command, cwd=ESTATE, env=env, capture_output=True, text=True)
            (dest / 'stdout_stderr.log').write_text(result.stdout + result.stderr)
            for folder in ('SessLogs', 'BadFiles', 'WorkflowLogs'):
                if (root / folder).exists():
                    shutil.copytree(root / folder, dest / folder)
            shutil.copy2(root / 'REP_SESS_LOG.psv', dest / 'REP_SESS_LOG.psv')
            runs = sessions(root)
            dump(dest / 'session_results.json', runs)
            targets = {s: snapshot(pg, t[1]) for s, t in TARGETS.items()}
            targets['archive'] = snapshot(pg, ARCHIVE_PG)
            dump(dest / 'targets.json', targets)
            rejects = {f.name: f.read_text().splitlines() for f in sorted((root / 'BadFiles').glob('*.bad'))}
            dump(dest / 'rejects.json', rejects)
            dump(dest / 'execution.json', {'argv': command, 'returncode': result.returncode,
                                           'start_utc': start, 'end_utc': utc()})
            if result.returncode:
                raise ValueError('Oracle workflow failed')
    run1 = load(path / 'run1/targets.json')
    accepted = {}
    for session, (mapping, _, _, keys) in TARGETS.items():
        template = load(ACCEPTED / mapping / 'oracle1/target.json')
        compare = full_compare(template, run1[session], keys)
        accepted[session] = {'equal': compare['equal'], 'rows': compare['after_rows'],
                             'accepted_rows': compare['before_rows']}
    status = {r['SESSION_INSTANCE_NAME']: r['RUN_STATUS'] for r in load(path / 'run1/session_results.json')}
    summary = {'accepted_oracle_equal': accepted, 'run1_sessions': status,
               'archive_rows': len(run1['archive']['rows']),
               'archive_ran': 's_m_SFX_AUDIT_EVENT_ARCHIVE' in status}
    dump(path / 'summary.json', summary)
    print(json.dumps(summary, indent=2))
    if not all(a['equal'] for a in accepted.values()) or summary['archive_ran'] or \
            set(status) != set(TARGETS) or set(status.values()) != {'SUCCEEDED'}:
        raise ValueError('Oracle does not match the accepted UNT-2 workflow oracle')


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('step', choices=['oracle'])
    args = parser.parse_args(argv)
    {'oracle': oracle}[args.step]()


if __name__ == '__main__':
    main()
