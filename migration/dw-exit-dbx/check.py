"""Validate local assessment and live control-table counts; never creates objects."""
import sys
import json
from collections import Counter
from decimal import Decimal

import yaml
import assess

from load_control import BASE, TABLE, connect, execute


def main():
    failures = []
    path = BASE / 'manifest.yaml'
    entries = yaml.safe_load(path.read_text())['objects'] if path.exists() else []
    if not path.exists():
        failures.append('manifest.yaml missing')
    else:
        from assess import ALLOWED, build, dbql, source_files
        metadata = yaml.safe_load(path.read_text())['metadata']
        assess.SPARK_REF = None if metadata['spark_ref'] == 'working tree' else metadata['spark_ref']
        expected = build()
        if {e['id'] for e in entries} != {e['id'] for e in expected}:
            failures.append('manifest object coverage differs from estate')
        covered = {p for e in entries for p in e['source_paths']}
        if not set(source_files()) <= covered:
            failures.append('source file coverage incomplete')
        if any(e['target'] not in ALLOWED for e in entries):
            failures.append('invalid target')
        dead, hidden = dbql()
        if sum(e['target'] == 'retire' for e in entries) != len(dead):
            failures.append('dead count mismatch')
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
