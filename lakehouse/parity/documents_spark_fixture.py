"""Deterministic, dated shared Spark-feed fixture; never warehouse feeds."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

from etl.spark.jobs.py.common.schemas import SCHEMAS
from lakehouse.runtime.documents_spark import SCHEMAS as INPUTS
from lakehouse.runtime.ingest import business_date


def generate(landing, day):
    date = business_date(day)
    root = Path(landing) / 'spark' / day
    ids = list(range(1, 65)) + [-1, 9999, 10000, 20000]
    rows = {table: [] for table in INPUTS}
    for i, doc in enumerate(ids, 1):
        owner = (i - 1) // 4 + 1
        rows['DOCUMENT'].append([doc, owner, (i - 1) // 8 + 1, f'Document {doc}', f'{date} 12:00:00', 'published'])
        rows['FILE_OBJECT'].append([i, doc, None if owner == 1 else i * 1000000000, f'hash-{i}', f'key-{i}'])
        rows['DOC_SHARE'].append([i, doc, 999, i % 7 + 1, ['view', 'edit', 'comment'][i % 3]])
        rows['DOC_TAG'].append([i, doc, [None, ' Finance ', 'annual\t review', 'ÉCOLE', 'ß', 'Ops\u00a0 Team', 'Contract|Legal'][i % 7]])
        rows['SEARCH_INDEX_LOG'].append([i, doc, f'{date} 12:00:00',
                                         [None, 'no action here', 'action=é_9 action=ignored', 'action=VIEW-status'][i % 4], 'active'])
    rows['FILE_OBJECT'].append([999, 1, None, 'extra', 'extra'])
    rows['DOC_SHARE'].append([999, 1, 999, 2, 'edit'])
    for i in range(1, 21):
        rows['APP_USER'].append([i, f'owner-{i}@example.test', f'Owner {i}', f'{date} 00:00:00', 'active'])
    for i in range(1, 11):
        rows['FOLDER'].append([i, 1, None if i == 1 else 1, f'Folder {i}'])
    files = {}
    for table, (area, _) in INPUTS.items():
        path = root / area / table / f'{day}.psv'
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.tmp')
        with temporary.open('w', newline='') as handle:
            writer = csv.writer(handle, delimiter='|', lineterminator='\n')
            writer.writerow([name for name, _ in SCHEMAS[table]])
            writer.writerows(rows[table])
        temporary.replace(path)
        files[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = dict(version=1, business_date=day, generator=__name__,
                    generator_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    files=files, rows={key: len(value) for key, value in rows.items()})
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--landing', type=Path, required=True)
    parser.add_argument('--business-date', required=True)
    args = parser.parse_args()
    generate(args.landing, args.business_date)


if __name__ == '__main__':
    main()
