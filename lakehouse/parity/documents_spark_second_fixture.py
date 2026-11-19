"""Deterministic second-batch feeds, isolated from first-batch provenance."""

import argparse
import csv
import hashlib
import json
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZipInfo

from lakehouse.runtime.documents_spark import SCHEMAS, SECOND_SCHEMAS
from lakehouse.runtime.ingest import business_date


def archive(entries):
    stream = BytesIO()
    with ZipFile(stream, 'w') as handle:
        for name, content in entries:
            handle.writestr(ZipInfo(name, (1980, 1, 1, 0, 0, 0)), content)
    return stream.getvalue()


def blobs():
    word = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:t>{}</w:t></w:document>'
    return {
        'valid.pdf': b'%PDF-1.4\n/Type /Pages /Type /Page /Type /Page\n(Hello) Tj (world) Tj',
        'corrupt.pdf': b'%PDF-1.4\n(no pages) Tj',
        'empty.bin': b'',
        'corrupt.zip': b'PK\x03\x04broken',
        'text.zip': archive([('a.txt', 'Alpha\fBeta'), ('b.txt', 'Unicode \u00e9'), ('skip.dat', 'not text')]),
        'empty.zip': archive([]),
        'valid.docx': archive([('word/document.xml', word.format('Hello &amp; world'))]),
        'long.docx': archive([('word/document.xml', word.format('x' * 6001))]),
        'corrupt.docx': archive([('word/document.xml', '<unclosed>')]),
        'doctype.docx': archive([('word/document.xml', '<!DOCTYPE x [<!ENTITY e "blocked">]><x>&e;</x>')]),
        'unsupported.bin': b'plain data',
        'unmatched.pdf': b'%PDF-1.4 /Type /Page (no metadata) Tj',
    }


def generate(landing, day):
    date = business_date(day)
    root = Path(landing) / 'spark' / day
    folders = [[i, 1, i - 1 if i > 1 else None, f'Folder {i}'] for i in range(1, 26)]
    folders += [[0, 1, None, 'Zero root'], [100, 1, 101, 'Cycle A'], [101, 1, 102, 'Cycle B'],
                [102, 1, 100, 'Cycle C'], [200, 1, 200, 'Self cycle'],
                [201, 1, 999, 'Orphan'], [202, 1, 0, 'Zero parent']]
    edges = [(1, 1), (1, 2), (2, 3), (3, 1), (3, 4), (4, 5), (5, 6),
             (2, 2), (1, 2), (40, 41), (41, 40)]
    shares = [[i, 999, owner, recipient, 'view'] for i, (owner, recipient) in enumerate(edges, 1)]
    midnight = datetime.combine(date, datetime.min.time())
    events = [[i, 7, 1, 'ignored-source-id', midnight + timedelta(seconds=seconds)]
              for i, seconds in enumerate([3601, 0, 1800, 1800, 1801, 5402], 1)]
    events += [[100, 8, 1, 'single', midnight], [101, 7, 2, 'other-user', midnight]]
    bodies = [(1, 1, 'abc'), (1, 2, 'abX'), (1, 3, None), (1, 4, '\u00e9\u00e9'),
              (2, 1, None), (2, 2, 'same'), (2, 3, 'same'), (3, 1, 'a' * 250 + 'b'),
              (3, 2, 'a' * 250 + 'c'), (4, 1, 'quoted|body'), (4, 2, 'changed|body')]
    versions = [[i, doc, number, body, midnight] for i, (doc, number, body) in enumerate(bodies, 1)]
    content = blobs()
    objects = [[i, i, len(raw), 'not-the-content-hash', 'documents/FILE_OBJECT_BLOBS/' + name]
               for i, (name, raw) in enumerate(content.items(), 1) if name != 'unmatched.pdf']
    objects += [[100, 1, 0, 'duplicate-blob-reference', 'documents/FILE_OBJECT_BLOBS/valid.pdf'],
                [101, 1, 0, 'missing-blob', 'documents/FILE_OBJECT_BLOBS/missing.pdf']]
    rows = dict(FOLDER=folders, DOC_SHARE=shares, COLLAB_SESSION=events, DOC_VERSION=versions, FILE_OBJECT=objects)
    schemas = {**SCHEMAS, **SECOND_SCHEMAS}
    files = {}
    for table, records in rows.items():
        path = root / 'documents' / table / f'{day}.psv'
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.tmp')
        with temporary.open('w', newline='') as handle:
            writer = csv.writer(handle, delimiter='|', lineterminator='\n')
            writer.writerow([column.split()[0] for column in schemas[table][1].split(', ')])
            writer.writerows(records)
        temporary.replace(path)
        files[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    directory = root / 'documents/FILE_OBJECT_BLOBS'
    directory.mkdir(parents=True, exist_ok=True)
    for name, raw in content.items():
        path = directory / name
        temporary = path.with_suffix('.tmp')
        temporary.write_bytes(raw)
        temporary.replace(path)
        files[str(path.relative_to(root))] = hashlib.sha256(raw).hexdigest()
    manifest = dict(version=1, business_date=day, generator=__name__,
                    generator_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), files=files,
                    rows={key: len(value) for key, value in rows.items()},
                    blobs=len(content), bytes=sum(map(len, content.values())))
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
