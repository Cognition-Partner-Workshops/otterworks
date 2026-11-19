"""Documents PowerCenter ports and stateful writers, separate from BTEQ snapshots."""

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from .ingest import business_date
from .layout import data_root, delta_path
from .session import create_session


DOCUMENT = ['document_id', 'folder_id', 'owner_user_id', 'customer_id',
            'document_name', 'created_dt', 'status_cd', 'file_type']
SHARE = ['share_id', 'document_id', 'user_id', 'access_level', 'shared_dt']
DOCUMENT_SCHEMA = ('document_id long, folder_id long, owner_user_id long, customer_id long, '
                   'document_name string, created_dt date, status_cd string, file_type string')
SHARE_SCHEMA = 'share_id long, document_id long, user_id long, access_level string, shared_dt date'
METRICS_SCHEMA = ('pipeline string, source_rows long, transformation_errors long, written_rows long, '
                  'rejected_rows long, inserted_rows long, updated_rows long, '
                  'rows_before long, rows_after long')


def read_feed(path, columns):
    with Path(path).open(newline='', encoding='utf-8') as handle:
        return [dict(zip(columns, [None if value == '' else value for value in
                                   (row + [''] * len(columns))[:len(columns)]]))
                for row in csv.reader(handle, delimiter='|', quoting=csv.QUOTE_NONE) if row]


def integer(value):
    if value is None:
        return None
    match = re.match(r'[-+]?\d+(\.\d*)?', value.strip())
    if not match:
        raise ValueError('invalid integer port')
    return int(Decimal(match.group()))


def date_port(value):
    if value is None:
        return None
    if not re.fullmatch(r'\d{4}-\d{1,2}-\d{1,2}', value):
        raise ValueError('invalid date port')
    return datetime.strptime(value, '%Y-%m-%d').date()


def text(value, width, upper=False):
    if value is None or value == '':
        return None
    value = value[:width].strip(' ')
    return value.upper() if upper else value


def ports(row, share=False):
    columns = SHARE if share else DOCUMENT
    numeric = columns[:3] if share else columns[:4]
    out = {key: integer(row[key][:20] if row[key] is not None else None) for key in numeric}
    if share:
        out.update(access_level=text(row['access_level'], 12, True),
                   shared_dt=date_port(row['shared_dt'][:10] if row['shared_dt'] else None))
        if out['access_level'] is not None:
            out['access_level'] = out['access_level'][:12]
    else:
        out.update(document_name=text(row['document_name'], 120),
                   created_dt=date_port(row['created_dt'][:10] if row['created_dt'] else None),
                   status_cd=text(row['status_cd'], 12, True), file_type=text(row['file_type'], 8))
    return out


def valid_target(row, key, widths):
    if key is not None and row[key] is None:
        return False
    return (not any(isinstance(value, str) and '\x00' in value for value in row.values()) and
            all(value is None or not isinstance(value, int) or -(2 ** 63) <= value < 2 ** 63
                for value in row.values()) and
            all(row[column] is None or len(row[column]) <= width for column, width in widths.items()))


def convert(document_feed, share_feed, users, roles, previous_documents=(), previous_shares=(),
            previous_stage_count=0):
    documents = {row['document_id']: dict(row) for row in previous_documents}
    shares = {row['share_id']: dict(row) for row in previous_shares}
    existing = set(documents)
    statuses, grants = {}, {}
    for row in users:
        statuses.setdefault(row['user_id'], row['status_cd'])
    for row in roles:
        grants.setdefault(row['user_id'], row['role_cd'])
    stage, rejected, metrics = [], [], []

    def metric(name, count, before):
        return dict(pipeline=name, source_rows=count, transformation_errors=0, written_rows=0,
                    rejected_rows=0, inserted_rows=0, updated_rows=0, rows_before=before, rows_after=0)

    def reject(m, position, kind):
        m['rejected_rows'] += 1
        m['transformation_errors'] += kind == 'transformation'
        rejected.append(dict(pipeline=m['pipeline'], source_row=position, rejection_kind=kind))

    m = metric('stg_document', len(document_feed), previous_stage_count)
    for position, raw in enumerate(document_feed, 1):
        try:
            row = ports(raw)
        except ValueError:
            reject(m, position, 'transformation')
            continue
        if not valid_target(row, None, {'document_name': 200, 'status_cd': 200, 'file_type': 200}):
            reject(m, position, 'writer')
            continue
        stage.append(row)
        m['inserted_rows'] += 1
    m['written_rows'] = m['rows_after'] = len(stage)
    metrics.append(m)

    m = metric('document', len(stage), len(documents))
    filtered = []
    for position, row in enumerate(stage, 1):
        if row['owner_user_id'] is None or statuses.get(row['owner_user_id']) is None:
            filtered.append(dict(row))
            continue
        key = row['document_id']
        if (not valid_target(row, 'document_id', {'document_name': 120, 'status_cd': 12, 'file_type': 8})
                or key in documents and key not in existing):
            reject(m, position, 'writer')
            continue
        documents[key] = dict(row)
        m['updated_rows' if key in existing else 'inserted_rows'] += 1
        m['written_rows'] += 1
    m['rows_after'] = len(documents)
    metrics.append(m)

    m = metric('doc_share', len(share_feed), len(shares))
    for position, raw in enumerate(share_feed, 1):
        try:
            row = ports(raw, share=True)
        except ValueError:
            reject(m, position, 'transformation')
            continue
        role = grants.get(row['user_id']) if row['user_id'] is not None else None
        role = role.rstrip(' ')[:12] if role is not None else None
        if role == 'ADMIN':
            row['access_level'] = 'OWNER'
        elif role == 'EDITOR' and row['access_level'] == 'VIEW':
            row['access_level'] = 'EDIT'
        if not valid_target(row, 'share_id', {'access_level': 12}):
            reject(m, position, 'writer')
            continue
        key = row['share_id']
        m['updated_rows' if key in shares else 'inserted_rows'] += 1
        shares[key] = row
        m['written_rows'] += 1
    m['rows_after'] = len(shares)
    metrics.append(m)
    return dict(stg_document=stage, document=list(documents.values()), doc_share=list(shares.values()),
                metrics=metrics, rejects=rejected, filtered=filtered)


def checkpoint(path, signature, compute):
    saved = json.loads(path.read_text()) if path.exists() else None
    if saved is not None and saved['signature'] == signature:
        result = saved['result']
        for name, column in [('stg_document', 'created_dt'), ('document', 'created_dt'),
                             ('doc_share', 'shared_dt'), ('filtered', 'created_dt')]:
            for row in result[name]:
                if row[column] is not None:
                    row[column] = datetime.strptime(row[column], '%Y-%m-%d').date()
        return result
    result = compute()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(dict(signature=signature, result=result), default=str))
    temporary.replace(path)
    return result


def run(spark, landing, day):
    business_date(day)

    def previous(name):
        table = 'silver_documents.infa_runtime_' + name
        return [row.asDict() for row in spark.table(table).collect()] if spark.catalog.tableExists(table) else []

    def lookup(table, columns):
        return [row.asDict() for row in spark.table('bronze_users.' + table)
                .where(f"_business_date = '{business_date(day)}'")
                .selectExpr('cast(user_id as bigint) as user_id', columns[1]).orderBy('user_id').collect()]

    inputs = dict(document_feed=read_feed(Path(landing) / 'documents/DOCUMENT' / f'{day}.psv', DOCUMENT),
                  share_feed=read_feed(Path(landing) / 'documents/DOC_SHARE' / f'{day}.psv', SHARE),
                  users=lookup('app_user', ['user_id', 'status_cd']),
                  roles=lookup('role_grant', ['user_id', 'role_cd']))
    signature = hashlib.sha256(json.dumps([day, inputs], sort_keys=True).encode() +
                               Path(__file__).read_bytes()).hexdigest()
    result = checkpoint(data_root() / 'transactions/documents_informatica.json', signature,
                        lambda: convert(**inputs, previous_documents=previous('document'),
                                        previous_shares=previous('doc_share'),
                                        previous_stage_count=len(previous('stg_document'))))
    schemas = dict(stg_document=DOCUMENT_SCHEMA, document=DOCUMENT_SCHEMA, doc_share=SHARE_SCHEMA,
                   metrics=METRICS_SCHEMA, rejects='pipeline string, source_row long, rejection_kind string',
                   filtered=DOCUMENT_SCHEMA)
    for name, rows in result.items():
        path = delta_path('silver', 'documents', 'infa_runtime_' + name)
        frame = spark.createDataFrame(rows, schemas[name])
        frame.write.format('delta').mode('overwrite').save(str(path))
        spark.sql(f"CREATE TABLE IF NOT EXISTS silver_documents.infa_runtime_{name} USING DELTA LOCATION '{path.as_uri()}'")
        print(f'documents.informatica.{name}: {len(rows)}', flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--landing', type=Path, required=True)
    parser.add_argument('--business-date', required=True)
    args = parser.parse_args()
    spark = create_session()
    try:
        run(spark, args.landing, args.business_date)
    finally:
        spark.stop()


if __name__ == '__main__':
    main()
