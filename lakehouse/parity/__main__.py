import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone

from lakehouse.runtime.ingest import business_date
from lakehouse.runtime.layout import ROOT, data_root

from .engine import compare
from .readers import Readers
from .spec import discover

EVIDENCE = ROOT / 'evidence'


def write_rollup(directory=EVIDENCE):
    lines = ['# Lakehouse parity', '',
             '| Spec | Coverage IDs | NS | Business date | Legacy rows | Lakehouse rows | Result |',
             '|---|---|---|---|---:|---:|---|']
    for path in sorted((directory / 'parity').glob('*.json')):
        report = json.loads(path.read_text())
        result = report['results']
        counts = result.get('row_counts', {})
        fields = [f'[{report["id"]}](parity/{path.name})', ', '.join(report['legacy_objects']),
                  report['NS'], report['business_date'], counts.get('legacy', '—'),
                  counts.get('lakehouse', '—'), 'PASS' if result['passed'] else 'FAIL']
        lines.append('| ' + ' | '.join(str(v).replace('|', '\\|') for v in fields) + ' |')
    (directory / 'PARITY.md').write_text('\n'.join(lines) + '\n')


def run(selected, day, sample_limit, evidence=EVIDENCE):
    data_root()
    business_date(day)
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip())
    readers = Readers(day)
    passed = True
    destination = evidence / 'parity'
    destination.mkdir(parents=True, exist_ok=True)
    try:
        for path, spec in selected:
            report = {'id': spec['id'], 'legacy_objects': spec['legacy_objects'],
                      'spec_hash': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'git_sha': sha, 'git_dirty': dirty, 'NS': os.environ['NS'],
                      'legacy_NS': os.environ.get('LEGACY_NS'), 'business_date': day,
                      'timestamp': datetime.now(timezone.utc).isoformat()}
            try:
                legacy, legacy_columns = readers.read(spec['legacy'])
                lakehouse, lakehouse_columns = readers.read(spec['lakehouse'])
                report['results'] = compare(legacy, lakehouse, spec, legacy_columns,
                                             lakehouse_columns, sample_limit)
            except Exception as exc:
                report['results'] = {'passed': False, 'error': f'{type(exc).__name__}: {exc}'}
            report['row_counts'] = report['results'].get('row_counts')
            (destination / f'{spec["id"]}.json').write_text(
                json.dumps(report, indent=2, sort_keys=True, default=str) + '\n')
            print(f'{spec["id"]}: {"PASS" if report["results"]["passed"] else "FAIL"} '
                  f'{report["row_counts"]}')
            if 'exact_matched_rows' in report['results']:
                print('  ' + ' '.join(f'{key}={report["results"][key]}' for key in
                                     ('exact_matched_rows', 'tie_resolved_rows', 'mismatches')))
            passed = passed and report['results']['passed']
    finally:
        readers.close()
        write_rollup(evidence)
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('run')
    selection = command.add_mutually_exclusive_group(required=True)
    selection.add_argument('--spec', nargs='+', action='extend')
    selection.add_argument('--all', action='store_true')
    command.add_argument('--business-date', required=True)
    command.add_argument('--samples', type=int, default=10)
    args = parser.parse_args()
    try:
        if args.samples < 0:
            raise ValueError('--samples must be nonnegative')
        specs = discover()
        wanted = sorted(specs) if args.all else sorted(set(args.spec))
        if not wanted or set(wanted) - specs.keys():
            raise ValueError(f'No specs selected or unknown ids: {sorted(set(wanted) - specs.keys())}')
        raise SystemExit(run([specs[key] for key in wanted], args.business_date, args.samples))
    except (ValueError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
