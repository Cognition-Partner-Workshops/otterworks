"""UNT-10: stage accepted mapping evidence for the shared mark command and read back control state."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

from .evidence import OUT as EVIDENCE_OUT, dump, sha
from .evidence_unt3 import control_snapshot, queries
from .inventory import inventory

OUT = Path(__file__).parent / 'out'
RUN = EVIDENCE_OUT / 'unt10'
OWNER = 'migrations-page'
BUNDLES = {
    'UNT-3': ('unt3/unt3-evidence.tar.gz', '5bcacf1f55dc12395cef8102de2f6ec589bc8219601e1ed98b0bd2d72b94a005'),
    'UNT-4': ('unt4/UNT-4-evidence.tar.gz', '58ecf795d1efeaf61cfa915cce93ee6c1bdfb563c5d1c60950e8ab4f9cc4fb22'),
    'UNT-5': ('unt5/bundle.tar.gz', '9693f01958ed65739adedf5b80c9f0f449c6384ec4df5ad53589271b64486780'),
    'UNT-6': ('unt6/bundle.tar.gz', 'e939134a3f73340b26723ae46f8b8e0893488c7e550b61a99c66995b56f1d783'),
    'UNT-7': ('unt7/bundle.tar.gz', '6851d0dfe6320e0f7ab32af573e3bc62074119e5eb89f637bf3c050132a48521'),
    'UNT-8': ('unt8/bundle.tar.gz', '3cf8385ea7594442c91cc6a32e3aa4b2918f82147244e97cd4bdbe8d7d2dd0fa'),
}
# (ticket, member, first-load comparison, second-run comparison, run1-vs-run2 comparison)
REPLAY = ('comparisons', 'oracle_run1'), ('comparisons', 'oracle_run2'), ('comparisons', 'run1_run2')
PROD = ('oracle1_dbt1',), ('oracle2_dbt2',), ('dbt1_dbt2',)
SOURCES = {
    'm_SFX_STG_AUDIT_EVENT': ('UNT-3', 'unt3/m_SFX_STG_AUDIT_EVENT/replay.json', REPLAY),
    'm_SFX_AUDIT_EVENT': ('UNT-3', 'unt3/m_SFX_AUDIT_EVENT/replay.json', REPLAY),
    'm_SFX_AUDIT_DAILY_SUMMARY': ('UNT-4', 'unt4/m_SFX_AUDIT_DAILY_SUMMARY/replay.json', REPLAY),
    'm_SFX_AUDIT_EVENT_ARCHIVE': ('UNT-4', 'unt4/m_SFX_AUDIT_EVENT_ARCHIVE/replay.json', REPLAY),
    'm_SFX_SECURITY_ALERT': ('UNT-5', 'production/comparison.json', PROD),
    'm_SFX_LOGIN_EVENT': ('UNT-6', 'production/comparison.json', PROD),
    'm_SFX_ROLE_GRANT': ('UNT-7', 'production/comparison_attempts/52134f52efa940ccb2ff9856d1c51460/comparison.json', PROD),
    'm_SFX_TEAM_MEMBER': ('UNT-8', None, None),
}
TEAM = ('unt8/production/comparison/parity1.json', 'unt8/production/comparison/parity2.json',
        'unt8/production/comparison/dbt_replay.json')


def member(tar, name):
    data = tar.extractfile(tar.getmember(name)).read()
    return json.loads(data), hashlib.sha256(data).hexdigest()


def pick(doc, path):
    for part in path:
        doc = doc[part]
    return doc


def clean(c):
    return (c['equal'] is True and not c['only_before'] and not c['only_after']
            and not c['duplicate_keys_before'] and not c['duplicate_keys_after'])


def evidence(mapping, root):
    ticket, name, paths = SOURCES[mapping]
    archive, expected = BUNDLES[ticket]
    if sha(root / archive) != expected:
        raise ValueError(f'{ticket} bundle hash mismatch')
    with tarfile.open(root / archive) as tar:
        if ticket == 'UNT-8':
            docs = [member(tar, n) for n in TEAM]
            first, second, replay = (d for d, _ in docs)
            files = {n: h for n, (_, h) in zip(TEAM, docs)}
            passed = True
        else:
            doc, digest = member(tar, name)
            first, second, replay = (pick(doc, p) for p in paths)
            files = {name: digest}
            passed = doc.get('passed') is True
    ok = passed and all(clean(c) for c in (first, second, replay))
    duplicates = len(second['duplicate_keys_after']) + len(replay['duplicate_keys_after'])
    tag = json.dumps({'unt10': ticket, 'bundle_sha256': expected,
                      'files': {k: v[:16] for k, v in files.items()}}, sort_keys=True, separators=(',', ':'))
    return dict(before_rows=first['before_rows'], after_rows=second['after_rows'],
                rowcount_match=ok and first['before_rows'] == first['after_rows'] == second['before_rows'] == second['after_rows'],
                keyed_hash_match=ok, sampled_diffs=[], run1_rows=first['after_rows'], run2_rows=second['after_rows'],
                rerun_duplicates=duplicates, parity_query_tag=tag, parity_error=None,
                evidence={'ticket': ticket, 'bundle': archive, 'bundle_sha256': expected, 'files': files})


def stage(root):
    rows = {r['mapping']: r for r in inventory()}
    manifest = {}
    for mapping in SOURCES:
        row = rows[mapping]
        result = evidence(mapping, root)
        result['config'] = row
        OUT.mkdir(exist_ok=True)
        (OUT / (mapping + '.json')).write_text(json.dumps(result, indent=2, default=str))
        manifest[row['folder'] + '.' + mapping] = {k: v for k, v in result.items() if k != 'config'}
    dump(RUN / 'staged.json', manifest)
    print(json.dumps({k: (v['before_rows'], v['run1_rows'], v['run2_rows'], v['rerun_duplicates'],
                          v['keyed_hash_match']) for k, v in manifest.items()}))


def readback(label):
    path = RUN / label
    with queries(path, 'unt10_readback') as q:
        result = control_snapshot(q, path)
    control = json.loads((path / 'control.json').read_text())
    cols = control['columns']
    keyed = {}
    for r in control['rows']:
        rec = {c: v[1] for c, v in zip(cols, r)}
        keyed[rec['FOLDER'] + '.' + rec['MAPPING']] = {
            'owner': rec['OWNER_EFFORT'], 'status': rec['STATUS'], 'amber_reason': rec['AMBER_REASON'],
            'row_sha256': hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest()}
    result['rows'] = keyed
    result['held_compute_budget'] = sorted(k for k, v in keyed.items()
                                           if 'held: compute budget' in str(v['amber_reason'] or '').lower())
    dump(path / 'readback.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}))


def diff(a, b):
    before = json.loads((RUN / a / 'readback.json').read_text())['rows']
    after = json.loads((RUN / b / 'readback.json').read_text())['rows']
    if set(before) != set(after):
        raise ValueError('Control key set changed')
    changed = sorted(k for k in before if before[k]['row_sha256'] != after[k]['row_sha256'])
    result = {'from': a, 'to': b, 'keys': len(after), 'changed': {
        k: {'status': [before[k]['status'], after[k]['status']],
            'amber_reason': [before[k]['amber_reason'], after[k]['amber_reason']]} for k in changed},
        'act3_unchanged': all(before[k]['row_sha256'] == after[k]['row_sha256']
                              for k in before if before[k]['owner'] != OWNER),
        'changed_only_ours': all(before[k]['owner'] == OWNER for k in changed)}
    dump(RUN / f'diff_{a}_{b}.json', result)
    print(json.dumps(result))
    if not result['act3_unchanged'] or not result['changed_only_ours']:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['stage', 'readback', 'diff'])
    parser.add_argument('--bundles', type=Path)
    parser.add_argument('--label')
    parser.add_argument('--against')
    args = parser.parse_args()
    if args.command == 'stage':
        stage(args.bundles)
    elif args.command == 'readback':
        readback(args.label)
    else:
        diff(args.against, args.label)


if __name__ == '__main__':
    main()
