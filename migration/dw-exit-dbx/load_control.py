"""Scoped, tagged Databricks SQL control-table loader."""
import os
from pathlib import Path

import yaml

TABLE = "cpw.dbx_d1111_control.migration_control"
COMMENT = "run_token=dbx-d1111 expires=2026-11-24"
BASE = Path(__file__).resolve().parent


def connect():
    from databricks import sql
    if os.environ['DATABRICKS_CATALOG'] != 'cpw':
        raise ValueError('Only catalog cpw is permitted')
    return sql.connect(
        server_hostname=os.environ['DATABRICKS_HOST'].removeprefix('https://').rstrip('/'),
        http_path='/sql/1.0/warehouses/' + os.environ['DATABRICKS_WAREHOUSE_ID'],
        access_token=os.environ['DATABRICKS_TOKEN'])


def execute(cursor, step, statement, parameters=None):
    cursor.execute(f'/* run=dbx-d1111 act=assess step={step} */ ' + statement, parameters)
    print(f'SQL step={step} statement_id={getattr(cursor, "query_id", None) or "unavailable"}')
    return cursor


def main():
    entries = yaml.safe_load((BASE / 'manifest.yaml').read_text())['objects']
    with connect() as connection, connection.cursor() as cursor:
        execute(cursor, 'schema', f"CREATE SCHEMA IF NOT EXISTS cpw.dbx_d1111_control COMMENT '{COMMENT}'")
        execute(cursor, 'table', f"CREATE TABLE IF NOT EXISTS {TABLE} (object_name STRING, subject_area STRING, source_system STRING, target STRING, status STRING, parity STRING, pr STRING, updated_at TIMESTAMP) USING DELTA COMMENT '{COMMENT}'")
        existing = {row[0] for row in execute(cursor, 'columns', f'DESCRIBE TABLE {TABLE}').fetchall()}
        additions = {'wave': 'INT', 'owner': 'STRING', 'risk': 'STRING', 'risk_reason': 'STRING', 'kind': 'STRING', 'source_path': 'STRING', 'loc': 'INT', 'complexity': 'STRING', 'executor_hours': 'DECIMAL(18,9)'}
        missing = [f'{name} {dtype}' for name, dtype in additions.items() if name not in existing]
        if missing:
            execute(cursor, 'extend', f'ALTER TABLE {TABLE} ADD COLUMNS (' + ', '.join(missing) + ')')
        columns = ['object_name', 'subject_area', 'source_system', 'target', *additions]
        values = ','.join('(' + ','.join('?' for _ in columns) + ')' for _ in entries)
        parameters = []
        for entry in entries:
            row = dict(entry, object_name=entry['id'], source_path=';'.join(entry['source_paths']))
            parameters.extend(row[c] for c in columns)
        updates = ', '.join(f't.{c}=s.{c}' for c in columns if c != 'object_name')
        execute(cursor, 'load', f"MERGE INTO {TABLE} t USING (SELECT * FROM VALUES {values} AS v({','.join(columns)})) s ON t.object_name=s.object_name WHEN MATCHED THEN UPDATE SET {updates}, t.updated_at=current_timestamp() WHEN NOT MATCHED THEN INSERT ({','.join(columns)},status,parity,pr,updated_at) VALUES ({','.join('s.' + c for c in columns)},'planned',NULL,NULL,current_timestamp())", parameters)
        print(f'LOADED {len(entries)} entries')


if __name__ == '__main__':
    main()
