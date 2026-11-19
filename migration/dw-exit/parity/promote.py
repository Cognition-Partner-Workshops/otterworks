"""Promote only objects that pass both legs of a fresh subject-area board."""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from object_board import MANIFEST, MIGRATION, SnowflakeMeasurements, measure_board, update_migration_summary
from parity.connection import COMMENT, DATABASE

SCHEMA = DATABASE + '.MIGRATION_CONTROL'
CONTROL = SCHEMA + '.OBJECTS'


def write_control(connection, objects, proofs, run_token):
    records = []
    for obj in objects:
        legs = proofs[obj['id']]['legs']
        evidence = json.dumps({'id': obj['id'], 'run_token': run_token,
                               'snowflake_query_ids': legs['snowflake']['query_ids'],
                               'legs': {side: leg['status'] for side, leg in legs.items()}})
        records.append((obj['subject_area'], obj['kind'], obj['name'], obj['source'], obj['target'], evidence))
    with connection.cursor() as cursor:
        cursor.execute(f'CREATE SCHEMA IF NOT EXISTS {SCHEMA} COMMENT = ?', (COMMENT,))
        cursor.execute(f"""CREATE TABLE IF NOT EXISTS {CONTROL} (
            SUBJECT_AREA VARCHAR, OBJECT_NAME VARCHAR, OBJECT_TYPE VARCHAR,
            SOURCE VARCHAR, TARGET VARCHAR, MIGRATION_STATUS VARCHAR, PARITY_STATUS VARCHAR,
            VERIFIED_AT TIMESTAMP_LTZ, EVIDENCE VARIANT
        ) COMMENT = ?""", (COMMENT,))
        cursor.execute('BEGIN')
        try:
            cursor.executemany(f"""MERGE INTO {CONTROL} t
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
            cursor.execute('COMMIT')
        except Exception:
            cursor.execute('ROLLBACK')
            raise


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
