"""MERGE exactly the five mapping rows, preserving their inventory identity."""
import argparse
import json

from dbx import EVIDENCE, ROOT, rows, sql
from run_validation import literal

TABLE = 'cpw.dbx_d1111_control.migration_control'
FIELDS = ['first_failure', 'first_failure_statement_id', 'corrected_parity', 'parity_statement_id',
          'idempotence', 'idempotence_statement_ids', 'licence_features', 'red_reason',
          'run_token', 'expires', 'job_id', 'job_run_ids', 'cross_folder_dependencies']


def publish(pr):
    evidence = json.loads((ROOT / 'evidence.json').read_text())
    schema = rows(sql(f'DESCRIBE TABLE {TABLE}', 'SFX_CONTENT', 'control', 'control-schema'))
    existing = {r['col_name'] for r in schema}
    missing = [f for f in FIELDS if f not in existing]
    if missing:
        sql(f"ALTER TABLE {TABLE} ADD COLUMNS ({','.join(f + ' STRING' for f in missing)})",
            'SFX_CONTENT', 'control', 'guarded-columns')
    paths = ','.join(literal(r['source']) for r in evidence['rows'])
    inventory = rows(sql(f'SELECT object_name,source_path FROM {TABLE} WHERE source_path IN ({paths})',
                         'SFX_CONTENT', 'control', 'inventory-identity'))
    identities = {}
    for row in inventory:
        assert row['source_path'] not in identities, 'Ambiguous inventory row; refusing control update'
        identities[row['source_path']] = row['object_name']
    assert len(identities) == 5, 'Expected exactly five existing mapping rows'
    records = []
    columns = ['object_name', 'source_path', 'status', 'parity', 'pr', 'target'] + FIELDS
    for row in evidence['rows']:
        values = {'object_name': identities[row['source']], 'source_path': row['source'],
                  'status': row['status'], 'parity': row['corrected_parity'], 'pr': pr,
                  'target': row['target'], **{f: row[f] for f in FIELDS if f in row},
                  'run_token': 'dbx-d1111', 'expires': '2026-11-24', 'job_id': evidence['job']['job_id'],
                  'job_run_ids': [r['run_id'] for r in evidence['job']['runs']],
                  'cross_folder_dependencies': row.get('cross_folder_dependencies', evidence['cross_folder_dependencies'])}
        records.append('SELECT ' + ','.join(
            literal(json.dumps(values[c]) if isinstance(values[c], list) else values[c]) + ' AS ' + c
            for c in columns))
    source = '\nUNION ALL\n'.join(records)
    update = ','.join(f't.{c}=s.{c}' for c in columns if c not in ('object_name', 'source_path'))
    statement = (f'MERGE INTO {TABLE} t USING ({source}) s '
                 'ON t.object_name=s.object_name AND t.source_path=s.source_path '
                 f'WHEN MATCHED THEN UPDATE SET {update},t.updated_at=current_timestamp()')
    result = sql(statement, 'SFX_CONTENT', 'control', 'mapping-evidence-merge')
    verify = sql(f'SELECT object_name,source_path,status,parity,pr FROM {TABLE} WHERE source_path IN ({paths})',
                 'SFX_CONTENT', 'control', 'verify-control')
    assert len(rows(verify)) == 5 and all(r['pr'] == pr for r in rows(verify))
    assert sorted(r['status'] for r in rows(verify)) == ['green'] * 4 + ['red']
    (EVIDENCE / 'control.json').write_text(json.dumps({'merge_statement_id': result['statement_id'],
        'verify_statement_id': verify['statement_id'], 'rows': rows(verify)}, indent=2))
    print(json.dumps({'merge_statement_id': result['statement_id'], 'verify_statement_id': verify['statement_id'],
                      'updated_rows': rows(result), 'verified_count': len(rows(verify))}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pr', required=True)
    publish(parser.parse_args().pr)
