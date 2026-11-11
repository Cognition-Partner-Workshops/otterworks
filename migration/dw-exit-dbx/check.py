"""Validate local assessment and live control-table counts; never creates objects."""
import sys
import json
import copy
import re
import subprocess
from collections import Counter
from decimal import Decimal

import yaml
import assess

from load_control import BASE, TABLE, connect, execute


def live_differences(entries, rows):
    expected = {e['id']: tuple(e[c] for c in ('target', 'wave', 'owner', 'risk')) for e in entries}
    actual = {row[0]: tuple(row[1:]) for row in rows}
    return sorted(key for key in expected.keys() | actual.keys() if expected.get(key) != actual.get(key))


def manifest_differences(recorded, expected):
    if recorded['metadata']['spark_ref'] != 'working tree':
        return [] if recorded == expected else ['manifest fields differ from regenerated estate assessment']
    failures = []
    commit = recorded['metadata']['spark_commit']
    paths = sorted({p for doc in (recorded, expected) for e in doc['objects'] for p in e['source_paths']}
                   | set(assess.source_files()) | set(assess.spark_files()))
    try:
        if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', commit):
            raise ValueError('invalid commit ID')
        assess.git('cat-file', '-e', commit + '^{commit}')
        if assess.git('diff', '--name-only', commit, 'HEAD', '--', *paths).strip() or assess.git('diff', '--name-only', 'HEAD', '--', *paths).strip():
            failures.append('working-tree assessed sources changed since recorded commit')
    except (subprocess.CalledProcessError, ValueError):
        failures.append('working-tree provenance commit does not exist or is invalid')
    recorded = copy.deepcopy(recorded)
    expected = copy.deepcopy(expected)
    for document in (recorded, expected):
        document['metadata'].pop('spark_commit', None)
    if recorded != expected:
        failures.append('manifest fields differ from regenerated estate assessment')
    return failures


def main():
    failures = []
    path = BASE / 'manifest.yaml'
    entries = yaml.safe_load(path.read_text())['objects'] if path.exists() else []
    if not path.exists():
        failures.append('manifest.yaml missing')
    else:
        from assess import ALLOWED, dbql, source_files
        metadata = yaml.safe_load(path.read_text())['metadata']
        assess.SPARK_REF = None if metadata['spark_ref'] == 'working tree' else metadata['spark_ref']
        expected = assess.manifest_document()
        failures.extend(manifest_differences(yaml.safe_load(path.read_text()), expected))
        covered = {p for e in entries for p in e['source_paths']}
        if not set(source_files()) <= covered:
            failures.append('source file coverage incomplete')
        if any(e['target'] not in ALLOWED for e in entries):
            failures.append('invalid target')
        dead, hidden = dbql()
        if {e['object_name'] for e in entries if e['target'] == 'retire'} != {name for name, evidence in dead.items() if not evidence['code_readers']}:
            failures.append('dead count mismatch')
        if {e['object_name']: e['unread_tier'] for e in entries if e['unread_tier']} != {name: evidence['tier'] for name, evidence in dead.items()}:
            failures.append('unread tier mismatch')
        print(f'DBQL unread={len(dead)} dormant={sum(d["tier"] == "dormant" for d in dead.values())} write_only={sum(d["tier"] == "write-only" for d in dead.values())} retire={sum(e["target"] == "retire" for e in entries)} hidden={len(hidden)}')
        if sum(e['kind'] == 'hidden consumer' for e in entries) != len(hidden):
            failures.append('hidden count mismatch')
        if 'etl/spark/jobs.txt' in assess.spark_files():
            baseline = json.loads(assess.read('etl/spark/history/baseline.json'), parse_float=Decimal)
            jobs = [e for e in entries if e['kind'] == 'Spark job']
            hours = sum(Decimal(str(e['executor_hours'])) for e in jobs)
            if len(jobs) != 30 or abs(hours - baseline['totals']['executor_hours']) > Decimal('0.000000010'):
                failures.append('Spark count or measured executor-hours mismatch')
            print(f'SPARK jobs={len(jobs)} executor_hours={hours} baseline={baseline["totals"]["executor_hours"]}')
    try:
        with connect() as connection, connection.cursor() as cursor:
            rows = execute(cursor, 'check', f'SELECT wave, count(*) FROM {TABLE} GROUP BY wave ORDER BY wave').fetchall()
            actual = {int(r[0]): int(r[1]) for r in rows}
            print(f'LIVE count={sum(actual.values())} waves={actual}')
            if actual != dict(sorted(Counter(e['wave'] for e in entries).items())):
                failures.append('live counts differ from manifest')
            details = execute(cursor, 'check_fields', f'SELECT object_name, target, wave, owner, risk FROM {TABLE} ORDER BY object_name').fetchall()
            differences = live_differences(entries, details)
            print(f'LIVE field_mismatches={len(differences)}')
            if differences:
                failures.append('live target/wave/owner/risk mismatch: ' + ', '.join(differences))
            measured = execute(cursor, 'check_hours', f'SELECT sum(executor_hours) FROM {TABLE}').fetchone()[0]
            print(f'LIVE executor_hours={measured}')
            expected_hours = sum(Decimal(str(e['executor_hours'])) for e in entries if e['executor_hours'] is not None)
            if (measured or Decimal(0)) != expected_hours:
                failures.append('live executor-hours mismatch')
    except Exception as error:
        print(f'LIVE SELECT FAILED {type(error).__name__}: {error}')
        failures.append('live control table unavailable')
    for failure in failures:
        print('FAIL ' + failure)
    print(f'{"FAIL" if failures else "PASS"} manifest_entries={len(entries)} errors={len(failures)}')
    return bool(failures)


if __name__ == '__main__':
    sys.exit(main())
