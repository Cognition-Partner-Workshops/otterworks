import csv
import datetime as dt
import json
from pathlib import Path

from dbql.generate import AS_OF, inventory


ROOT = Path(__file__).resolve().parents[3]


def test_fragment_locations():
    fragment = json.loads((ROOT / 'demos/app/complexity/sfx-teradata.json').read_text())
    assert (fragment['schema_version'], fragment['area'], fragment['run_token']) == (1, 'teradata', 'sfx-d1110')
    assert len(fragment['classes']) == 5
    assert len({group['id'] for group in fragment['classes']}) == 5
    objects = inventory()
    locations = 0
    for group in fragment['classes']:
        assert group['instances']
        for instance in group['instances']:
            path = ROOT / instance['file']
            assert path.is_file(), path
            lines = path.read_text().splitlines()
            assert 1 <= instance['line'] <= len(lines), instance
            assert instance['anchor'] in lines[instance['line']-1], instance
            assert instance['object'] in objects, instance
            for value in instance.values():
                if isinstance(value, dict) and 'keys' in value:
                    assert value['table'] in objects
                    assert value['range'][0] == 9_000_000_001
                    assert value['range'][1]-value['range'][0]+1 == value['count']
                    assert value['keys'] == list(range(value['range'][0], value['range'][0]+20))
            locations += 1
    candidates = next(value for value in fragment.values() if isinstance(value, list) and value and 'evidence' in value[0])
    assert len(candidates) == 6
    for candidate in candidates:
        path = ROOT / candidate['evidence']
        with path.open() as handle:
            catalog = {row['DatabaseName']+'.'+row['TableName']: row for row in csv.DictReader(handle)}
        row = catalog[candidate['object']]
        assert candidate['kind'] == {'T': 'table', 'V': 'view', 'M': 'macro'}[row['TableKind']]
        assert row['LastAccessTimeStamp'] == candidate['last_access']
        assert dt.datetime.fromisoformat(candidate['last_access']).date() < AS_OF-dt.timedelta(days=90)
    print(f'Fragment valid: {len(fragment["classes"])} classes, {locations} file:line anchors, {len(candidates)} catalog evidence records')
