"""Promote only objects that pass both legs of a fresh subject-area board."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from object_board import MANIFEST, MIGRATION, SnowflakeMeasurements, measure_board, update_migration_summary
from parity.connection import COMMENT, DATABASE
from warehouse.run_config import RunConfig

SCHEMA = DATABASE + '.MIGRATION_CONTROL'
CONTROL = SCHEMA + '.OBJECTS'


@contextmanager
def control_transaction(connection, schema, table, comment, query_tag=None):
    with connection.cursor() as cursor:
        if query_tag is not None:
            cursor.execute('ALTER SESSION SET QUERY_TAG = ?', (query_tag,))
        cursor.execute('CREATE SCHEMA IF NOT EXISTS IDENTIFIER(?) COMMENT = ?', (schema, comment))
        cursor.execute("""CREATE TABLE IF NOT EXISTS IDENTIFIER(?) (
            SUBJECT_AREA VARCHAR, OBJECT_NAME VARCHAR, OBJECT_TYPE VARCHAR,
            SOURCE VARCHAR, TARGET VARCHAR, MIGRATION_STATUS VARCHAR, PARITY_STATUS VARCHAR,
            VERIFIED_AT TIMESTAMP_LTZ, EVIDENCE VARIANT
        ) COMMENT = ?""", (table, comment))
        cursor.execute('BEGIN')
        try:
            yield cursor
            cursor.execute('COMMIT')
        except Exception:
            cursor.execute('ROLLBACK')
            raise


def write_control(connection, objects, proofs, run_token):
    records = []
    for obj in objects:
        legs = proofs[obj['id']]['legs']
        evidence = json.dumps({'id': obj['id'], 'run_token': run_token,
                               'snowflake_query_ids': legs['snowflake']['query_ids'],
                               'legs': {side: leg['status'] for side, leg in legs.items()}})
        records.append((CONTROL, obj['subject_area'], obj['kind'], obj['name'], obj['source'], obj['target'], evidence))
    with control_transaction(connection, SCHEMA, CONTROL, COMMENT) as cursor:
        cursor.executemany("""MERGE INTO IDENTIFIER(?) t
                USING (SELECT ? AS SUBJECT_AREA, ? AS OBJECT_TYPE, ? AS OBJECT_NAME,
                              ? AS SOURCE, ? AS TARGET, PARSE_JSON(?) AS EVIDENCE) s
                ON t.SUBJECT_AREA=s.SUBJECT_AREA AND t.OBJECT_TYPE=s.OBJECT_TYPE AND t.OBJECT_NAME=s.OBJECT_NAME
                WHEN MATCHED THEN UPDATE SET SOURCE=s.SOURCE, TARGET=s.TARGET,
                    MIGRATION_STATUS='migrated', PARITY_STATUS='verified',
                    VERIFIED_AT=CURRENT_TIMESTAMP(), EVIDENCE=s.EVIDENCE
                WHEN NOT MATCHED THEN INSERT
                    (SUBJECT_AREA,OBJECT_NAME,OBJECT_TYPE,SOURCE,TARGET,MIGRATION_STATUS,
                     PARITY_STATUS,VERIFIED_AT,EVIDENCE)
                    VALUES (s.SUBJECT_AREA,s.OBJECT_NAME,s.OBJECT_TYPE,s.SOURCE,s.TARGET,
                            'migrated','verified',CURRENT_TIMESTAMP(),s.EVIDENCE)""", records)


def write_retirements(connection, objects, run_token):
    """Upsert manifest retirements via a caller-supplied connection."""
    config = RunConfig(run_token)
    schema = config.render('__RUN_DATABASE__.MIGRATION_CONTROL')
    table = schema + '.OBJECTS'
    records = []
    for obj in objects:
        if obj.get('status') != 'retired':
            continue
        reason = obj.get('retirement_reason')
        if obj['target_type'] != 'retire' or not isinstance(reason, str) or not reason.strip():
            raise ValueError('Invalid retirement: ' + obj['id'])
        evidence = json.dumps({'id': obj['id'], 'run_token': run_token, 'retirement_reason': reason})
        records.append((table, obj['subject_area'], obj['kind'], obj['name'], obj['source'], obj['target'],
                        'retired', 'retired', evidence))
    if not records:
        return
    tag = json.dumps({'run_id': run_token, 'act': 'retire', 'step': 'migration-control'}, separators=(',', ':'))
    comment = config.render('run_token=__RUN_TOKEN__ expires=2026-11-24')
    with control_transaction(connection, schema, table, comment, tag) as cursor:
        cursor.executemany("""MERGE INTO IDENTIFIER(?) t
            USING (SELECT ? AS SUBJECT_AREA, ? AS OBJECT_TYPE, ? AS OBJECT_NAME,
                          ? AS SOURCE, ? AS TARGET, ? AS MIGRATION_STATUS, ? AS PARITY_STATUS,
                          PARSE_JSON(?) AS EVIDENCE) s
            ON t.SUBJECT_AREA=s.SUBJECT_AREA AND t.OBJECT_TYPE=s.OBJECT_TYPE AND t.OBJECT_NAME=s.OBJECT_NAME
            WHEN MATCHED THEN UPDATE SET SOURCE=s.SOURCE, TARGET=s.TARGET,
                MIGRATION_STATUS=s.MIGRATION_STATUS, PARITY_STATUS=s.PARITY_STATUS,
                VERIFIED_AT=NULL, EVIDENCE=s.EVIDENCE
            WHEN NOT MATCHED THEN INSERT
                (SUBJECT_AREA,OBJECT_NAME,OBJECT_TYPE,SOURCE,TARGET,MIGRATION_STATUS,
                 PARITY_STATUS,VERIFIED_AT,EVIDENCE)
                VALUES (s.SUBJECT_AREA,s.OBJECT_NAME,s.OBJECT_TYPE,s.SOURCE,s.TARGET,
                        s.MIGRATION_STATUS,s.PARITY_STATUS,NULL,s.EVIDENCE)""", records)


def promote(area, manifest_path):
    original = manifest_path.read_text()
    manifest = yaml.safe_load(original)
    selected = [obj for obj in manifest['objects'] if obj['subject_area'] == area]
    if not selected:
        raise ValueError(f'Unknown subject area: {area!r}')

    snowflake = SnowflakeMeasurements()
    try:
        board = measure_board(manifest, subject_area=area, snowflake=snowflake)
        proofs = {r['id']: r for r in board['rows']}
        eligible, refused = [], []
        for obj in selected:
            if obj.get('status') == 'retired':
                continue
            row = proofs.get(obj['id'], {})
            legs = row.get('legs', {})
            reason = next((legs.get(side, {}).get('reason') or f'{side} parity unmeasured'
                           for side in ('snowflake', 'duckdb')
                           if legs.get(side, {}).get('status') != 'green'), None)
            if reason or row.get('status') != 'green' or snowflake.error:
                refused.append({'id': obj['id'], 'name': obj['name'],
                                'reason': reason or snowflake.error or row.get('reason') or 'parity unmeasured'})
            else:
                eligible.append(obj)

        if eligible:
            for obj in eligible:
                obj['status'] = 'migrated'
            with TemporaryDirectory(dir=manifest_path.parent) as directory:
                staged = Path(directory) / manifest_path.name
                staged.write_text(yaml.safe_dump(manifest, sort_keys=False))
                if manifest_path.read_text() != original:
                    raise RuntimeError('Manifest changed during measurement; rerun promotion')
                write_control(snowflake.connection, eligible, proofs, board['run_token'])
                staged.replace(manifest_path)
            update_migration_summary(board, selected)

        board.update(subject_area=area, promoted=[obj['id'] for obj in eligible], refused=refused)
        return board
    finally:
        snowflake.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--subject-area', required=True)
    parser.add_argument('--manifest', type=Path, default=MANIFEST)
    parser.add_argument('--output', type=Path, default=MIGRATION/'.runs/migration-control.json')
    args = parser.parse_args()
    if args.output.resolve() == args.manifest.resolve():
        parser.error('the output must not overwrite the manifest')
    try:
        board = promote(args.subject_area, args.manifest)
    except ValueError as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(board, indent=2, default=str) + '\n')
    for row in board['refused']:
        print(f"Refused {row['name']} ({row['id']}): {row['reason']}")
    print(f"{args.subject_area}: {len(board['promoted'])} promoted, {len(board['refused'])} refused")
    print(json.dumps(board['summary'], sort_keys=True))
    return 0 if board['promoted'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
